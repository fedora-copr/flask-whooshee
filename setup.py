#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Flask-Whooshee
--------------

Adds Whoosh support to Flask-SQLAlchemy.

Links
`````

* `Documentation <https://pythonhosted.org/Flask-Whooshee/>`_
* `Source Code <https://github.com/bkabrda/flask-whooshee>`_
* `Issues <https://github.com/bkabrda/flask-whooshee/issues>`_
"""
from setuptools import setup

setup(
    name='flask-whooshee',
    version='0.3.1',
    description='Flask-SQLAlchemy - Whoosh Integration',
    long_description=__doc__,
    keywords='flask, sqlalchemy, whoosh',
    author='Bohuslav "Slavek" Kabrda',
    author_email='bkabrda@redhat.com',
    url='https://github.com/bkabrda/flask-whooshee',
    license='BSD',
    py_modules=['flask_whooshee'],
    zip_safe=False,
    platforms='any',
    install_requires=[
        'blinker',
        'Flask-Sqlalchemy',
        'Whoosh'
    ],
    tests_require=[
        'nose'
    ],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ]
)
