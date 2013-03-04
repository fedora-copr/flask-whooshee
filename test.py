import shutil
import tempfile
from unittest import TestCase

import whoosh
from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy

from flask_whooshee import AbstractWhoosheer, Whooshee


class Tests(TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config['WHOOSHEE_DIR'] = tempfile.mkdtemp()
        self.app.config['DATABASE_URL'] = 'sqlite:///:memory:'
        self.app.config['TESTING'] = True
        self.db = SQLAlchemy(self.app)
        self.wh = Whooshee(self.app)

        class User(self.db.Model):
            id = self.db.Column(self.db.Integer, primary_key=True)
            name = self.db.Column(self.db.String)

        # separate index for just entry
        @self.wh.register_model('title', 'content')
        class Entry(self.db.Model):
            id = self.db.Column(self.db.Integer, primary_key=True)
            title = self.db.Column(self.db.String)
            content = self.db.Column(self.db.Text)
            user = self.db.relationship(User, backref = self.db.backref('entries'))
            user_id = self.db.Column(self.db.Integer, self.db.ForeignKey('user.id'))

        # index for both entry and user
        @self.wh.register_whoosheer
        class EntryUserWhoosheer(AbstractWhoosheer):
            schema = whoosh.fields.Schema(
                entry_id = whoosh.fields.NUMERIC(stored=True, unique=True),
                user_id = whoosh.fields.NUMERIC(stored=True),
                username = whoosh.fields.TEXT(),
                title = whoosh.fields.TEXT(),
                content = whoosh.fields.TEXT())

            models = [Entry, User]

            @classmethod
            def update_user(cls, writer, user):
                pass # TODO: update all users entries 

            @classmethod
            def update_entry(cls, writer, entry):
                writer.update_document(entry_id=entry.id,
                                       user_id=entry.user.id,
                                       username=entry.user.name,
                                       title=entry.title,
                                       content=entry.content)

            @classmethod
            def insert_user(cls, writer, user):
                # nothing, user doesn't have entries yet
                pass

            @classmethod
            def insert_entry(cls, writer, entry):
                writer.add_document(entry_id=entry.id,
                                    user_id=entry.user.id,
                                    username=entry.user.name,
                                    title=entry.title,
                                    content=entry.content)

        self.User = User
        self.Entry = Entry
        self.EntryUserWhoosheer = EntryUserWhoosheer

        self.db.create_all()

        self.u1 = User(name=u'chuck')
        self.u2 = User(name=u'arnold')
        self.u3 = User(name=u'silvester')

        self.e1 = Entry(title=u'chuck nr. 1 article', content=u'blah blah blah', user=self.u1)
        self.e2 = Entry(title=u'norris nr. 2 article', content=u'spam spam spam', user=self.u1)
        self.e3 = Entry(title=u'arnold blah', content=u'spam is cool', user=self.u2)
        self.e4 = Entry(title=u'the less dangerous', content=u'chuck is better', user=self.u3)

        self.all_inst = [self.u1, self.u2, self.u3, self.e1, self.e2, self.e3, self.e4]

    def tearDown(self):
        shutil.rmtree(self.app.config['WHOOSHEE_DIR'])
        Whooshee.whoosheers = []
        self.db.drop_all()

    # tests testing model whoosheers should have mw in their name, for custom whoosheers it's cw
    # ideally, there should be a separate class for model whoosheer and custom whoosheer
    # but we also want to test how they coexist

    def test_mw_result_in_different_fields(self):
        self.db.session.add_all(self.all_inst)
        self.db.session.commit()

        found = self.Entry.query.whooshee_search('chuck').all()
        self.assertEqual(len(found), 2)
        self.assertIn(self.e1, found)
        self.assertIn(self.e4, found)

    def test_cw_result_in_different_tables(self):
        self.db.session.add_all(self.all_inst)
        self.db.session.commit()

        found = self.Entry.query.join(self.User).whooshee_search('chuck').all()
        self.assertEqual(len(found), 3)
        self.assertIn(self.e1, found)
        self.assertIn(self.e2, found)
        self.assertIn(self.e4, found)

    # TODO: more :)
