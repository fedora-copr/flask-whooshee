#!/usr/bin/env python
# -*- coding: utf-8 -*-

try:
    from setuptools import setup
except:
    from distutils.core import setup


setup(
    name='flask-whooshee',
    version='0.3.1',
    description='Flask - SQLAlchemy - Whoosh integration',
    long_description=''.join(open('README.md').readlines()),
    keywords='flask, sqlalchemy, whoosh',
    author='Bohuslav "Slavek" Kabrda',
    author_email='bkabrda@redhat.com',
    url='https://github.com/bkabrda/flask-whooshee',
    license='BSD',
    py_modules=['flask_whooshee', ],
    install_requires=open('requirements.txt').read().splitlines(),
    setup_requires=[],
    classifiers=['Development Status :: 4 - Beta',
                 'Environment :: Web Environment',
                 'Intended Audience :: Developers',
                 'License :: OSI Approved :: BSD License',
                 'Operating System :: OS Independent',
                 'Programming Language :: Python',
                 'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
                 'Topic :: Software Development :: Libraries :: Python Modules'
                 ]
)
