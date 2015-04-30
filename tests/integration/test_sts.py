# Copyright 2015 Amazon.com, Inc. or its affiliates. All Rights Reserved.
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
import sys, os
import unittest
import asyncio
import yieldfrom.botocore.session
from yieldfrom.botocore.exceptions import ClientError

sys.path.append('..')
from asyncio_test_utils import async_test


class TestSTS(unittest.TestCase):

    @asyncio.coroutine
    def set_up(self):

        self.session = yieldfrom.botocore.session.get_session()
        credentials = yield from self.session.get_credentials()
        if credentials.token is not None:
            self.skipTest('STS tests require long-term credentials')

    @async_test
    def test_regionalized_endpoints(self):
        sts = yield from self.session.create_client('sts', region_name='ap-southeast-1')
        response = yield from sts.get_session_token()
        # Do not want to be revealing any temporary keys if the assertion fails
        self.assertIn('Credentials', response.keys())

        # Since we have to activate STS regionalization, we will test
        # that you can send an STS request to a regionalized endpoint
        # by making a call with the explicitly wrong region name
        sts = yield from self.session.create_client(
            'sts', region_name='ap-southeast-1',
            endpoint_url='https://sts.us-west-2.amazonaws.com')
        # Signing error will be thrown with the incorrect region name included.
        with self.assertRaisesRegexp(ClientError, 'ap-southeast-1') as e:
            yield from sts.get_session_token()

    @async_test
    def test_regionalized_endpoints_operation(self):
        # TODO: Remove this test once service/operation objects are removed.
        # This was added here because the CLI uses operation objects currently
        # but this type of integration testing (non customized) should
        # be done at the botocore level.
        sts = yield from self.session.get_service('sts')

        endpoint = sts.get_endpoint(region_name='ap-southeast-1')
        operation = sts.get_operation('GetSessionToken')
        http, response = yield from operation.call(endpoint)
        # Do not want to be revealing any temporary keys if the assertion fails
        self.assertIn('Credentials', response.keys())

        endpoint = sts.get_endpoint(
            region_name='ap-southeast-1',
            endpoint_url='https://sts.us-west-2.amazonaws.com')
        operation = sts.get_operation('GetSessionToken')
        http, response = yield from operation.call(endpoint)
        self.assertIn('Error', response)
        error = response['Error']
        self.assertEqual('SignatureDoesNotMatch', error['Code'])
        self.assertIn('ap-southeast-1', error['Message'])
