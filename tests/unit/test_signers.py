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

import mock
import asyncio
import functools

import botocore
import botocore.auth

from botocore.credentials import Credentials
from botocore.exceptions import NoRegionError, UnknownSignatureVersionError
from botocore.signers import RequestSigner

from tests import unittest

def async_test(f):

    testLoop = asyncio.get_event_loop()

    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        coro = asyncio.coroutine(f)
        future = coro(*args, **kwargs)
        testLoop.run_until_complete(future)
    return wrapper

async_test.__test__ = False # not a test


class TestSigner(unittest.TestCase):
    def setUp(self):
        self.credentials = Credentials('key', 'secret')
        self.emitter = mock.Mock()
        self.emitter.emit_until_response.return_value = (None, None)
        self.signer = RequestSigner(
            'service_name', 'region_name', 'signing_name',
            'v4', self.credentials, self.emitter)

    @async_test
    def test_region_required_for_sigv4(self):
        self.signer = RequestSigner(
            'service_name', None, 'signing_name', 'v4', self.credentials,
            self.emitter)
        _f = asyncio.Future()
        _f.set_result( (None, None))
        self.emitter.emit_until_response.return_value = _f
        _g = asyncio.Future()
        _g.set_result((None,))
        self.emitter.emit.return_value = _g

        with self.assertRaises(NoRegionError):
            yield from self.signer.sign('operation_name', mock.Mock())

    def test_get_auth(self):
        auth_cls = mock.Mock()
        with mock.patch.dict(botocore.auth.AUTH_TYPE_MAPS,
                             {'v4': auth_cls}):
            auth = self.signer.get_auth('service_name', 'region_name')

            self.assertEqual(auth, auth_cls.return_value)
            auth_cls.assert_called_with(
                credentials=self.credentials, service_name='service_name',
                region_name='region_name')

    def test_get_auth_cached(self):
        auth_cls = mock.Mock()
        with mock.patch.dict(botocore.auth.AUTH_TYPE_MAPS,
                             {'v4': auth_cls}):
            auth1 = self.signer.get_auth('service_name', 'region_name')
            auth2 = self.signer.get_auth('service_name', 'region_name')

        self.assertEqual(auth1, auth2)

    def test_get_auth_signature_override(self):
        auth_cls = mock.Mock()
        with mock.patch.dict(botocore.auth.AUTH_TYPE_MAPS,
                             {'v4-custom': auth_cls}):
            auth = self.signer.get_auth(
                'service_name', 'region_name', signature_version='v4-custom')

            self.assertEqual(auth, auth_cls.return_value)
            auth_cls.assert_called_with(
                credentials=self.credentials, service_name='service_name',
                region_name='region_name')

    def test_get_auth_bad_override(self):
        with self.assertRaises(UnknownSignatureVersionError):
            self.signer.get_auth('service_name', 'region_name',
                                 signature_version='bad')

    @async_test
    def test_emits_choose_signer(self):
        request = mock.Mock()

        _f = asyncio.Future()
        _f.set_result((None, 'v4'))
        self.emitter.emit_until_response.return_value = _f
        _g = asyncio.Future()
        _g.set_result((None,))
        self.emitter.emit.return_value = _g

        with mock.patch.dict(botocore.auth.AUTH_TYPE_MAPS,
                             {'v4': mock.Mock()}):
            yield from self.signer.sign('operation_name', request)

        self.emitter.emit_until_response.assert_called_with(
            'choose-signer.service_name.operation_name',
            signing_name='signing_name', region_name='region_name',
            signature_version='v4')

    @async_test
    def test_choose_signer_override(self):
        request = mock.Mock()
        auth = mock.Mock()
        auth.REQUIRES_REGION = False
        _f = asyncio.Future()
        _f.set_result( (None, 'custom'))
        self.emitter.emit_until_response.return_value = _f
        _g = asyncio.Future()
        _g.set_result((None,))
        self.emitter.emit.return_value = _g

        with mock.patch.dict(botocore.auth.AUTH_TYPE_MAPS,
                             {'custom': auth}):
            yield from self.signer.sign('operation_name', request)

        auth.assert_called_with(credentials=self.credentials)
        auth.return_value.add_auth.assert_called_with(request=request)

    @asyncio.coroutine
    def test_emits_before_sign(self):
        request = mock.Mock()

        _f = asyncio.Future()
        _f.set_result( (None, 'custom'))
        self.emitter.emit_until_response.return_value = _f
        _g = asyncio.Future()
        _g.set_result((None,))
        self.emitter.emit.return_value = _g

        with mock.patch.dict(botocore.auth.AUTH_TYPE_MAPS,
                             {'v4': mock.Mock()}):
            yield from self.signer.sign('operation_name', request)

        self.emitter.emit.assert_called_with(
            'before-sign.service_name.operation_name',
            request=mock.ANY, signing_name='signing_name',
            region_name='region_name', signature_version='v4',
            request_signer=self.signer)

    def test_disable_signing(self):
        # Returning botocore.UNSIGNED from choose-signer disables signing!
        request = mock.Mock()
        auth = mock.Mock()
        _g = asyncio.Future()
        _g.set_result((None,))
        self.emitter.emit.return_value = _g
        self.emitter.emit_until_response.return_value = (None,
                                                         botocore.UNSIGNED)

        with mock.patch.dict(botocore.auth.AUTH_TYPE_MAPS,
                             {'v4': auth}):
            yield from self.signer.sign('operation_name', request)

        auth.assert_not_called()
