#!/usr/bin/env python

"""
distutils/setuptools install script.
"""

import botocore

from setuptools import setup, find_packages

requires = ['jmespath==0.6.1',
            'python-dateutil>=2.1,<3.0.0']

setup(
    name='botocore',
    version=botocore.__version__,
    description='Low-level, data-driven core of boto 3.',
    long_description=open('README.rst').read(),
    author='David Keeney',
    author_email='dkeeney@travelbyroad.net',
    url='https://github.com/rdbhost/botocore',
    scripts=[],
    packages=find_packages(exclude=['tests*']),
    package_data={'botocore': ['data/*.json', 'data/aws/*.json']},
    package_dir={'botocore': 'botocore'},
    include_package_data=True,
    install_requires=requires,
    license=open("LICENSE.txt").read(),
    classifiers=(
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'Natural Language :: English',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
    ),
)
