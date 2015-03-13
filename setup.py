#!/usr/bin/env python

"""
distutils/setuptools install script.
"""

import botocore

from setuptools import setup, find_packages

requires = ['jmespath==0.6.1',
            'python-dateutil>=2.1,<3.0.0']

packages = [
    'yieldfrom',
    'yieldfrom.botocore',
]

requires = ['jmespath==0.6.1', 'python-dateutil>=2.1,<3.0.0',
            'yieldfrom.http.client<0.2.0', 'yieldfrom.urllib3<0.2.0', 'setuptools']

with open('README.rst', 'r', 'utf-8') as f:
    readme = f.read()
with open('HISTORY.rst', 'r', 'utf-8') as f:
    history = f.read()

setup(
    name='yieldfrom.botocore',
    version='0.1.2',
    description='asyncio port of botocore, the low-level, data-driven core of boto 3.',
    long_description=open('README.rst').read(),
    author='Mitch Garnaatt',
    author_email='garnaat@amazon.com',
    maintainer='David Keeney',
    author_email='dkeeney@rdbhost.com',
    url='https://github.com/rdbhost/yieldfromBotocore',
    scripts=[],
    packages=packages,
    package_data={'yieldfrom.botocore': ['data/*.json', 'data/aws/*.json']},
    package_dir={'yieldfrom': 'yieldfrom'},
    include_package_data=True,
    namespace_packages=['yieldfrom'],
    install_requires=requires,
    license=open("LICENSE.txt").read(),
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
