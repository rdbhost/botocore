#!/usr/bin/env python
# Copyright (c) 2012-2013 Mitch Garnaat http://garnaat.org/
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


#
#  This file altered by David Keeney 2015, as part of conversion to
# asyncio.
#
import asyncio
import sys, os
from mock import patch, Mock

import yieldfrom.botocore.session
from yieldfrom.botocore import auth, credentials
from yieldfrom.botocore.exceptions import ServiceNotInRegionError
# from yieldfrom.botocore.handlers import fix_s3_host

sys.path.extend(['..', '../..'])
from tests import BaseSessionTest
from asyncio_test_utils import async_test, future_wrapped

os.environ['PYTHONASYNCIODEBUG'] = '1'
import logging
logging.basicConfig(level=logging.DEBUG)


class TestS3Addressing(BaseSessionTest):

    @asyncio.coroutine
    def set_up(self):
        super(TestS3Addressing, self).setUp()
        self.region_name = 'us-east-1'
        self.signature_version = 's3'

        self.mock_response = Mock()
        self.mock_response.content = ''
        self.mock_response.headers = {}
        self.mock_response.status_code = 200

    @asyncio.coroutine
    def get_prepared_request(self, operation, params, force_hmacv1=False):
        if force_hmacv1:
            self.session.register('choose-signer', self.enable_hmacv1)
        with patch('yieldfrom.botocore.endpoint.PreserveAuthSession') as \
                mock_http_session:
            mock_send = mock_http_session.return_value.send
            mock_send.return_value = future_wrapped(self.mock_response)
            client = yield from self.session.create_client('s3', self.region_name)
            _ = yield from getattr(client, operation)(**params)
            # Return the request that was sent over the wire.
            return mock_send.call_args[0][0]

    def enable_hmacv1(self, **kwargs):
        return 's3'

    @async_test
    def test_list_objects_dns_name(self):
        params = {'Bucket': 'safename'}
        prepared_request = yield from self.get_prepared_request('list_objects', params,
                                                     force_hmacv1=True)
        self.assertEqual(prepared_request.url,
                         'https://safename.s3.amazonaws.com/')

    @async_test
    def test_list_objects_non_dns_name(self):
        params = {'Bucket': 'un_safe_name'}
        prepared_request = yield from self.get_prepared_request('list_objects', params,
                                                     force_hmacv1=True)
        self.assertEqual(prepared_request.url,
                         'https://s3.amazonaws.com/un_safe_name')

    @async_test
    def test_list_objects_dns_name_non_classic(self):
        self.region_name = 'us-west-2'
        params = {'Bucket': 'safename'}
        prepared_request = yield from self.get_prepared_request('list_objects', params,
                                                     force_hmacv1=True)
        self.assertEqual(prepared_request.url,
                         'https://safename.s3.amazonaws.com/')

    @async_test
    def test_list_objects_unicode_query_string_eu_central_1(self):
        self.region_name = 'eu-central-1'
        params = {'Bucket': 'safename', 'Marker': u'\xe4\xf6\xfc-01.txt'}
        prepared_request = yield from self.get_prepared_request('list_objects', params)
        self.assertEqual(
            prepared_request.url,
            ('https://s3.eu-central-1.amazonaws.com/safename'
             '?marker=%C3%A4%C3%B6%C3%BC-01.txt')
        )

    @async_test
    def test_list_objects_in_restricted_regions(self):
        self.region_name = 'us-gov-west-1'
        params = {'Bucket': 'safename'}
        prepared_request = yield from self.get_prepared_request('list_objects', params)
        # Note how we keep the region specific endpoint here.
        self.assertEqual(prepared_request.url,
                         'https://s3-us-gov-west-1.amazonaws.com/safename')

    @async_test
    def test_list_objects_in_fips(self):
        self.region_name = 'fips-us-gov-west-1'
        params = {'Bucket': 'safename'}
        prepared_request = yield from self.get_prepared_request('list_objects', params)
        # Note how we keep the region specific endpoint here.
        self.assertEqual(
            prepared_request.url,
            'https://s3-fips-us-gov-west-1.amazonaws.com/safename')

    @async_test
    def test_list_objects_non_dns_name_non_classic(self):
        self.region_name = 'us-west-2'
        params = {'Bucket': 'un_safe_name'}
        prepared_request = yield from self.get_prepared_request('list_objects', params)
        self.assertEqual(prepared_request.url,
                         'https://s3-us-west-2.amazonaws.com/un_safe_name')

    @async_test
    def test_put_object_dns_name_non_classic(self):
        self.region_name = 'us-west-2'
        file_path = os.path.join(os.path.dirname(__file__),
                                 'put_object_data')
        with open(file_path, 'rb') as fp:
            params = {
                'Bucket': 'my.valid.name',
                'Key': 'mykeyname',
                'Body': fp,
                'ACL': 'public-read',
                'ContentLanguage': 'piglatin',
                'ContentType': 'text/plain'
            }
            prepared_request = yield from self.get_prepared_request('put_object', params)
            self.assertEqual(
                prepared_request.url,
                'https://s3-us-west-2.amazonaws.com/my.valid.name/mykeyname')

    @async_test
    def test_put_object_dns_name_classic(self):
        self.region_name = 'us-east-1'
        file_path = os.path.join(os.path.dirname(__file__),
                                 'put_object_data')
        with open(file_path, 'rb') as fp:
            params = {
                'Bucket': 'my.valid.name',
                'Key': 'mykeyname',
                'Body': fp,
                'ACL': 'public-read',
                'ContentLanguage': 'piglatin',
                'ContentType': 'text/plain'
            }
            prepared_request = yield from self.get_prepared_request('put_object', params)
            self.assertEqual(
                prepared_request.url,
                'https://s3.amazonaws.com/my.valid.name/mykeyname')

    @async_test
    def test_put_object_dns_name_single_letter_non_classic(self):
        self.region_name = 'us-west-2'
        file_path = os.path.join(os.path.dirname(__file__),
                                 'put_object_data')
        with open(file_path, 'rb') as fp:
            params = {
                'Bucket': 'a.valid.name',
                'Key': 'mykeyname',
                'Body': fp,
                'ACL': 'public-read',
                'ContentLanguage': 'piglatin',
                'ContentType': 'text/plain'
            }
            prepared_request = yield from self.get_prepared_request('put_object', params)
            self.assertEqual(
                prepared_request.url,
                'https://s3-us-west-2.amazonaws.com/a.valid.name/mykeyname')

    @async_test
    def test_get_object_non_dns_name_non_classic(self):
        self.region_name = 'us-west-2'
        params = {
            'Bucket': 'AnInvalidName',
            'Key': 'mykeyname'
        }
        prepared_request = yield from self.get_prepared_request('get_object', params)
        self.assertEqual(
            prepared_request.url,
            'https://s3-us-west-2.amazonaws.com/AnInvalidName/mykeyname')

    @async_test
    def test_get_object_non_dns_name_classic(self):
        self.region_name = 'us-east-1'
        params = {
            'Bucket': 'AnInvalidName',
            'Key': 'mykeyname'
        }
        prepared_request = yield from self.get_prepared_request('get_object', params)
        self.assertEqual(prepared_request.url,
                         'https://s3.amazonaws.com/AnInvalidName/mykeyname')

    @async_test
    def test_get_object_ip_address_name_non_classic(self):
        self.region_name = 'us-west-2'
        params = {
            'Bucket': '192.168.5.4',
            'Key': 'mykeyname'}
        prepared_request = yield from self.get_prepared_request('get_object', params)
        self.assertEqual(
            prepared_request.url,
            'https://s3-us-west-2.amazonaws.com/192.168.5.4/mykeyname')

    @async_test
    def test_get_object_almost_an_ip_address_name_non_classic(self):
        self.region_name = 'us-west-2'
        params = {
            'Bucket': '192.168.5.256',
            'Key': 'mykeyname'}
        prepared_request = yield from self.get_prepared_request('get_object', params)
        self.assertEqual(
            prepared_request.url,
            'https://s3-us-west-2.amazonaws.com/192.168.5.256/mykeyname')

    def test_invalid_endpoint_raises_exception(self):
        with self.assertRaisesRegexp(ValueError, 'Invalid endpoint'):
            yield from self.session.create_client('s3', 'Invalid region')

    @async_test
    def test_non_existent_region(self):
        # If I ask for a region that does not
        # exist on a global endpoint, such as:
        client = yield from self.session.create_client('s3', 'REGION-DOES-NOT-EXIST')
        # Then the default endpoint heuristic will apply and we'll
        # get the region name as specified.
        self.assertEqual(client.meta.region_name, 'REGION-DOES-NOT-EXIST')
        # Why not fixed this?  Well backwards compatability for one thing.
        # The other reason is because it was intended to accomodate this
        # use case.  Let's say I have us-west-2 set as my default region,
        # possibly through an env var or config variable.  Well, by default,
        # we'd make a call like:
        client = yield from self.session.create_client('iam', 'us-west-2')
        # Instead of giving the user an error, we should instead give
        # them the global endpoint.
        self.assertEqual(client.meta.region_name, 'us-east-1')
        # But if they request an endpoint that we *do* know about, we use
        # that specific endpoint.
        client = yield from self.session.create_client('iam', 'us-gov-west-1')
        self.assertEqual(
            client.meta.region_name,
            'us-gov-west-1')
