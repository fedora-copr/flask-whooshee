Flask-Whooshee
==============

[![Build Status](https://travis-ci.org/bkabrda/flask-whooshee.svg?branch=master)](https://travis-ci.org/bkabrda/flask-whooshee)
[![PyPI Version](https://img.shields.io/pypi/v/flask-whooshee.svg)](https://pypi.python.org/pypi/flask-whooshee)
[![License](https://img.shields.io/badge/license-BSD-yellow.svg)](https://github.com/bkabrda/flask-whooshee)

*Adds Whoosh integration to Flask-SQLAlchemy.*

Flask-Whooshee provides a more advanced Whoosh integration for Flask.
Its main power is in the ability to index and search joined queries.


The project is in early beta stage and is fairly stable.
However, API may still change before 1.0.0 release.

Flask-Whooshee is licensed under BSD License.
Note that up until 0.3.0 it was licensed under GPLv2+.


Quickstart
----------

Install it from PyPI:

```
$ pip install Flask-Whooshee
```

Flask-Whooshee supports two different methods of setting up the extension.
You can either initialize it directly, thus binding it to a specific
application instance:

```python
app = Flask(__name__)
whooshee = Whooshee(app)
```

and the second is to use the factory pattern which will allow you to
configure whooshee at a later point:

```python
whooshee = Whooshee()
def create_app():
    app = Flask(__name__)
    whooshee.init_app(app)
    return app
```

Now you can create a basic whoosheer:

```python
@whooshee.register_model('title', 'content')
class Entry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String)
    content = db.Column(db.Text)
```

and finally you can search the model:

```python
Entry.query.whooshee_search('chuck norris').order_by(Entry.id.desc()).all()
```


Links
=====

* [Documentation](https://flask-whooshee.readthedocs.io)
* [Source Code](https://github.com/bkabrda/flask-whooshee)
* [Issues](https://github.com/bkabrda/flask-whooshee/issues)
