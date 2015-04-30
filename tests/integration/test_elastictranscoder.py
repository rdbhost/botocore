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
import logging
import unittest
import asyncio
import sys
import functools
import random

import yieldfrom.botocore.session

sys.path.append('..')
from asyncio_test_utils import async_test

os.environ['PYTHONASYNCIODEBUG'] = '1'
logging.basicConfig(level=logging.DEBUG)


DEFAULT_ROLE_POLICY = """\
{"Statement": [
    {
        "Action": "sts:AssumeRole",
        "Principal": {
            "Service": "elastictranscoder.amazonaws.com"
        },
        "Effect": "Allow",
        "Sid": "1"
    }
]}
"""

class TestElasticTranscoder(unittest.TestCase):

    @asyncio.coroutine
    def set_up(self):
        self.session = yieldfrom.botocore.session.get_session()
        self.service = yield from self.session.get_service('elastictranscoder')
        self.endpoint = self.service.get_endpoint('us-east-1')

    @asyncio.coroutine
    def create_bucket(self):
        s3 = yield from self.session.get_service('s3')
        bucket_name = 'ets-bucket-1-%s' % random.randint(1, 1000000)
        create_bucket = s3.get_operation('CreateBucket')
        delete_bucket = s3.get_operation('DeleteBucket')
        endpoint = s3.get_endpoint('us-east-1')
        response = (yield from create_bucket.call(endpoint, bucket=bucket_name))[0]
        self.assertEqual(response.status_code, 200)
        self.addCleanup(
            functools.partial(delete_bucket.call, endpoint,
                              bucket=bucket_name))
        return bucket_name

    @asyncio.coroutine
    def create_iam_role(self):
        iam = yield from self.session.get_service('iam')
        endpoint = iam.get_endpoint('us-east-1')
        create_role = iam.get_operation('CreateRole')
        delete_role = iam.get_operation('DeleteRole')
        role_name = 'ets-role-name-1-%s' % random.randint(1, 1000000)
        response, parsed = yield from create_role.call(endpoint, role_name=role_name,
            assume_role_policy_document=DEFAULT_ROLE_POLICY)
        self.assertEqual(response.status_code, 200)
        arn = parsed['Role']['Arn']
        self.addCleanup(
            functools.partial(delete_role.call, endpoint, role_name=role_name))
        return arn

    @async_test
    def test_list_streams(self):
        operation = self.service.get_operation('ListPipelines')
        http, parsed = yield from operation.call(self.endpoint)
        self.assertEqual(http.status_code, 200)
        self.assertIn('Pipelines', parsed)

    @async_test
    def test_list_presets(self):
        operation = self.service.get_operation('ListPresets')
        http, parsed = yield from operation.call(self.endpoint, ascending='true')
        self.assertEqual(http.status_code, 200)
        self.assertIn('Presets', parsed)

    @async_test
    def test_create_pipeline(self):
        # In order to create a pipeline, we need to create 2 s3 buckets
        # and 1 iam role.
        input_bucket = yield from self.create_bucket()
        output_bucket = yield from self.create_bucket()
        role = yield from self.create_iam_role()
        pipeline_name = 'botocore-test-create-%s' % (random.randint(1, 1000000))

        delete_pipeline = self.service.get_operation('DeletePipeline')

        operation = self.service.get_operation('CreatePipeline')
        http, parsed = yield from operation.call(
            self.endpoint, input_bucket=input_bucket, output_bucket=output_bucket,
            role=role, name=pipeline_name,
            notifications={'Progressing': '', 'Completed': '',
                           'Warning': '', 'Error': ''})
        pipeline_id = parsed['Pipeline']['Id']
        self.addCleanup(
            functools.partial(delete_pipeline.call, self.endpoint, Id=pipeline_id))
        if http.status_code == 429:
            # It's possible that we have too many existing pipelines.
            # We don't want to fail the test, but we need to indicate
            # that it didn't pass.  A SkipTest is a reasonable compromise.
            raise unittest.SkipTest(
                "HTTP status 429, too many existing pipelines."
            )
        self.assertEqual(http.status_code, 201)
        self.assertIn('Pipeline', parsed)


if __name__ == '__main__':
    unittest.main()
