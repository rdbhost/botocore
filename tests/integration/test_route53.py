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


class TestRoute53Pagination(unittest.TestCase):

    @asyncio.coroutine
    def set_up(self):
        self.session = yieldfrom.botocore.session.get_session()
        self.service = yield from self.session.get_service('route53')
        self.endpoint = self.service.get_endpoint('us-west-2')

    @async_test
    def test_paginate_with_max_items(self):
        # Route53 has a string type for MaxItems.  We need to ensure that this
        # still works without any issues.
        operation = self.service.get_operation('ListHostedZones')
        results = yield from pump_iter(operation.paginate(self.endpoint, max_items='1'))
        self.assertTrue(len(results) >= 0)


if __name__ == '__main__':
    unittest.main()
