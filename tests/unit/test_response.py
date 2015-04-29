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
import unittest
import datetime
import asyncio
import sys, os

from dateutil.tz import tzutc

import yieldfrom.botocore
from yieldfrom.botocore import response
from yieldfrom.botocore.exceptions import IncompleteReadError
from yieldfrom.requests.models import Response, Request

sys.path.append('..')
from asyncio_test_utils import async_test, future_wrapped

os.environ['PYTHONASYNCIODEBUG'] = '1'
import logging
logging.basicConfig(level=logging.DEBUG)


XMLBODY1 = (b'<?xml version="1.0" encoding="UTF-8"?><Error>'
            b'<Code>AccessDenied</Code>'
            b'<Message>Access Denied</Message>'
            b'<RequestId>XXXXXXXXXXXXXXXX</RequestId>'
            b'<HostId>AAAAAAAAAAAAAAAAAAA</HostId>'
            b'</Error>')

XMLBODY2 = (b'<?xml version="1.0" encoding="UTF-8"?>'
            b'<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">'
            b'<Name>mybucket</Name><Prefix></Prefix><Marker></Marker>'
            b'<MaxKeys>1000</MaxKeys><IsTruncated>false</IsTruncated>'
            b'<Contents><Key>test.png</Key><LastModified>2014-03-01T17:06:40.000Z</LastModified>'
            b'<ETag>&quot;00000000000000000000000000000000&quot;</ETag><Size>6702</Size>'
            b'<Owner><ID>AAAAAAAAAAAAAAAAAAA</ID>'
            b'<DisplayName>dummy</DisplayName></Owner>'
            b'<StorageClass>STANDARD</StorageClass></Contents></ListBucketResult>')


def TestReader(data):
    r = asyncio.StreamReader()
    r.feed_data(data)
    r.feed_eof()
    return r

class TestStreamWrapper(unittest.TestCase):

    @async_test
    def test_streaming_wrapper_validates_content_length(self):
        #body = io.BytesIO(b'1234567890')
        body = TestReader(b'1234567890')
        stream = response.StreamingBody(body, content_length=10)
        self.assertEqual((yield from stream.read()), b'1234567890')

    @async_test
    def test_streaming_body_with_invalid_length(self):
        body = TestReader(b'123456789')
        stream = response.StreamingBody(body, content_length=10)
        with self.assertRaises(IncompleteReadError):
            self.assertEqual((yield from stream.read(9)), b'123456789')
            # The next read will have nothing returned and raise
            # an IncompleteReadError because we were expectd 10 bytes, not 9.
            yield from stream.read()

    @async_test
    def test_streaming_body_with_single_read(self):
        body = TestReader(b'123456789')
        stream = response.StreamingBody(body, content_length=10)
        with self.assertRaises(IncompleteReadError):
            yield from stream.read()

class TestGetResponse(unittest.TestCase):
    maxDiff = None

    @async_test
    def test_get_response_streaming_ok(self):
        http_response = Response()
        http_response.headers = {
            'content-type': 'image/png',
            'server': 'AmazonS3',
            'AcceptRanges': 'bytes',
            'transfer-encoding': 'chunked',
            'ETag': '"00000000000000000000000000000000"',
        }
        http_response._content_consumed = True
        http_response._content = b'\x89PNG\r\n\x1a\n\x00\x00'

        http_response.status_code = 200
        http_response.reason = 'OK'

        session = yieldfrom.botocore.session.get_session()
        s3 = yield from session.get_service('s3')
        operation = s3.get_operation('GetObject')

        res = yield from response.get_response(operation.model, http_response)
        self.assertTrue(isinstance(res[1]['Body'], response.StreamingBody))
        self.assertEqual(res[1]['ETag'],
                         '"00000000000000000000000000000000"')

    @async_test
    def test_get_response_streaming_ng(self):
        http_response = Response()
        http_response.headers = {
            'content-type': 'application/xml',
            'date': 'Sat, 08 Mar 2014 12:05:44 GMT',
            'server': 'AmazonS3',
            'transfer-encoding': 'chunked',
            'x-amz-id-2': 'AAAAAAAAAAAAAAAAAAA',
            'x-amz-request-id': 'XXXXXXXXXXXXXXXX'}
        http_response._content = XMLBODY1
        http_response._content_consumed = True
        http_response.status_code = 403
        http_response.reason = 'Forbidden'

        session = yieldfrom.botocore.session.get_session()
        s3 = yield from session.get_service('s3')
        operation = s3.get_operation('GetObject') # streaming operation

        self.assertEqual(
            (yield from response.get_response(operation.model, http_response))[1],
            {'Error': {'Message': 'Access Denied',
                       'Code': 'AccessDenied',},
             'ResponseMetadata': {'HostId': 'AAAAAAAAAAAAAAAAAAA',
                                  'RequestId': 'XXXXXXXXXXXXXXXX',
                                  'HTTPStatusCode': 403},
             }
            )

    @async_test
    def test_get_response_nonstreaming_ok(self):
        http_response = Response()
        http_response.headers = {
            'content-type': 'application/xml',
            'date': 'Sun, 09 Mar 2014 02:55:43 GMT',
            'server': 'AmazonS3',
            'transfer-encoding': 'chunked',
            'x-amz-id-2': 'AAAAAAAAAAAAAAAAAAA',
            'x-amz-request-id': 'XXXXXXXXXXXXXXXX'}
        http_response._content = XMLBODY1
        http_response._content_consumed = True
        http_response.status_code = 403
        http_response.reason = 'Forbidden'
        http_response.request = Request()

        session = yieldfrom.botocore.session.get_session()
        s3 = yield from session.get_service('s3')
        operation = s3.get_operation('ListObjects') # non-streaming operation

        self.assertEqual(
            (yield from response.get_response(operation.model, http_response))[1],
            { 'ResponseMetadata': {'RequestId': 'XXXXXXXXXXXXXXXX',
                                   'HostId': 'AAAAAAAAAAAAAAAAAAA',
                                   'HTTPStatusCode': 403},
              'Error': {'Message': 'Access Denied',
                        'Code': 'AccessDenied',}
              }
            )

    @async_test
    def test_get_response_nonstreaming_ng(self):
        http_response = Response()
        http_response.headers = {
            'content-type': 'application/xml',
            'date': 'Sat, 08 Mar 2014 12:05:44 GMT',
            'server': 'AmazonS3',
            'transfer-encoding': 'chunked',
            'x-amz-id-2': 'AAAAAAAAAAAAAAAAAAA',
            'x-amz-request-id': 'XXXXXXXXXXXXXXXX'}
        http_response._content = XMLBODY2
        http_response._content_consumed = True
        http_response.status_code = 200
        http_response.reason = 'ok'
        http_response.request = Request()

        session = yieldfrom.botocore.session.get_session()
        s3 = yield from session.get_service('s3')
        operation = s3.get_operation('ListObjects')  # non-streaming operation

        body = yield from response.get_response(operation.model, http_response)

        self.assertEqual(body[1],
            {u'Contents': [{u'ETag': '"00000000000000000000000000000000"',
                            u'Key': 'test.png',
                            u'LastModified': datetime.datetime(2014, 3, 1, 17, 6, 40, tzinfo=tzutc()),
                            u'Owner': {u'DisplayName': 'dummy',
                                       u'ID': 'AAAAAAAAAAAAAAAAAAA'},
                            u'Size': 6702,
                            u'StorageClass': 'STANDARD'}],
             u'IsTruncated': False,
             u'Marker': "",
             u'MaxKeys': 1000,
             u'Name': 'mybucket',
             u'Prefix': "",
             'ResponseMetadata': {
                 'RequestId': 'XXXXXXXXXXXXXXXX',
                 'HostId': 'AAAAAAAAAAAAAAAAAAA',
                 'HTTPStatusCode': 200,
             }}
        )
