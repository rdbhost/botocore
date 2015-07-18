# Copyright 2012-2014 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"). You
# may not use this file except in compliance with the License. A copy of
# the License is located at
#
# http://aws.amazon.com/apache2.0/
#
# or in the "license" file accompanying this file. This file is
# distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF
# ANY KIND, either express or implied. See the License for the specific
# language governing permissions and limitations under the License.

# This file altered by David Keeney 2015, as part of conversion to
# asyncio.
#
import os
os.environ['PYTHONASYNCIODEBUG'] = '1'
import logging
logging.basicConfig(level=logging.DEBUG)


import unittest
import itertools
import asyncio
import sys
sys.path.append('..')
from asyncio_test_utils import async_test, future_wrapped, pump_iter

import yieldfrom.botocore.session


class TestRDSPagination(unittest.TestCase):
    @asyncio.coroutine
    def set_up(self):
        self.session = yieldfrom.botocore.session.get_session()
        self.client = yield from self.session.create_client('rds', 'us-west-2')

    @async_test
    def test_can_paginate_reserved_instances(self):
        # Using an operation that we know will paginate.
        paginator = self.client.get_paginator(
            'describe_reserved_db_instances_offerings')
        generator = paginator.paginate()
        genResults = yield from pump_iter(generator)
        results = list(itertools.islice(genResults, 0, 3))
        self.assertEqual(len(results), 3)
        self.assertTrue(results[0]['Marker'] != results[1]['Marker'])

    @async_test
    def test_can_paginate_orderable_db(self):
        paginator = self.client.get_paginator(
            'describe_orderable_db_instance_options')
        generator = paginator.paginate(Engine='mysql')
        genResults = yield from pump_iter(generator)
        results = list(itertools.islice(genResults, 0, 2))
        self.assertEqual(len(results), 2)
        self.assertTrue(results[0].get('Marker') != results[1].get('Marker'))


if __name__ == '__main__':
    unittest.main()
