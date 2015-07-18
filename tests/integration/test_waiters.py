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
import random
import unittest
import asyncio
import sys, os
import logging

from nose.plugins.attrib import attr

import yieldfrom.botocore.session
from yieldfrom.botocore.client import ClientError

sys.path.append('..')
from asyncio_test_utils import async_test

# This is the same test as above, except using the client interface.
@attr('slow')
class TestWaiterForDynamoDB(unittest.TestCase):

    @asyncio.coroutine
    def set_up(self):
        self.session = yieldfrom.botocore.session.get_session()
        self.client = yield from self.session.create_client('dynamodb', 'us-west-2')

    @async_test
    def test_create_table_and_wait(self):
        table_name = 'botocoretestddb-%s' % random.randint(1, 10000)
        yield from self.client.create_table(
            TableName=table_name,
            ProvisionedThroughput={"ReadCapacityUnits": 5,
                                   "WriteCapacityUnits": 5},
            KeySchema=[{"AttributeName": "foo", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "foo",
                                   "AttributeType": "S"}])
        self.addCleanup(self.client.delete_table, TableName=table_name)
        waiter = self.client.get_waiter('table_exists')
        yield from waiter.wait(TableName=table_name)
        parsed = yield from self.client.describe_table(TableName=table_name)
        self.assertEqual(parsed['Table']['TableStatus'], 'ACTIVE')


class TestCanGetWaitersThroughClientInterface(unittest.TestCase):

    @async_test
    def test_get_ses_waiter(self):
        # We're checking this because ses is not the endpoint prefix
        # for the service, it's email.  We want to make sure this does
        # not affect the lookup process.
        session = yieldfrom.botocore.session.get_session()
        client = yield from session.create_client('ses', 'us-east-1')
        # If we have at least one waiter in the list, we know that we have
        # actually loaded the waiters and this test has passed.
        self.assertTrue(len(client.waiter_names) > 0)
