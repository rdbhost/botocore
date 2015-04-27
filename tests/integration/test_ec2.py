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
from nose.plugins.attrib import attr



class TestEC2(unittest.TestCase):

    def setUp(self):
        self.session = yieldfrom.botocore.session.get_session()
        self.client = self.session.create_client(
            'ec2', region_name='us-west-2')

    @async_test
    def test_can_make_request(self):
        # Basic smoke test to ensure we can talk to ec2.
        result = self.client.describe_availability_zones()
        assert result
        zones = list(sorted(a['ZoneName'] for a in result['AvailabilityZones']))
        self.assertEqual(zones, ['us-west-2a', 'us-west-2b', 'us-west-2c'])


class TestEC2Pagination(unittest.TestCase):

    @asyncio.coroutine
    def set_up(self):
        self.session = yieldfrom.botocore.session.get_session()
        self.client = self.session.create_client(
            'ec2', region_name='us-west-2')

    @async_test
    def test_can_paginate(self):
        # Using an operation that we know will paginate.
        paginator = self.client.get_paginator(
            'describe_reserved_instances_offerings')
        pages = paginator.paginate()
        genList = yield from pump_iter(pages)
        results = list(itertools.islice(genList, 0, 3))
        self.assertEqual(len(results), 3)
        self.assertTrue(results[0]['NextToken'] != results[1]['NextToken'])

    @async_test
    def test_can_paginate_with_page_size(self):
        # Using an operation that we know will paginate.
        paginator = self.client.get_paginator(
            'describe_reserved_instances_offerings')
        pages = paginator.paginate(page_size=1)
        genList = yield from pump_iter(pages)
        results = list(itertools.islice(genList, 0, 3))
        self.assertEqual(len(results), 3)
        for parsed in results:
            reserved_inst_offer = parsed['ReservedInstancesOfferings']
            # There should only be one reserved instance offering on each
            # page.
            self.assertEqual(len(reserved_inst_offer), 1)


@attr('slow')
class TestCopySnapshotCustomization(unittest.TestCase):

    @asyncio.coroutine
    def set_up(self):
        # However, all the test fixture setup/cleanup can use
        # the client interface.
        self.client = yield from self.session.create_client('ec2', 'us-west-2')
        self.client_us_east_1 = yield from self.session.create_client(
            'ec2', 'us-east-1')

    @asyncio.coroutine
    def create_volume(self, encrypted=False):
        available_zones = yield from self.client.describe_availability_zones()
        first_zone = available_zones['AvailabilityZones'][0]['ZoneName']
        response = yield from self.client.create_volume(
            Size=1, AvailabilityZone=first_zone, Encrypted=encrypted)
        volume_id = response['VolumeId']
        self.addCleanup(self.client.delete_volume, VolumeId=volume_id)
        yield from self.client.get_waiter('volume_available').wait(VolumeIds=[volume_id])
        return volume_id

    @asyncio.coroutine
    def create_snapshot(self, volume_id):
        response = yield from self.client.create_snapshot(VolumeId=volume_id)
        snapshot_id = response['SnapshotId']
        yield from self.client.get_waiter('snapshot_completed').wait(
            SnapshotIds=[snapshot_id])
        self.addCleanup(self.client.delete_snapshot, SnapshotId=snapshot_id)
        return snapshot_id

    @asyncio.coroutine
    def cleanup_copied_snapshot(self, snapshot_id):
        dest_client = yield from self.session.create_client('ec2', 'us-east-1')
        self.addCleanup(dest_client.delete_snapshot,
                        SnapshotId=snapshot_id)
        yield from dest_client.get_waiter('snapshot_completed').wait(
            SnapshotIds=[snapshot_id])

    @async_test
    def test_can_copy_snapshot(self):
        volume_id = yield from self.create_volume()
        yield from asyncio.sleep(10)
        snapshot_id = yield from self.create_snapshot(volume_id)

        result = yield from self.client_us_east_1.copy_snapshot(
            SourceRegion='us-west-2',
            SourceSnapshotId=snapshot_id)
        self.assertIn('SnapshotId', result)

        # Cleanup code.  We can wait for the snapshot to be complete
        # and then we can delete the snapshot.
        yield from self.cleanup_copied_snapshot(result['SnapshotId'])

    @async_test
    def test_can_copy_encrypted_snapshot(self):
        # Note that we're creating an encrypted volume here.
        volume_id = yield from self.create_volume(encrypted=True)
        yield from asyncio.sleep(10)
        snapshot_id = yield from self.create_snapshot(volume_id)

        result = yield from self.client_us_east_1.copy_snapshot(
            SourceRegion='us-west-2',
            SourceSnapshotId=snapshot_id)
        self.assertIn('SnapshotId', result)
        yield from self.cleanup_copied_snapshot(result['SnapshotId'])


if __name__ == '__main__':
    unittest.main()
