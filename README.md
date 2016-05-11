flask-whooshee
==============

Customizable Flask - SQLAlchemy - Whoosh integration

flask-whooshee provides more advanced Whoosh integration into Flask. Its main power is in the ability to index and search joined queries (which to my knowledge no other Flask - SQLAlchemy - Whoosh integration library doesn't provide).

How it works
------------
flask-whooshee is based on so-called whoosheers. These represent Whoosh indexes and they are responsible for indexing new/updated fields. There are two types of whoosheers. The simple *model whoosheers*, that index fields from just one index look like this:

```python
from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.whooshee import Whooshee

app = Flask(__name__)
app.config['WHOOSHEE_DIR'] = '/tmp/whoosheers'
db = SQLAlchemy(app)
whooshee = Whooshee(app)

@whooshee.register_model('title', 'content')
class Entry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String)
    content = db.Column(db.Text)
```

Now you can use queries like this:
```python
# will find entries whose title or content matches 'chuck norris'
Entry.query.whooshee_search('chuck norris').order_by(Entry.id.desc()).all()
```

The more complicated custom whoosheers allow you to create indexes and search across multiple tables. Create them like this:

```python
from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.whooshee import Whooshee, AbstractWhoosheer

app = Flask(__name__)
app.config['WHOOSHEE_DIR'] = /tmp/whoosheers
# how long should whooshee try to acquire write lock? (defaults to 2)
app.config['WHOOSHEE_WRITER_TIMEOUT'] = 3
db = SQLAlchemy(app)
whooshee = Whooshee(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String)

# you can still keep the model whoosheer
@whooshee.register_model('title', 'content')
class Entry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String)
    content = db.Column(db.Text)
    user = self.db.relationship(User, backref = self.db.backref('entries'))
    user_id = self.db.Column(self.db.Integer, self.db.ForeignKey('user.id'))

# create a custom whoosheer class
@whooshee.register_whoosheer
class EntryUserWhoosheer(AbstractWhoosheer):
    # create schema, the unique attribute must be in form of
    # model.__name__.lower() + '_' + 'id' (name of model primary key)
    schema = whoosh.fields.Schema(
        entry_id = whoosh.fields.NUMERIC(stored=True, unique=True),
        user_id = whoosh.fields.NUMERIC(stored=True),
        username = whoosh.fields.TEXT(),
        title = whoosh.fields.TEXT(),
        content = whoosh.fields.TEXT())

    # don't forget to list the included models
    models = [Entry, User]

    # create insert_* and update_* methods for all models
    # if you have camel case names like FooBar, just lowercase them: insert_foobar, update_foobar
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
```

Now you can search join queries like this:
```python
# will find any joined entry<->query, whose User.name or Entry.title or Entry.content matches 'chuck norris'
Entry.query.join(User).whooshee_search('chuck norris').order_by(Entry.id.desc()).all()
```

The whoosheer that is used for searching is, by default, selected based on the models participating in the query.
This set of models is compared against the value of `models` attribute of each registered whoosheer and the one
with an exact match is selected. You can override this behaviour by explicitly passing whoosheer that should be
used for searching to the `whooshee_search` method. This is useful if you don't want to join on all the models that
form the search index. For example:
```python
Entry.query.whooshee_search('chuck norris', whoosheer=EntryUserWhoosheer).order_by(Entry.id.desc()).all()
```
If there exists an entry of a user called 'chuck norris', this entry will be found because the custom whoosheer, that contains field `username`, will be used. But without the whoosheer option, that entry won't be found (unless it has 'chuck&nbsp;norris' in content or title) because the model whoosheer will be used.

### Reindex

Available since v0.0.9.

If you lost your whooshee data and you need to recreate it, you can run inside Flask application context:

```
from flask.ext.whooshee import Whooshee
w = Whooshee(app)
w.reindex()
```
### Search results ordering

By default only first 10 (for optimization reasons) search results are sorted by relevance.
You can modify this behaviour by explicitly setting the value of `order_by_relevance`
parameter of the `whooshee_search` method.

```python
# return all search results sorted by relevance (only Chuck Norris can do this)
Entry.query.join(User).whooshee_search('chuck norris', order_by_relevance=-1).all()

# disable sorting altogether
Entry.query.join(User).whooshee_search('chuck norris', order_by_relevance=0).all()

# return first 25 rows sorted by their relevance
Entry.query.join(User).whooshee_search('chuck norris', order_by_relevance=25).all()
```


Project is in early alpha stage, documentation and more functionality will be landing soon.

Licensed under GPLv2+
