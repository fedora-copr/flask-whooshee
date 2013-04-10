import abc
import os
import re

import whoosh
import whoosh.fields
import whoosh.index
import whoosh.qparser

from flask.ext.sqlalchemy import models_committed, BaseQuery
from sqlalchemy.orm.mapper import Mapper

class WhoosheeQuery(BaseQuery):
    # TODO: add an option to override used Whoosheer
    def whooshee_search(self, search_string, group=whoosh.qparser.OrGroup, match_substrings=True):
        ### inspiration taken from flask-WhooshAlchemy
        # find out all entities in join
        entities = set()
        # directly queried entities
        for cd in self.column_descriptions:
            entities.add(cd['type'])
        # joined entities
        if self._join_entities and isinstance(self._join_entities[0], Mapper):
            # SQLAlchemy >= 0.8.0
            entities.update(set(map(lambda x: x.entity, self._join_entities)))
        else:
            # SQLAlchemy < 0.8.0
            entities.update(set(self._join_entities))

        whoosheer = next(w for w in Whooshee.whoosheers if set(w.models) == entities)

        # TODO what if unique field doesn't exist or there are multiple?
        for fname, field in whoosheer.schema._fields.items():
            if field.unique:
                uniq = fname

        # TODO: use something more general than id
        res = whoosheer.search(search_string=search_string,
                               values_of=uniq,
                               group=group,
                               match_substrings=match_substrings)
        if not res:
            return self.filter('null')

        # transform unique field name into model attribute field
        attr = None

        if hasattr(whoosheer, '_is_model_whoosheer'):
            attr = getattr(whoosheer.models[0], uniq)
        else:
            # non-model whoosheers must have unique field named
            # model.__name__.lower + '_' + attr
            for m in whoosheer.models:
                if m.__name__.lower() == uniq.split('_')[0]:
                    attr = getattr(m, uniq.split('_')[1])

        return self.filter(attr.in_(res))

class AbstractWhoosheer(object):
    __metaclass__ = abc.ABCMeta

    @classmethod
    def search(cls, search_string, values_of='', group=whoosh.qparser.OrGroup, match_substrings=True):
        prepped_string = cls.prep_search_string(search_string, match_substrings)
        with cls.index.searcher() as searcher:
            parser = whoosh.qparser.MultifieldParser(cls.schema.names(), cls.index.schema, group=group)
            query = parser.parse(prepped_string)
            results = searcher.search(query)
            if values_of:
                return map(lambda x: x[values_of], results)
            return results

    @classmethod
    def prep_search_string(cls, search_string, match_substrings):
        s = search_string.strip()
        # we don't want stars from user
        s = s.replace('*', '')
        if len(s) < cls.search_string_min_len:
            raise ValueError('Search string must have at least 3 characters')
        # replace multiple with star space star
        if match_substrings:
            s = u'*{0}*'.format(re.sub('[\s]+', '* *', s))
        # TODO: some sanitization
        return s

class Whooshee(object):
    _underscore_re1 = re.compile(r'(.)([A-Z][a-z]+)')
    _underscore_re2 = re.compile('([a-z0-9])([A-Z])')
    whoosheers = []

    def __init__(self, app):
        self.index_path_root = app.config.get('WHOOSHEE_DIR', '') or 'whooshee'
        self.search_string_min_len = app.config.get('WHOSHEE_MIN_STRING_LEN', 3)
        models_committed.connect(self.on_commit, sender=app)
        if not os.path.exists(self.index_path_root):
            os.makedirs(self.index_path_root)

    def register_whoosheer(self, wh):
        if not hasattr(wh, 'search_string_min_len'):
            wh.search_string_min_len = self.search_string_min_len
        if not hasattr(wh, 'index_subdir'):
            # TODO: do we really want/need to use camel casing?
            # everywhere else, there is just .lower()
            wh.index_subdir = self.camel_to_snake(wh.__name__)
        self.__class__.whoosheers.append(wh)
        self.create_index(wh)
        for model in wh.models:
            model.query_class = WhoosheeQuery
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
            # we can't check with isinstance, because ModelWhoosheer is private
            # so use this attribute to find out
            mwh._is_model_whoosheer = True

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
        for wh in self.__class__.whoosheers:
            writer = wh.index.writer()
            for change in changes:
                if change[0].__class__ in wh.models:
                    method_name = '{0}_{1}'.format(change[1], change[0].__class__.__name__.lower())
                    getattr(wh, method_name)(writer, change[0])
            writer.commit()

    def camel_to_snake(self, s):
        return self._underscore_re2.sub(r'\1_\2', self._underscore_re1.sub(r'\1_\2', s)).lower()
