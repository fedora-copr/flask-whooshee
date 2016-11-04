.. Flask-Whooshee documentation master file, created by
   sphinx-quickstart on Fri Nov  4 10:11:36 2016.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Flask-Whooshee
==============

.. module:: flask_whooshee

*Customizable Flask-SQLAlchemy - Whoosh Integration*

Flask-Whooshee provides more advanced Whoosh integration into Flask.
Its main power is in the ability to index and search joined queries.


Installation
------------

Install the extension with one of the following commands::

    $ easy_install Flask-Whooshee

or alternatively if you have pip installed::

    $ pip install Flask-Whooshee


Set Up
------

TODO: Explain init_app and such..


Following configuration options are available:

+-----------------------------+-----------------------------------------------------------------------+
| Option                      | Description                                                           |
+=============================+=======================================================================+
| ``WHOOSHEE_DIR``            | The path for the whoosh index (defaults to **whooshee**)              |
+-----------------------------+-----------------------------------------------------------------------+
| ``WHOOSHEE_MIN_STRING_LEN`` | Min. characters for the search string (defaults to **3**)             |
+-----------------------------+-----------------------------------------------------------------------+
| ``WHOOSHEE_WRITER_TIMEOUT`` | How long should whoosh try to acquire write lock? (defaults to **2**) |
+-----------------------------+-----------------------------------------------------------------------+

API
---

.. autoclass:: Whooshee
    :members:

.. autoclass:: WhoosheeQuery
    :members:

.. autoclass:: AbstractWhoosheer
    :members:


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
