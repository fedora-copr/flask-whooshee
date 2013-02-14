import abc
import os
import re

import whoosh
import whoosh.fields
import whoosh.index
import whoosh.qparser

from flask.ext.sqlalchemy import models_committed

class AbstractWhoosheer(object):
    __metaclass__ = abc.ABCMeta

    @classmethod
    def search(cls, search_string, values_of=''):
        prepped_string = cls.prep_search_string(search_string)
        with cls.index.searcher() as searcher:
            parser = whoosh.qparser.MultifieldParser(cls.schema.names(), cls.index.schema)
            query = parser.parse(prepped_string)
            results = searcher.search(query)
            if values_of:
                return map(lambda x: x[values_of], results)
            return results

    @classmethod
    def prep_search_string(cls, search_string):
        s = search_string.strip()
        # we don't want stars from user
        s = s.replace('*', '')
        if len(s) < cls.search_string_min_len:
            raise ValueError('Search string must have at least 3 characters')
        # replace multiple whitechars with one space
        s = u'*{0}*'.format(re.sub('[\s]+', '*', s))
        # TODO: some sanitization
        return s

class Whooshee(object):
    _underscore_re1 = re.compile(r'(.)([A-Z][a-z]+)')
    _underscore_re2 = re.compile('([a-z0-9])([A-Z])')

    def __init__(self, app):
        self.index_path_root = app.config.get('WHOOSHEE_DIR', '') or 'whooshee'
        self.whoosheers = []
        self.search_string_min_len = app.config.get('WHOSHEE_MIN_STRING_LEN', 3)
        models_committed.connect(self.on_commit, sender=app)
        if not os.path.exists(self.index_path_root):
            os.makedirs(self.index_path_root)

    def register_whoosheer(self, wh):
        if not hasattr(wh, 'search_string_min_len'):
            wh.search_string_min_len = self.search_string_min_len
        if not hasattr(wh, 'index_subdir'):
            wh.index_subdir = self.camel_to_snake(wh.__name__)
        self.whoosheers.append(wh)
        self.create_index(wh)
        return wh

    def register_model(self, *index_fields):
        # construct subclass of AbstractWhoosheer for a model
        class ModelWhoosheer(AbstractWhoosheer):
            pass

        mwh = ModelWhoosheer

        def inner(model):
            mwh.index_subdir = model.__tablename__
            mwh.models = [model]

            schema_attrs = {}
            for field in model.__table__.columns:
                if field.primary_key:
                    primary = field.name
                    schema_attrs[field.name] = whoosh.fields.NUMERIC(stored=True, unique=True)
                elif field.name in index_fields:
                    schema_attrs[field.name] = whoosh.fields.TEXT()
            mwh.schema = whoosh.fields.Schema(**schema_attrs)

            @classmethod
            def update_model(cls, writer, model):
                attrs = {primary: getattr(model, primary)}
                for f in index_fields:
                    attrs[f] = getattr(model, f)
                    if not isinstance(attrs[f], int):
                        attrs[f] = unicode(attrs[f])
                writer.update_document(**attrs)

            @classmethod
            def insert_model(cls, writer, model):
                attrs = {primary: getattr(model, primary)}
                for f in index_fields:
                    attrs[f] = getattr(model, f)
                    if not isinstance(attrs[f], int):
                        attrs[f] = unicode(attrs[f])
                writer.add_document(**attrs)

            setattr(mwh, 'update_{0}'.format(model.__name__.lower()), update_model)
            setattr(mwh, 'insert_{0}'.format(model.__name__.lower()), insert_model)

            model._whoosheer_ = mwh
            model.whoosh_search = mwh.search
            self.register_whoosheer(mwh)
            return model

        return inner

    def create_index(self, wh):
        index_path = os.path.join(self.index_path_root, wh.index_subdir)
        if whoosh.index.exists_in(index_path):
            index = whoosh.index.open_dir(index_path)
        else:
            if not os.path.exists(index_path):
                os.makedirs(index_path)
            index = whoosh.index.create_in(index_path, wh.schema)
        wh.index = index

    def on_commit(self, app, changes):
        for wh in self.whoosheers:
            writer = wh.index.writer()
            for change in changes:
                if change[0].__class__ in wh.models:
                    method_name = '{0}_{1}'.format(change[1], change[0].__class__.__name__.lower())
                    getattr(wh, method_name)(writer, change[0])
            writer.commit()

    def camel_to_snake(self, s):
        return self._underscore_re2.sub(r'\1_\2', self._underscore_re1.sub(r'\1_\2', s)).lower()
