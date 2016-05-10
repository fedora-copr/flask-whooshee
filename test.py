import shutil
import tempfile
from unittest import TestCase
import string

import whoosh
from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy

from flask_whooshee import AbstractWhoosheer, Whooshee


class BaseTestCases(object):

    class BaseTest(TestCase):

        def __init__(self, *args, **kwargs):
            super(BaseTestCases.BaseTest, self).__init__(*args, **kwargs)
            self.app = Flask(__name__)

            self.app.config['WHOOSHEE_DIR'] = tempfile.mkdtemp()
            self.app.config['DATABASE_URL'] = 'sqlite:///:memory:'
            self.app.config['TESTING'] = True

            self.db = SQLAlchemy(self.app)

        def setUp(self):

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
            shutil.rmtree(self.app.config['WHOOSHEE_DIR'], ignore_errors=True)
            Whooshee.whoosheers = []
            self.db.drop_all()

        # tests testing model whoosheers should have mw in their name, for custom whoosheers it's cw
        # ideally, there should be a separate class for model whoosheer and custom whoosheer
        # but we also want to test how they coexist

        def test_nothing_found(self):
            found = self.Entry.query.whooshee_search('not there!').all()
            self.assertEqual(len(found), 0)

        def test_mw_result_in_different_fields(self):
            self.db.session.add_all(self.all_inst)
            self.db.session.commit()

            found = self.Entry.query.whooshee_search('chuck').all()
            self.assertEqual(len(found), 2)
            # there is no assertIn in Python 2.6
            self.assertTrue(self.e1 in found)
            self.assertTrue(self.e4 in found)

        def test_cw_result_in_different_tables(self):
            self.db.session.add_all(self.all_inst)
            self.db.session.commit()

            found = self.Entry.query.join(self.User).whooshee_search('chuck').all()
            self.assertEqual(len(found), 3)
            self.assertTrue(self.e1 in found)
            self.assertTrue(self.e2 in found)
            self.assertTrue(self.e4 in found)

        def test_more_items(self):
            expected_count = 0
            # couldn't test for large set due to some bugs either in sqlite or whoosh or SA
            # got: OperationalError: (OperationalError) too many SQL variables u'SELECT entry.id
            #  ... FROM entry \nWHERE entry.id IN (?, ?, .... when whooshee_search is invoked
            #
            # NOTE: This is caused by sqlite db paramater SQLITE_LIMIT_VARIABLE_NUMBER being set to 999 by default
            for batch_size in [2, 5, 7, 20, 50, 300, 500]:  # , 1000]:
                expected_count += batch_size
                self.entry_list = [
                    self.Entry(title=u'foobar_{0}_{1}'.format(expected_count, x),
                               content=u'xxxx', user=self.u1)
                    for x in range(batch_size)
                ]

                self.db.session.add_all(self.entry_list)
                self.db.session.commit()

                found = self.Entry.query.whooshee_search('foobar', order_by_relevance=0).all()
                assert len(found) == expected_count

        def test_order_by_relevance(self):
            entries_to_add = []

            for x in range(1, len(string.ascii_lowercase)+1):
                content = u' '.join([string.ascii_lowercase[i]*3 for i in range(x)])
                entries_to_add.append(self.Entry(title=u'{0}'.format(x), content=content, user=self.u1))

            self.db.session.add_all(entries_to_add)
            self.db.session.commit()

            search_string = u' '.join([string.ascii_lowercase[i]*3 for i in range(26)])

            # no sorting (this assumes (hopes) rows won't be returned in the correct order by default)
            found_entries = self.Entry.query.whooshee_search(search_string, order_by_relevance=0).all()
            titles = [int(entry.title) for entry in found_entries]
            self.assertNotEqual(titles, sorted(titles, reverse=True))

            # sort all
            found_entries = self.Entry.query.whooshee_search(search_string, order_by_relevance=-1).all()
            titles = [int(entry.title) for entry in found_entries]
            self.assertEqual(titles, sorted(titles, reverse=True))

            # sort some (this assumes (hopes) the rest of the rows won't be returned in the correct order by default)
            found_entries = self.Entry.query.whooshee_search(search_string, order_by_relevance=20).all()
            titles = [int(entry.title) for entry in found_entries]
            self.assertNotEqual(titles, sorted(titles, reverse=True))

            # sort all (by setting order_by_relevance to the number of returned search results)
            found_entries = self.Entry.query.whooshee_search(search_string, order_by_relevance=26).all()
            titles = [int(entry.title) for entry in found_entries]
            self.assertEqual(titles, sorted(titles, reverse=True))

            # order_by after whooshee_search (note: order_by following whooshee_search has no impact for the first n results)
            found_entries = self.Entry.query.whooshee_search(search_string, order_by_relevance=26).order_by(self.Entry.id).all()
            titles = [int(entry.title) for entry in found_entries]
            self.assertEqual(titles, sorted(titles, reverse=True))

            # order_by before whooshee_search (note: order_by is a primary criterion here and search ordering is secondary)
            found_entries = self.Entry.query.order_by(self.Entry.id).whooshee_search(search_string, order_by_relevance=26).all()
            titles = [int(entry.title) for entry in found_entries]
            self.assertEqual(titles, sorted(titles))

        def test_whoosheer_search_option(self):

            # alternative whoosheer
            @self.wh.register_whoosheer
            class EntryWhoosheer(AbstractWhoosheer):
                schema = whoosh.fields.Schema(
                    entry_id = whoosh.fields.NUMERIC(stored=True, unique=True),
                    title = whoosh.fields.TEXT()
                )

                models = [self.Entry]

                @classmethod
                def update_entry(cls, writer, entry):
                    writer.update_document(entry_id=entry.id, title=entry.title+'cookie')

                @classmethod
                def insert_entry(cls, writer, entry):
                    writer.add_document(entry_id=entry.id, title=entry.title+'cookie')

            entry = self.Entry(title=u'secret_', content=u'blah blah blah', user=self.u1)
            self.db.session.add(entry)
            self.db.session.commit()

            found = self.Entry.query.join(self.User).whooshee_search('secret_cookie').all()
            self.assertEqual(len(found), 0)
            found = self.Entry.query.join(self.User).whooshee_search('secret_cookie', whoosheer=EntryWhoosheer).all()
            self.assertEqual(len(found), 1)

        def test_reindex(self):
            self.db.session.add_all(self.all_inst)
            self.db.session.commit()
            # generall reindex
            self.wh.reindex()
            # put stallone directly in db and find him only after reindex
            result = self.db.session.execute("INSERT INTO entry VALUES (100, 'rambo', 'pack of one two and three', {0})".format(self.u3.id))
            self.db.session.commit()
            found = self.Entry.query.join(self.User).whooshee_search('rambo').all()
            self.assertEqual(len(found), 0)
            self.wh.reindex()
            found = self.Entry.query.join(self.User).whooshee_search('rambo').all()
            self.assertEqual(len(found), 1)

        # TODO: more :)

class TestsWithApp(BaseTestCases.BaseTest):

    def setUp(self):

        self.wh = Whooshee(self.app)

        super(TestsWithApp, self).setUp()

class TestsWithInitApp(BaseTestCases.BaseTest):

    def setUp(self):

        self.wh = Whooshee()
        self.wh.init_app(self.app)

        super(TestsWithInitApp, self).setUp()
