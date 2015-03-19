###!/usr/bin/env python

"""
distutils/setuptools install script.
"""

#import botocore

from codecs import open
from setuptools import setup


packages = [
    'yieldfrom',
    'yieldfrom.botocore',
]

requires = ['jmespath==0.6.1', 'python-dateutil>=2.1,<3.0.0',
            'yieldfrom.http.client<0.2.0', 'yieldfrom.urllib3<0.2.0',
            'yieldfrom.requests<0.2.0', 'setuptools']

with open('README.rst', 'r', 'utf-8') as f:
    readme = f.read()
with open('HISTORY.rst', 'r', 'utf-8') as f:
    history = f.read()
with open('license.txt', 'r', 'utf-8') as f:
    license = f.read()

setup(
    name='yieldfrom.botocore',
    version='0.1.3',

    description='asyncio port of botocore, the low-level, data-driven core of boto 3.',
    long_description=open('README.rst', 'r', 'utf-8').read(),

    author='Mitch Garnaatt',
    author_email='garnaat@amazon.com',
    maintainer='David Keeney',
    maintainer_email='dkeeney@rdbhost.com',

    url='https://github.com/rdbhost/yieldfromBotocore',

    packages=packages,
    package_data={'': ['LICENSE', 'NOTICE'],
                  'yieldfrom.botocore': ['data/*.json', 'data/aws/*.json']},
                  #'yieldfrom': ['data/*.json', 'data/aws/*.json']},

    package_dir={'yieldfrom': 'yieldfrom'},
    include_package_data=True,
    namespace_packages=['yieldfrom'],
    install_requires=requires,

    license=license,
    zip_safe=False,
    classifiers=(
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
    ),
)
