# Copyright 2014 Amazon.com, Inc. or its affiliates. All Rights Reserved.
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
#import itertools
import asyncio
import sys
sys.path.append('..')
from asyncio_test_utils import async_test, future_wrapped, pump_iter

import yieldfrom.botocore.session

@asyncio.coroutine
def pump_paginator(pg):
    t = []
    p = yield from pg.next()
    while p:
        t.append(p)
        p = yield from pg.next()
    return t


class TestRDSPagination(unittest.TestCase):
    @asyncio.coroutine
    def set_up(self):
        self.session = yieldfrom.botocore.session.get_session()
        self.client = yield from self.session.create_client('route53', 'us-west-2')

    @async_test
    def test_paginate_with_max_items(self):
        # Route53 has a string type for MaxItems.  We need to ensure that this
        # still works without any issues.
        paginator = self.client.get_paginator('list_hosted_zones')
        results = yield from pump_paginator(paginator.paginate(max_items='1'))
        self.assertTrue(len(results) >= 0)


if __name__ == '__main__':
    unittest.main()
