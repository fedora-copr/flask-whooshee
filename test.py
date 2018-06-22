# -*- coding: utf-8 -*-

import shutil
import tempfile
from unittest import TestCase
import string

import whoosh
from whoosh.filedb.filestore import RamStorage
from flask import Flask
from flask_sqlalchemy import SQLAlchemy, BaseQuery
from sqlalchemy.orm import Query as SQLAQuery
from flask_whooshee import AbstractWhoosheer, Whooshee, WhoosheeQuery


class BaseTestCases(object):

    class BaseTest(TestCase):

        def __init__(self, *args, **kwargs):
            super(BaseTestCases.BaseTest, self).__init__(*args, **kwargs)
            self.app = Flask(__name__)

            self.app.config['WHOOSHEE_DIR'] = tempfile.mkdtemp()
            self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite://'
            self.app.config['TESTING'] = True
            self.app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

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

                @classmethod
                def delete_user(cls, writer, user):
                    # nothing, user doesn't have entries yet
                    pass

                @classmethod
                def delete_entry(cls, writer, entry):
                    writer.delete_by_term('entry_id', entry.id)

            @self.wh.register_model('attribute')
            class ModelWithNonIntID(self.db.Model):
                id = self.db.Column(self.db.String, primary_key=True)
                attribute = self.db.Column(self.db.String)

            self.User = User
            self.Entry = Entry
            self.EntryUserWhoosheer = EntryUserWhoosheer
            self.ModelWithNonIntID = ModelWithNonIntID

            self.db.create_all()

            self.u1 = User(name=u'chuck')
            self.u2 = User(name=u'arnold')
            self.u3 = User(name=u'silvester')

            self.e1 = Entry(title=u'chuck nr. 1 article', content=u'blah blah blah', user=self.u1)
            self.e2 = Entry(title=u'norris nr. 2 article', content=u'spam spam spam', user=self.u1)
            self.e3 = Entry(title=u'arnold blah', content=u'spam is cool', user=self.u2)
            self.e4 = Entry(title=u'the less dangerous', content=u'chuck is better', user=self.u3)

            self.n1 = ModelWithNonIntID(id='guybrush', attribute='threepwood')

            self.all_inst = [self.u1, self.u2, self.u3, self.e1, self.e2, self.e3, self.e4, self.n1]

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

        def test_no_autoupdate(self):
            for whoosheer in self.wh.whoosheers:
                whoosheer.auto_update = False
            self.db.session.add(self.u1)
            self.db.session.commit()

            found = self.Entry.query.whooshee_search('chuck').all()
            self.assertEqual(len(found), 0) # nothing is found

            for whoosheer in self.wh.whoosheers:
                whoosheer.auto_update = True
            self.db.session.add(self.u2)
            self.db.session.commit()

            found = self.Entry.query.whooshee_search('arnold').all()
            self.assertEqual(len(found), 1) # arnold is found

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

        def test_add(self):
            # test that the add operation works
            found = self.Entry.query.whooshee_search('blah blah blah').all()
            self.assertEqual(len(found), 0)

            self.db.session.add(self.e1)
            self.db.session.commit()

            found = self.Entry.query.whooshee_search('blah blah blah').all()
            self.assertEqual(len(found), 1)

        # def test_update(self):
        #     # test that the update operation works
        #     self.db.session.add(self.e1)
        #     self.db.session.commit()
        #     self.db.session.remove()
        #
        #     found = self.Entry.query.whooshee_search('blah blah blah').all()
        #     self.assertEqual(len(found), 1)
        #
        #     # TODO there is an error here "InvalidRequestError: This session is in 'committed' state; no further SQL can be emitted within this transaction."
        #     self.e1.content = 'ramble ramble ramble'
        #     self.db.session.commit()
        #
        #     found = self.Entry.query.whooshee_search('ramble ramble ramble').all()
        #     self.assertEqual(len(found), 1)
        #
        #     found = self.Entry.query.whooshee_search('blah blah blah').all()
        #     self.assertEqual(len(found), 0)

        def test_delete(self):
            # test that the delete operation works
            self.db.session.add(self.e1)
            self.db.session.commit()

            found = self.Entry.query.whooshee_search('blah blah blah').all()
            self.assertEqual(len(found), 1)

            self.db.session.delete(self.e1)
            self.db.session.flush()

            found = self.Entry.query.whooshee_search('blah blah blah').all()
            self.assertEqual(len(found), 0)

            # make sure that the entry has actually been deleted from the whoosh index
            # https://github.com/bkabrda/flask-whooshee/pull/26#issuecomment-257549715
            whoosheer = next(w for w in self.wh.whoosheers if set(w.models) == set([self.Entry]))
            self.assertEqual(len(whoosheer.search('blah blah blah')), 0)

        def test_sqlalchemy_aliased(self):
            # make sure that sqlalchemy aliased entities are recognized
            self.db.session.add_all(self.all_inst)
            self.db.session.commit()
            alias = self.db.aliased(self.Entry)
            self.assertEqual(len(self.User.query.join(alias).whooshee_search('chuck').all()), 3)

        def test_unicode_search(self):
            # we just need to make sure this doesn't fail (problem only on py-2)
            self.Entry.query.whooshee_search('ěšč').all()
            self.Entry.query.whooshee_search(u'ěšč').all()

        def test_enable_indexing(self):
            self.app.extensions['whooshee']['enable_indexing'] = False
            self.db.session.add_all(self.all_inst)
            self.db.session.commit()
            # test joined search
            found = self.Entry.query.join(self.User).whooshee_search('arnold').all()
            self.assertEqual(found, [])
            # test simple search
            found = self.Entry.query.whooshee_search('arnold').all()
            self.assertEqual(found, [])

            # reenable and see if everything works now
            self.app.extensions['whooshee']['enable_indexing'] = True
            self.db.session.add(self.Entry(user=self.u1, title=u'newentry'))
            self.db.session.commit()
            found = self.Entry.query.whooshee_search('newentry').all()
            self.assertEqual(len(found), 1)

        def test_model_with_nonint_id(self):
            self.db.session.add(self.n1)
            self.db.session.commit()
            found = self.ModelWithNonIntID.query.whooshee_search('threepwood').all()
            self.assertEqual(len(found), 1)
            found[0].attribute = 'LeChuck'
            self.db.session.commit()
            found = self.ModelWithNonIntID.query.whooshee_search('LeChuck').all()
            self.assertEqual(len(found), 1)
            self.n1.query.delete()
            found = self.ModelWithNonIntID.query.whooshee_search('LeChuck').all()
            self.assertEqual(len(found), 0)


class TestsWithApp(BaseTestCases.BaseTest):

    def setUp(self):

        self.wh = Whooshee(self.app)

        super(TestsWithApp, self).setUp()

class TestsWithInitApp(BaseTestCases.BaseTest):

    def setUp(self):

        self.wh = Whooshee()

        super(TestsWithInitApp, self).setUp()
        # we intentionally call `init_app` after creating whoosheers, to test that lazy app
        # intialization is possible
        self.wh.init_app(self.app)

        self.ctx = self.app.app_context()
        self.ctx.push()

    def tearDown(self):
        super(TestsWithInitApp, self).tearDown()
        self.ctx.pop()


class TestsAppWithMemoryStorage(TestCase):

    def setUp(self):
        self.app = Flask(__name__)

        self.app.config['WHOOSHEE_MEMORY_STORAGE'] = True
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite://'
        self.app.config['TESTING'] = True
        self.app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

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

            @classmethod
            def delete_user(cls, writer, user):
                # nothing, user doesn't have entries yet
                pass

            @classmethod
            def delete_entry(cls, writer, entry):
                writer.delete_by_term('entry_id', entry.id)

        self.User = User
        self.Entry = Entry
        self.EntryUserWhoosheer = EntryUserWhoosheer

        self.db.create_all(app=self.app)

        self.u1 = User(name=u'chuck')
        self.u2 = User(name=u'arnold')
        self.u3 = User(name=u'silvester')

        self.e1 = Entry(title=u'chuck nr. 1 article', content=u'blah blah blah', user=self.u1)
        self.e2 = Entry(title=u'norris nr. 2 article', content=u'spam spam spam', user=self.u1)
        self.e3 = Entry(title=u'arnold blah', content=u'spam is cool', user=self.u2)
        self.e4 = Entry(title=u'the less dangerous', content=u'chuck is better', user=self.u3)

        self.all_inst = [self.u1, self.u2, self.u3, self.e1, self.e2, self.e3, self.e4]
        self.db.session.add_all(self.all_inst)
        self.db.session.commit()

    def tearDown(self):
        self.db.drop_all(app=self.app)

    def test_memory_storage(self):
        indexes = self.app.extensions['whooshee']['whoosheers_indexes']
        self.assertTrue(isinstance(indexes[self.EntryUserWhoosheer].storage, RamStorage))


class TestMultipleApps(TestCase):
    def setUp(self):
        self.db = SQLAlchemy()
        self.wh = Whooshee()
        for a in ['app1', 'app2']:
            app = Flask(a)
            app.config['WHOOSHEE_DIR'] = tempfile.mkdtemp()
            app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite://'
            app.config['TESTING'] = True
            app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
            self.db.init_app(app)
            self.wh.init_app(app)
            setattr(self, a, app)

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

            @classmethod
            def delete_user(cls, writer, user):
                # nothing, user doesn't have entries yet
                pass

            @classmethod
            def delete_entry(cls, writer, entry):
                writer.delete_by_term('entry_id', entry.id)

        self.User = User
        self.Entry = Entry
        self.EntryUserWhoosheer = EntryUserWhoosheer

        self.db.create_all(app=self.app1)
        self.db.create_all(app=self.app2)

        self.u1 = User(name=u'chuck')
        self.u2 = User(name=u'arnold')
        self.u3 = User(name=u'silvester')

        self.e1 = Entry(title=u'chuck nr. 1 article', content=u'blah blah blah', user=self.u1)
        self.e2 = Entry(title=u'norris nr. 2 article', content=u'spam spam spam', user=self.u1)
        self.e3 = Entry(title=u'arnold blah', content=u'spam is cool', user=self.u2)
        self.e4 = Entry(title=u'the less dangerous', content=u'chuck is better', user=self.u3)

        self.all_inst = [self.u1, self.u2, self.u3, self.e1, self.e2, self.e3, self.e4]

    def tearDown(self):
        shutil.rmtree(self.app1.config['WHOOSHEE_DIR'], ignore_errors=True)
        shutil.rmtree(self.app2.config['WHOOSHEE_DIR'], ignore_errors=True)
        self.db.drop_all(app=self.app1)
        self.db.drop_all(app=self.app2)

    def test_multiple_apps(self):
        # IIUC, you can't add the same model instance under multiple apps with flask-sqlalchemy
        #  this pretty much reduces the testing to "make sure we used the right app to do
        #  the search"
        with self.app1.test_request_context():
            self.db.session.add_all([self.u2, self.u3, self.e3, self.e4])
            self.db.session.commit()

        with self.app2.test_request_context():
            self.db.session.add_all([self.u1, self.e1, self.e2])
            self.db.session.commit()

        # make sure that entities stored only for app1 are only found for app1, same for app2
        with self.app1.test_request_context():
            q = self.Entry.query.whooshee_search('chuck')
            self.assertEqual(len(q.all()), 1)
            self.assertEqual(q[0].title, 'the less dangerous')
        with self.app2.test_request_context():
            q = self.Entry.query.whooshee_search('chuck')
            self.assertEqual(len(q.all()), 1)
            self.assertEqual(q[0].title, 'chuck nr. 1 article')

        # try deleting everything from one app and then searching again
        with self.app1.test_request_context():
            self.Entry.query.delete()
            q = self.Entry.query.whooshee_search('chuck')
            self.assertEqual(len(q.all()), 0)
        with self.app2.test_request_context():
            q = self.Entry.query.whooshee_search('chuck')
            self.assertEqual(len(q.all()), 1)
            self.assertEqual(q[0].title, 'chuck nr. 1 article')


class TestDoesntMixesWithModelQueryClass(TestCase):
    def setUp(self):
        self.app = Flask(__name__)

        self.app.config['WHOOSHEE_MEMORY_STORAGE'] = True
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite://'
        self.app.config['TESTING'] = True
        self.app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

        self.db = SQLAlchemy(self.app)
        self.wh = Whooshee(self.app)

    def test_mixes_with_model_query(self):
        class CustomQueryClass(BaseQuery):
            pass

        self._make_model_and_whoosheer(CustomQueryClass)
        self.assertEqual('WhoosheeCustomQueryClass', self.user_model.query_class.__name__)

    def test_doesnt_mix_with_default_query_class(self):
        self._make_model_and_whoosheer(BaseQuery)
        self.assertIs(self.wh.query, self.user_model.query_class)

    def test_doesnt_mix_with_explicit_whooshee_query_class(self):
        self._make_model_and_whoosheer(WhoosheeQuery)
        self.assertIs(self.wh.query, self.user_model.query_class)

    def test_doesnt_mix_with_whoosheequerywithapp(self):
        self._make_model_and_whoosheer(self.wh.query)
        self.assertIs(self.wh.query, self.user_model.query_class)

    def test_doesnt_mix_with_SQLA_query_class(self):
        self._make_model_and_whoosheer(SQLAQuery)
        self.assertIs(self.wh.query, self.user_model.query_class)

    def test_mixes_with_whooshee_query_subclass(self):
        class CustomWhoosheeQuery(WhoosheeQuery):
            pass

        self._make_model_and_whoosheer(CustomWhoosheeQuery)
        self.assertTrue(issubclass(self.user_model.query_class, CustomWhoosheeQuery))
        self.assertTrue(issubclass(self.user_model.query_class, self.wh.query))

    def test_overwrites_if_query_class_is_not_type(self):
        self._make_model_and_whoosheer(5)
        self.assertIs(self.wh.query, self.user_model.query_class)

    def _make_model_and_whoosheer(self, query=None):
        class User(self.db.Model):
            query_class = query
            id = self.db.Column(self.db.Integer, primary_key=True)
            name = self.db.Column(self.db.String)

        @self.wh.register_whoosheer
        class UserWhoosheer(AbstractWhoosheer):
            schema = whoosh.fields.Schema(
                user_id = whoosh.fields.NUMERIC(stored=True),
                username = whoosh.fields.TEXT())

            models = [User]

            @classmethod
            def update_user(cls, writer, user):
                pass # TODO: update all users entries

            @classmethod
            def update_entry(cls, writer, entry):
                writer.update_document(user_id=entry.user.id,
                                        username=entry.user.name)

            @classmethod
            def insert_user(cls, writer, user):
                # nothing, user doesn't have entries yet
                pass

            @classmethod
            def delete_user(cls, writer, user):
                # nothing, user doesn't have entries yet
                pass

        self.user_model = User
        self.user_whoosheer = UserWhoosheer
