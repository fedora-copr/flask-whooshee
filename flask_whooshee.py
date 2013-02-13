import abc
import os
import re

import whoosh
import whoosh.fields
import whoosh.index
import whoosh.qparser

from flask.ext.sqlalchemy import models_committed

class AbstractSchema(object):
    __metaclass__ = abc.ABCMeta
    models = []
    index_subdir = 'subdir'
    index = None

    @classmethod
    def search(cls, search_string, values_of=''):
        prepped_string = cls.prep_search_string(search_string)
        with cls.index.searcher() as searcher:
            parser = whoosh.qparser.MultifieldParser(cls.Schema().names(), cls.index.schema)
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
    def __init__(self, app):
        self.index_path_root = app.config.get('WHOOSHEE_DIR', '') or 'whooshee'
        self.schemas = []
        self.search_string_min_len = app.config.get('WHOSHEE_MIN_STRING_LEN', 3)
        models_committed.connect(self.on_commit, sender=app)

    def register_schema(self, schema):
        if not hasattr(schema, 'search_string_min_len'):
            schema.search_string_min_len = self.search_string_min_len
        self.schemas.append(schema)
        self.create_index(schema)
        return schema

    def create_index(self, schema):
        index_path = os.path.join(self.index_path_root, schema.index_subdir)
        if whoosh.index.exists_in(index_path):
            index = whoosh.index.open_dir(index_path)
        else:
            if not os.path.exists(index_path):
                os.makedirs(index_path)
            index = whoosh.index.create_in(index_path, schema.Schema)
        schema.index = index

    def on_commit(self, app, changes):
        for schema in schemas:
            writer = schema.index.writer()
            for change in changes:
                if change[0].__class__ in schema.models:
                    method_name = '{0}_{1}'.format(change[1], change[0].__class__.__name__.lower())
                    getattr(schema, method_name)(writer, change[0])
            writer.commit()

