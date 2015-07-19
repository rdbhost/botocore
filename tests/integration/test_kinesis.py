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

import time
from tests import unittest, random_chars
import random
import unittest

import asyncio
import sys
sys.path.append('..')
from asyncio_test_utils import async_test

import yieldfrom.botocore.session
from nose.plugins.attrib import attr



class TestKinesisListStreams(unittest.TestCase):

    REGION = 'us-east-1'

    @asyncio.coroutine
    def set_up(self):

        self.session = yieldfrom.botocore.session.get_session()
        self.stream_name = 'botocore-test-%s' % random_chars(10)
        client = yield from self.session.create_client('kinesis', self.REGION)
        yield from client.create_stream(StreamName=self.stream_name,
                             ShardCount=1)
        waiter = client.get_waiter('stream_exists')
        yield from waiter.wait(StreamName=self.stream_name)
        self.client = yield from self.session.create_client('kinesis', self.REGION)

    #@classmethod
    #def tearDownClass(self):

    @asyncio.coroutine
    def tear_down(self):
        client = yield from self.session.create_client('kinesis', self.REGION)
        yield from client.delete_stream(StreamName=self.stream_name)

    @async_test
    def test_list_streams(self):
        parsed = yield from self.client.list_streams()
        self.assertIn('StreamNames', parsed)

    @async_test
    @attr('slow')
    def test_can_put_stream_blob(self):

        yield from self.client.put_record(StreamName=self.stream_name, PartitionKey='foo', Data='foobar')
        # Give it a few seconds for the record to get into the stream.
        time.sleep(10)

        stream = yield from self.client.describe_stream(StreamName=self.stream_name)
        shard = stream['StreamDescription']['Shards'][0]
        shard_iterator = yield from self.client.get_shard_iterator(
            StreamName=self.stream_name, ShardId=shard['ShardId'],
            ShardIteratorType='TRIM_HORIZON')

        records = yield from self.client.get_records(
            ShardIterator=shard_iterator['ShardIterator'])
        self.assertTrue(len(records['Records']) > 0)
        self.assertEqual(records['Records'][0]['Data'], b'foobar')

    @async_test
    @attr('slow')
    def test_can_put_records_single_blob(self):
        yield from self.client.put_records(
            StreamName=self.stream_name,
            Records=[{
                'Data': 'foobar',
                'PartitionKey': 'foo'
            }]
        )
        # Give it a few seconds for the record to get into the stream.
        time.sleep(10)

        stream = yield from self.client.describe_stream(StreamName=self.stream_name)
        shard = stream['StreamDescription']['Shards'][0]
        shard_iterator = yield from self.client.get_shard_iterator(
            StreamName=self.stream_name, ShardId=shard['ShardId'],
            ShardIteratorType='TRIM_HORIZON')

        records = yield from self.client.get_records(
            ShardIterator=shard_iterator['ShardIterator'])
        self.assertTrue(len(records['Records']) > 0)
        self.assertEqual(records['Records'][0]['Data'], b'foobar')

    @async_test
    @attr('slow')
    def test_can_put_records_multiple_blob(self):
        _t = yield from self.client.put_records(
            StreamName=self.stream_name,
            Records=[{
                'Data': 'foobar',
                'PartitionKey': 'foo'
            }, {
                'Data': 'barfoo',
                'PartitionKey': 'foo'
            }]
        )
        # Give it a few seconds for the record to get into the stream.
        yield from asyncio.sleep(10)

        stream = yield from self.client.describe_stream(StreamName=self.stream_name)
        shard = stream['StreamDescription']['Shards'][0]
        shard_iterator = yield from self.client.get_shard_iterator(
            StreamName=self.stream_name, ShardId=shard['ShardId'],
            ShardIteratorType='TRIM_HORIZON')

        records = yield from self.client.get_records(
            ShardIterator=shard_iterator['ShardIterator'])
        self.assertTrue(len(records['Records']) == 2)
        # Verify that both made it through.
        record_data = [r['Data'] for r in records['Records']]
        self.assertEqual(sorted([b'foobar', b'barfoo']), sorted(record_data))


if __name__ == '__main__':
    unittest.main()
