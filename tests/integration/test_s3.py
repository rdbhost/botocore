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

import os
import sys
import time
import random
from tests import unittest, temporary_file
from collections import defaultdict
import tempfile
import shutil
import threading
import mock
import asyncio
import io
try:
    from itertools import izip_longest as zip_longest
except ImportError:
    from itertools import zip_longest

from yieldfrom.requests import adapters
from yieldfrom.requests.exceptions import ConnectionError
import yieldfrom.botocore.session
import yieldfrom.botocore.auth
import yieldfrom.botocore.credentials
import yieldfrom.requests as requests

#import logging
#logging.basicConfig(level=logging.DEBUG)

sys.path.append('..')
from asyncio_test_utils import async_test


class BaseS3Test(unittest.TestCase):

    @asyncio.coroutine
    def set_up(self):
        self.session = yieldfrom.botocore.session.get_session()
        self.service = yield from self.session.get_service('s3')
        self.region = 'us-east-1'
        self.endpoint = self.service.get_endpoint(self.region)
        self.keys = []

    @asyncio.coroutine
    def create_object(self, key_name, body='foo'):
        self.keys.append(key_name)
        operation = self.service.get_operation('PutObject')
        response = (yield from operation.call(
            self.endpoint, bucket=self.bucket_name, key=key_name,
            body=body))[0]
        self.assertEqual(response.status_code, 200)

    @asyncio.coroutine
    def create_multipart_upload(self, key_name):

        operation = self.service.get_operation('CreateMultipartUpload')
        http_response, parsed = yield from operation.call(self.endpoint,
                                               bucket=self.bucket_name,
                                               key=key_name)
        upload_id = parsed['UploadId']
        self.addCleanup(
            self.service.get_operation('AbortMultipartUpload').call,
            self.endpoint, upload_id=upload_id,
            bucket=self.bucket_name, key=key_name)

    @asyncio.coroutine
    def create_object_catch_exceptions(self, key_name):
        try:
            yield from self.create_object(key_name=key_name)
        except Exception as e:
            self.caught_exceptions.append(e)

    @asyncio.coroutine
    def delete_object(self, key, bucket_name):
        operation = self.service.get_operation('DeleteObject')
        response = yield from operation.call(self.endpoint, bucket=bucket_name,
                                  key=key)
        self.assertEqual(response[0].status_code, 204)

    @asyncio.coroutine
    def delete_bucket(self, bucket_name):
        operation = self.service.get_operation('DeleteBucket')
        response = yield from operation.call(self.endpoint, bucket=bucket_name)
        self.assertEqual(response[0].status_code, 204)

    @asyncio.coroutine
    def assert_num_uploads_found(self, operation, num_uploads,
                                 max_items=None, num_attempts=5):
        amount_seen = None
        for _ in range(num_attempts):
            pages = operation.paginate(self.endpoint, bucket=self.bucket_name,
                                       max_items=max_items)
            iterators = pages.result_key_iters()
            self.assertEqual(len(iterators), 2)
            self.assertEqual(iterators[0].result_key.expression, 'Uploads')
            # It sometimes takes a while for all the uploads to show up,
            # especially if the upload was just created.  If we don't
            # see the expected amount, we retry up to num_attempts time
            # before failing.
            amount_seen = len(list(iterators[0]))
            if amount_seen == num_uploads:
                # Test passed.
                return
            else:
                # Sleep and try again.
                time.sleep(2)
        self.fail("Expected to see %s uploads, instead saw: %s" % (
            num_uploads, amount_seen))


class TestS3BaseWithBucket(BaseS3Test):

    @asyncio.coroutine
    def set_up(self):

        yield from BaseS3Test.set_up(self)
        self.bucket_name = 'botocoretest%s-%s' % (
            int(time.time()), random.randint(1, 1000))
        self.bucket_location = 'us-west-2'

        operation = self.service.get_operation('CreateBucket')
        location = {'LocationConstraint': self.bucket_location}
        response = yield from operation.call(
            self.endpoint, bucket=self.bucket_name,
            create_bucket_configuration=location)
        self.assertEqual(response[0].status_code, 200)

    @asyncio.coroutine
    def tear_down(self):
        yield from self.delete_bucket(self.bucket_name)


class TestS3Buckets(TestS3BaseWithBucket):

    @async_test
    def test_can_make_request(self):
        # Basic smoke test to ensure we can talk to s3.
        operation = self.service.get_operation('ListBuckets')
        http, result = yield from operation.call(self.endpoint)
        self.assertEqual(http.status_code, 200)
        # Can't really assume anything about whether or not they have buckets,
        # but we can assume something about the structure of the response.
        self.assertEqual(sorted(list(result.keys())),
                         ['Buckets', 'Owner', 'ResponseMetadata'])

    @async_test
    def test_roundtrip(self):
        pass

    @async_test
    def test_can_get_bucket_location(self):
        operation = self.service.get_operation('GetBucketLocation')
        http, result = yield from operation.call(self.endpoint, bucket=self.bucket_name)
        self.assertEqual(http.status_code, 200)
        self.assertIn('LocationConstraint', result)
        # For buckets in us-east-1 (US Classic Region) this will be None
        self.assertEqual(result['LocationConstraint'], self.bucket_location)


class TestS3Objects(TestS3BaseWithBucket):

    @asyncio.coroutine
    def tear_down(self):
        for key in self.keys:
            operation = self.service.get_operation('DeleteObject')
            yield from operation.call(self.endpoint, bucket=self.bucket_name,
                           key=key)
        yield from TestS3BaseWithBucket.tear_down(self)

    def increment_auth(self, request, **kwargs):
        self.auth_paths.append(request.auth_path)

    @async_test
    def test_can_delete_urlencoded_object(self):
        key_name = 'a+b/foo'
        yield from self.create_object(key_name=key_name)
        self.keys.pop()
        bucket_op = self.service.get_operation('ListObjects')
        bucket_contents = (yield from bucket_op.call(
            self.endpoint, bucket=self.bucket_name))[1]['Contents']
        self.assertEqual(len(bucket_contents), 1)
        self.assertEqual(bucket_contents[0]['Key'], 'a+b/foo')

        op = self.service.get_operation('ListObjects')
        subdir_contents = (yield from op.call(self.endpoint, bucket=self.bucket_name, prefix='a+b'))[1]['Contents']
        self.assertEqual(len(subdir_contents), 1)
        self.assertEqual(subdir_contents[0]['Key'], 'a+b/foo')

        operation = self.service.get_operation('DeleteObject')
        response = (yield from operation.call(self.endpoint, bucket=self.bucket_name, key=key_name))[0]
        self.assertEqual(response.status_code, 204)

    @async_test
    def test_can_paginate(self):
        for i in range(5):
            key_name = 'key%s' % i
            yield from self.create_object(key_name)
        # Eventual consistency.
        time.sleep(3)
        operation = self.service.get_operation('ListObjects')
        generator = operation.paginate(self.endpoint, max_keys=1,
                                       bucket=self.bucket_name)
        responses = []
        r = yield from generator.next()
        while r:
            responses.append(r)
            r = yield from generator.next()
        self.assertEqual(len(responses), 5, responses)
        data = [r[1] for r in responses]
        key_names = [el['Contents'][0]['Key'] for el in data]
        self.assertEqual(key_names, ['key0', 'key1', 'key2', 'key3', 'key4'])

    @async_test
    def test_can_paginate_with_page_size(self):
        for i in range(5):
            key_name = 'key%s' % i
            yield from self.create_object(key_name)
        # Eventual consistency.
        time.sleep(3)
        operation = self.service.get_operation('ListObjects')
        generator = operation.paginate(self.endpoint, page_size=1,
                                       bucket=self.bucket_name)
        responses = []
        r = yield from generator.next()
        while r:
            responses.append(r)
            r = yield from generator.next()

        self.assertEqual(len(responses), 5, responses)
        data = [r[1] for r in responses]
        key_names = [el['Contents'][0]['Key'] for el in data]
        self.assertEqual(key_names, ['key0', 'key1', 'key2', 'key3', 'key4'])

    @async_test
    def test_client_can_paginate_with_page_size(self):
        for i in range(5):
            key_name = 'key%s' % i
            yield from self.create_object(key_name)
        # Eventual consistency.
        time.sleep(3)
        client = yield from self.session.create_client('s3', region_name=self.region)
        paginator = client.get_paginator('list_objects')
        generator = paginator.paginate(page_size=1, Bucket=self.bucket_name)
        responses = []
        r = yield from generator.next()
        while r:
            responses.append(r)
            r = yield from generator.next()
        # responses = list(generator)

        self.assertEqual(len(responses), 5, responses)
        data = [r for r in responses]
        key_names = [el['Contents'][0]['Key'] for el in data]
        self.assertEqual(key_names, ['key0', 'key1', 'key2', 'key3', 'key4'])

    @async_test
    def tst_result_key_iters(self):
        for i in range(5):
            key_name = 'key/%s/%s' % (i, i)
            yield from self.create_object(key_name)
            key_name2 = 'key/%s' % i
            yield from self.create_object(key_name2)
        time.sleep(3)
        operation = self.service.get_operation('ListObjects')
        generator = operation.paginate(self.endpoint, max_keys=2,
                                       prefix='key/',
                                       delimiter='/',
                                       bucket=self.bucket_name)
        iterators = generator.result_key_iters()
        response = defaultdict(list)
        key_names = [i.result_key for i in iterators]
        for vals in zip_longest(*iterators):
            for k, val in zip(key_names, vals):
                response.setdefault(k.expression, [])
                response[k.expression].append(val)
        self.assertIn('Contents', response)
        self.assertIn('CommonPrefixes', response)

    @async_test
    def test_can_get_and_put_object(self):
        yield from self.create_object('foobarbaz', body='body contents')
        time.sleep(3)

        operation = self.service.get_operation('GetObject')
        response = yield from operation.call(self.endpoint, bucket=self.bucket_name, key='foobarbaz')
        data = response[1]
        self.assertEqual((yield from data['Body'].read()).decode('utf-8'), 'body contents')

    @async_test
    def test_get_object_stream_wrapper(self):
        yield from self.create_object('foobarbaz', body='body contents')
        operation = self.service.get_operation('GetObject')
        response = yield from operation.call(self.endpoint, bucket=self.bucket_name,
                                  key='foobarbaz')
        body = response[1]['Body']
        # Am able to set a socket timeout
        body.set_socket_timeout(10)
        self.assertEqual((yield from body.read(amt=1)).decode('utf-8'), 'b')
        self.assertEqual((yield from body.read()).decode('utf-8'), 'ody contents')

    @async_test
    def test_paginate_max_items(self):
        yield from self.create_multipart_upload('foo/key1')
        yield from self.create_multipart_upload('foo/key1')
        yield from self.create_multipart_upload('foo/key1')
        yield from self.create_multipart_upload('foo/key2')
        yield from self.create_multipart_upload('foobar/key1')
        yield from self.create_multipart_upload('foobar/key2')
        yield from self.create_multipart_upload('bar/key1')
        yield from self.create_multipart_upload('bar/key2')

        operation = self.service.get_operation('ListMultipartUploads')

        # Verify when we have max_items=None, we get back all 8 uploads.
        self.assert_num_uploads_found(operation, max_items=None, num_uploads=8)

        # Verify when we have max_items=1, we get back 1 upload.
        self.assert_num_uploads_found(operation, max_items=1, num_uploads=1)

        # Works similar with build_full_result()
        pages = operation.paginate(self.endpoint,
                                   max_items=1,
                                   bucket=self.bucket_name)
        full_result = yield from pages.build_full_result()
        self.assertEqual(len(full_result['Uploads']), 1)

    @async_test
    def test_paginate_within_page_boundaries(self):
        yield from self.create_object('a')
        yield from self.create_object('b')
        yield from self.create_object('c')
        yield from self.create_object('d')
        operation = self.service.get_operation('ListObjects')
        # First do it without a max keys so we're operating on a single page of
        # results.
        pages = operation.paginate(self.endpoint, max_items=1,
                                   bucket=self.bucket_name)
        first = yield from pages.build_full_result()
        t1 = first['NextToken']

        pages = operation.paginate(self.endpoint, max_items=1,
                                   starting_token=t1,
                                   bucket=self.bucket_name)
        second = yield from pages.build_full_result()
        t2 = second['NextToken']

        pages = operation.paginate(self.endpoint, max_items=1,
                                   starting_token=t2,
                                   bucket=self.bucket_name)
        third = yield from pages.build_full_result()
        t3 = third['NextToken']

        pages = operation.paginate(self.endpoint, max_items=1,
                                   starting_token=t3,
                                   bucket=self.bucket_name)
        fourth = yield from pages.build_full_result()

        self.assertEqual(first['Contents'][-1]['Key'], 'a')
        self.assertEqual(second['Contents'][-1]['Key'], 'b')
        self.assertEqual(third['Contents'][-1]['Key'], 'c')
        self.assertEqual(fourth['Contents'][-1]['Key'], 'd')

    @async_test
    def test_unicode_key_put_list(self):
        # Verify we can upload a key with a unicode char and list it as well.
        key_name = u'\u2713'
        yield from self.create_object(key_name)
        operation = self.service.get_operation('ListObjects')
        parsed = (yield from operation.call(self.endpoint, bucket=self.bucket_name))[1]
        self.assertEqual(len(parsed['Contents']), 1)
        self.assertEqual(parsed['Contents'][0]['Key'], key_name)
        operation = self.service.get_operation('GetObject')
        parsed = (yield from operation.call(self.endpoint, bucket=self.bucket_name, key=key_name))[1]
        self.assertEqual((yield from parsed['Body'].read()).decode('utf-8'), 'foo')

    @async_test
    def tst_thread_safe_auth(self):
        self.auth_paths = []
        self.caught_exceptions = []
        self.session.register('before-sign', self.increment_auth)
        yield from self.create_object(key_name='foo1')
        threads = []
        for i in range(10):
            t = threading.Thread(target=self.create_object_catch_exceptions,
                                 args=('foo%s' % i,))
            t.daemon = True
            threads.append(t)
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(
            self.caught_exceptions, [],
            "Unexpectedly caught exceptions: %s" % self.caught_exceptions)
        self.assertEqual(
            len(set(self.auth_paths)), 10,
            "Expected 10 unique auth paths, instead received: %s" %
            (self.auth_paths))

    @async_test
    def test_non_normalized_key_paths(self):
        # The create_object method has assertEqual checks for 200 status.
        yield from self.create_object('key./././name')
        bucket_contents = (yield from self.service.get_operation('ListObjects').call(
            self.endpoint, bucket=self.bucket_name))[1]['Contents']
        self.assertEqual(len(bucket_contents), 1)
        self.assertEqual(bucket_contents[0]['Key'], 'key./././name')


class TestS3Regions(BaseS3Test):

    @asyncio.coroutine
    def set_up(self):
        yield from BaseS3Test.set_up(self)
        self.tempdir = tempfile.mkdtemp()
        self.endpoint = self.service.get_endpoint('us-west-2')

    @asyncio.coroutine
    def tear_down(self):
        shutil.rmtree(self.tempdir)
        #yield from BaseS3Test.tear_down(self)

    @asyncio.coroutine
    def create_bucket_in_region(self, region):
        bucket_name = 'botocoretest%s-%s' % (
            int(time.time()), random.randint(1, 1000))
        operation = self.service.get_operation('CreateBucket')
        response, parsed = yield from operation.call(
            self.endpoint, bucket=bucket_name,
            create_bucket_configuration={'LocationConstraint': 'us-west-2'})
        self.assertEqual(response.status_code, 200)
        self.addCleanup(self.delete_bucket, bucket_name=bucket_name)
        return bucket_name

    @async_test
    def test_reset_stream_on_redirects(self):
        # Create a bucket in a non classic region.
        bucket_name = yield from self.create_bucket_in_region('us-west-2')
        # Then try to put a file like object to this location.
        filename = os.path.join(self.tempdir, 'foo')
        with open(filename, 'wb') as f:
            f.write(b'foo' * 1024)
        put_object = self.service.get_operation('PutObject')
        with open(filename, 'rb') as f:
            response, parsed = yield from put_object.call(
                self.endpoint, bucket=bucket_name, key='foo', body=f)
        self.assertEqual(
            response.status_code, 200,
            "Non 200 status code (%s) received: %s" % (
                response.status_code, parsed))
        self.addCleanup(self.delete_object, key='foo',
                        bucket_name=bucket_name)

        operation = self.service.get_operation('GetObject')
        data = (yield from operation.call(self.endpoint, bucket=bucket_name, key='foo'))[1]
        self.assertEqual((yield from data['Body'].read()), b'foo' * 1024)


class TestS3Copy(TestS3BaseWithBucket):

    @asyncio.coroutine
    def tear_down(self):
        for key in self.keys:
            operation = self.service.get_operation('DeleteObject')
            response = yield from operation.call(
                self.endpoint, bucket=self.bucket_name, key=key)
            self.assertEqual(response[0].status_code, 204)
        yield from TestS3BaseWithBucket.tear_down(self)

    @async_test
    def test_copy_with_quoted_char(self):
        key_name = 'a+b/foo'
        yield from self.create_object(key_name=key_name)

        operation = self.service.get_operation('CopyObject')
        key_name2 = key_name + 'bar'
        http, parsed = yield from operation.call(
            self.endpoint, bucket=self.bucket_name, key=key_name + 'bar',
            copy_source='%s/%s' % (self.bucket_name, key_name))
        self.assertEqual(http.status_code, 200)
        self.keys.append(key_name2)

        # Now verify we can retrieve the copied object.
        operation = self.service.get_operation('GetObject')
        response = yield from operation.call(self.endpoint, bucket=self.bucket_name,
                                  key=key_name + 'bar')
        data = response[1]
        self.assertEqual((yield from data['Body'].read()).decode('utf-8'), 'foo')

    @async_test
    def test_copy_with_s3_metadata(self):
        key_name = 'foo.txt'
        yield from self.create_object(key_name=key_name)
        copied_key = 'copied.txt'
        operation = self.service.get_operation('CopyObject')
        http, parsed = yield from operation.call(
            self.endpoint, bucket=self.bucket_name, key=copied_key,
            copy_source='%s/%s' % (self.bucket_name, key_name),
            metadata_directive='REPLACE',
            metadata={"mykey": "myvalue", "mykey2": "myvalue2"})
        self.keys.append(copied_key)
        self.assertEqual(http.status_code, 200)


class TestS3Presign(BaseS3Test):

    @asyncio.coroutine
    def set_up(self):
        yield from BaseS3Test.set_up(self)
        self.bucket_name = 'botocoretest%s-%s' % (
            int(time.time()), random.randint(1, 1000))

        operation = self.service.get_operation('CreateBucket')
        response = yield from operation.call(self.endpoint, bucket=self.bucket_name)
        self.assertEqual(response[0].status_code, 200)

    @asyncio.coroutine
    def tear_down(self):
        for key in self.keys:
            operation = self.service.get_operation('DeleteObject')
            yield from operation.call(self.endpoint, bucket=self.bucket_name,
                           key=key)
        yield from self.delete_bucket(self.bucket_name)
        #yield from BaseS3Test.tear_down(self)

    @async_test
    def test_can_retrieve_presigned_object(self):
        key_name = 'mykey'
        yield from self.create_object(key_name=key_name, body='foobar')
        signer = yieldfrom.botocore.auth.S3SigV4QueryAuth(
            credentials=(yield from self.service.session.get_credentials()),
            region_name='us-east-1', service_name='s3', expires=60)
        op = self.service.get_operation('GetObject')
        params = op.build_parameters(bucket=self.bucket_name, key=key_name)
        request = yield from self.endpoint.create_request(params)
        signer.add_auth(request.original)
        presigned_url = request.original.prepare().url
        # We should now be able to retrieve the contents of 'mykey' using
        # this presigned url.
        self.assertEqual((yield from (yield from requests.get(presigned_url)).content), b'foobar')


class TestS3PresignFixHost(BaseS3Test):

    @async_test
    def test_presign_does_not_change_host(self):
        endpoint = self.service.get_endpoint('us-west-2')
        key_name = 'mykey'
        bucket_name = 'mybucket'
        signer = yieldfrom.botocore.auth.S3SigV4QueryAuth(
            credentials=(yield from self.service.session.get_credentials()),
            region_name='us-west-2', service_name='s3', expires=60)
        op = self.service.get_operation('GetObject')
        params = op.build_parameters(bucket=bucket_name, key=key_name)
        request = yield from endpoint.create_request(params)
        signer.add_auth(request.original)
        presigned_url = request.original.prepare().url
        # We should not have rewritten the host to be s3.amazonaws.com.
        self.assertTrue(presigned_url.startswith(
            'https://s3-us-west-2.amazonaws.com/mybucket/mykey'),
            "Host was suppose to be the us-west-2 endpoint, instead "
            "got: %s" % presigned_url)


class TestCreateBucketInOtherRegion(BaseS3Test):

    @asyncio.coroutine
    def set_up(self):
        yield from BaseS3Test.set_up(self)
        self.bucket_name = 'botocoretest%s-%s' % (
            int(time.time()), random.randint(1, 1000))
        self.bucket_location = 'us-west-2'

        operation = self.service.get_operation('CreateBucket')
        location = {'LocationConstraint': self.bucket_location}
        response = yield from operation.call(
            self.endpoint, bucket=self.bucket_name,
            create_bucket_configuration=location)
        self.assertEqual(response[0].status_code, 200)
        self.keys = []

    @asyncio.coroutine
    def tear_down(self):
        for key in self.keys:
            op = self.service.get_operation('DeleteObject')
            response = yield from op.call(self.endpoint, bucket=self.bucket_name, key=key)
            self.assertEqual(response[0].status_code, 204)
        yield from self.delete_bucket(self.bucket_name)

    @async_test
    def test_bucket_in_other_region(self):
        # This verifies expect 100-continue behavior.  We previously
        # had a bug where we did not support this behavior and trying to
        # create a bucket and immediately PutObject with a file like object
        # would actually cause errors.
        with temporary_file('w') as f:
            f.write('foobarbaz' * 1024 * 1024)
            f.flush()
            op = self.service.get_operation('PutObject')
            with open(f.name, 'rb') as body_file:
                response = yield from op.call(
                    self.endpoint, bucket=self.bucket_name,
                    key='foo.txt', body=body_file)
            self.assertEqual(response[0].status_code, 200)
            self.keys.append('foo.txt')

    @async_test
    def test_bucket_in_other_region_using_http(self):

        http_endpoint = self.service.get_endpoint(
            endpoint_url='http://s3.amazonaws.com/')
        with temporary_file('w') as f:
            f.write('foobarbaz' * 1024 * 1024)
            f.flush()
            op = self.service.get_operation('PutObject')
            with open(f.name, 'rb') as body_file:
                response = yield from op.call(
                    http_endpoint, bucket=self.bucket_name,
                    key='foo.txt', body=body_file)
            self.assertEqual(response[0].status_code, 200)
            self.keys.append('foo.txt')


class BaseS3ClientTest(BaseS3Test):

    @asyncio.coroutine
    def set_up(self):
        yield from BaseS3Test.set_up(self)
        self.client = yield from self.session.create_client('s3', region_name=self.region)

    def assert_status_code(self, response, status_code):
        self.assertEqual(
            response['ResponseMetadata']['HTTPStatusCode'],
            status_code
        )

    @asyncio.coroutine
    def create_bucket(self, bucket_name=None):
        bucket_kwargs = {}
        if bucket_name is None:
            bucket_name = 'botocoretest%s-%s' % (int(time.time()),
                                                 random.randint(1, 1000))
        bucket_kwargs = {'Bucket': bucket_name}
        if self.region != 'us-east-1':
            bucket_kwargs['CreateBucketConfiguration'] = {
                'LocationConstraint': self.region,
            }
        response = yield from self.client.create_bucket(**bucket_kwargs)
        self.assert_status_code(response, 200)
        self.addCleanup(self.delete_bucket, bucket_name)
        return bucket_name

    @asyncio.coroutine
    def abort_multipart_upload(self, bucket_name, key, upload_id):
        response = yield from self.client.abort_multipart_upload(
            UploadId=upload_id, Bucket=self.bucket_name, Key=key)
        pass

    @asyncio.coroutine
    def delete_object(self, key, bucket_name):
        response = yield from self.client.delete_object(Bucket=bucket_name, Key=key)
        self.assert_status_code(response, 204)

    @asyncio.coroutine
    def delete_bucket(self, bucket_name):
        response = yield from self.client.delete_bucket(Bucket=bucket_name)
        self.assert_status_code(response, 204)


class TestS3SigV4Client(BaseS3ClientTest):

    @asyncio.coroutine
    def set_up(self):
        yield from BaseS3ClientTest.set_up(self)
        self.region = 'eu-central-1'
        self.client = yield from self.session.create_client('s3', self.region)
        self.bucket_name = yield from self.create_bucket()
        self.keys = []

    @asyncio.coroutine
    def tear_down(self):
        for key in self.keys:
            response = yield from self.delete_object(bucket_name=self.bucket_name, key=key)
        #yield from BaseS3ClientTest.tear_down(self)

    @async_test
    def test_can_get_bucket_location(self):
        # Even though the bucket is in eu-central-1, we should still be able to
        # use the us-east-1 endpoint class to get the bucket location.
        operation = self.service.get_operation('GetBucketLocation')
        # Also keep in mind that while this test is useful, it doesn't test
        # what happens once DNS propogates which is arguably more interesting,
        # as DNS will point us to the eu-central-1 endpoint.
        us_east_1 = self.service.get_endpoint('us-east-1')
        response = yield from operation.call(us_east_1, Bucket=self.bucket_name)
        self.assertEqual(response[1]['LocationConstraint'], 'eu-central-1')

    @async_test
    def test_request_retried_for_sigv4(self):
        body = io.BytesIO(b"Hello world!")

        original_send = adapters.HTTPAdapter.send
        state = mock.Mock()
        state.error_raised = False

        @asyncio.coroutine
        def mock_http_adapter_send(self, *args, **kwargs):
            if not state.error_raised:
                state.error_raised = True
                raise ConnectionError("Simulated ConnectionError raised.")
            else:
                return (yield from original_send(self, *args, **kwargs))
        with mock.patch('yieldfrom.requests.adapters.HTTPAdapter.send',
                        mock_http_adapter_send):
            response = yield from self.client.put_object(Bucket=self.bucket_name,
                                              Key='foo.txt', Body=body)
            self.assert_status_code(response, 200)
            self.keys.append('foo.txt')

    @async_test
    def test_paginate_list_objects_unicode(self):
        key_names = [
            u'non-ascii-key-\xe4\xf6\xfc-01.txt',
            u'non-ascii-key-\xe4\xf6\xfc-02.txt',
            u'non-ascii-key-\xe4\xf6\xfc-03.txt',
            u'non-ascii-key-\xe4\xf6\xfc-04.txt',
        ]
        for key in key_names:
            response = yield from self.client.put_object(Bucket=self.bucket_name,
                                              Key=key, Body='')
            self.assert_status_code(response, 200)
            self.keys.append(key)

        list_objs_paginator = self.client.get_paginator('list_objects')
        key_refs = []
        pageIterator = list_objs_paginator.paginate(Bucket=self.bucket_name,
                                                     page_size=2)
        response = yield from pageIterator.next()
        while response:
            for content in response['Contents']:
                key_refs.append(content['Key'])
            response = yield from pageIterator.next()

        self.assertEqual(key_names, key_refs)

    @async_test
    def test_paginate_list_objects_safe_chars(self):

        key_names = [
            u'-._~safe-chars-key-01.txt',
            u'-._~safe-chars-key-02.txt',
            u'-._~safe-chars-key-03.txt',
            u'-._~safe-chars-key-04.txt',
        ]
        for key in key_names:
            response = yield from self.client.put_object(Bucket=self.bucket_name,
                                              Key=key, Body='')
            self.assert_status_code(response, 200)
            self.keys.append(key)

        list_objs_paginator = self.client.get_paginator('list_objects')
        key_refs = []
        pageIterator = list_objs_paginator.paginate(Bucket=self.bucket_name, page_size=2)
        response = yield from pageIterator.next()
        while response:
            for content in response['Contents']:
                key_refs.append(content['Key'])
            response = yield from pageIterator.next()

        self.assertEqual(key_names, key_refs)

    @async_test
    def test_create_multipart_upload(self):

        key = 'mymultipartupload'
        response = yield from self.client.create_multipart_upload(
            Bucket=self.bucket_name, Key=key
        )
        self.assert_status_code(response, 200)
        upload_id = response['UploadId']
        self.addCleanup(
            self.abort_multipart_upload,
            bucket_name=self.bucket_name, key=key, upload_id=upload_id
        )

        response = yield from self.client.list_multipart_uploads(
            Bucket=self.bucket_name, Prefix=key
        )

        # Make sure there is only one multipart upload.
        self.assertEqual(len(response['Uploads']), 1)
        # Make sure the upload id is as expected.
        self.assertEqual(response['Uploads'][0]['UploadId'], upload_id)


class TestCanSwitchToSigV4(unittest.TestCase):

    @asyncio.coroutine
    def set_up(self):
        self.environ = {}
        self.environ_patch = mock.patch('os.environ', self.environ)
        self.environ_patch.start()
        self.session = yieldfrom.botocore.session.get_session()
        self.tempdir = tempfile.mkdtemp()
        self.config_filename = os.path.join(self.tempdir, 'config_file')
        self.environ['AWS_CONFIG_FILE'] = self.config_filename

    @asyncio.coroutine
    def tear_down(self):
        self.environ_patch.stop()
        shutil.rmtree(self.tempdir)


class TestSSEKeyParamValidation(unittest.TestCase):

    @asyncio.coroutine
    def set_up(self):
        self.session = yieldfrom.botocore.session.get_session()
        self.client = yield from self.session.create_client('s3', 'us-west-2')
        self.bucket_name = 'botocoretest%s-%s' % (
            int(time.time()), random.randint(1, 1000))
        yield from self.client.create_bucket(
            Bucket=self.bucket_name,
            CreateBucketConfiguration={
                'LocationConstraint': 'us-west-2',
            }
        )
        self.addCleanup(self.client.delete_bucket, Bucket=self.bucket_name)

    @async_test
    def test_make_request_with_sse(self):

        key_bytes = os.urandom(32)
        # Obviously a bad key here, but we just want to ensure we can use
        # a str/unicode type as a key.
        key_str = 'abcd' * 8

        # Put two objects with an sse key, one with random bytes,
        # one with str/unicode.  Then verify we can GetObject() both
        # objects.
        yield from self.client.put_object(
            Bucket=self.bucket_name, Key='foo.txt',
            Body=io.BytesIO(b'mycontents'), SSECustomerAlgorithm='AES256',
            SSECustomerKey=key_bytes)
        self.addCleanup(self.client.delete_object,
                        Bucket=self.bucket_name, Key='foo.txt')
        yield from self.client.put_object(
            Bucket=self.bucket_name, Key='foo2.txt',
            Body=io.BytesIO(b'mycontents2'), SSECustomerAlgorithm='AES256',
            SSECustomerKey=key_str)
        self.addCleanup(self.client.delete_object,
                        Bucket=self.bucket_name, Key='foo2.txt')

        _o = yield from self.client.get_object(Bucket=self.bucket_name,
                                   Key='foo.txt',
                                   SSECustomerAlgorithm='AES256',
                                   SSECustomerKey=key_bytes)
        self.assertEqual((yield from _o['Body'].read()), b'mycontents')
        _o = yield from self.client.get_object(Bucket=self.bucket_name,
                                   Key='foo2.txt',
                                   SSECustomerAlgorithm='AES256',
                                   SSECustomerKey=key_str)
        self.assertEqual((yield from _o['Body'].read()), b'mycontents2')


if __name__ == '__main__':
    unittest.main()
