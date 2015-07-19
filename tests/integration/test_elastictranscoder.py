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

from tests import unittest, random_chars
# This file altered by David Keeney 2015, as part of conversion to
# asyncio.
#
import os
import logging
import unittest
import asyncio
import sys
import functools

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
        self.client = yield from self.session.create_client(
            'elastictranscoder', 'us-east-1')
        self.s3_client = yield from self.session.create_client('s3', 'us-east-1')
        self.iam_client = yield from self.session.create_client('iam', 'us-east-1')

    @asyncio.coroutine
    def create_bucket(self):
        bucket_name = 'ets-bucket-1-%s' % random_chars(50)
        yield from self.s3_client.create_bucket(Bucket=bucket_name)
        self.addCleanup(
            self.s3_client.delete_bucket, Bucket=bucket_name)
        return bucket_name

    @asyncio.coroutine
    def create_iam_role(self):
        role_name = 'ets-role-name-1-%s' % random_chars(10)
        parsed = yield from self.iam_client.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=DEFAULT_ROLE_POLICY)
        arn = parsed['Role']['Arn']
        self.addCleanup(
            self.iam_client.delete_role, RoleName=role_name)
        return arn

    @async_test
    def test_list_streams(self):
        parsed = yield from self.client.list_pipelines()
        self.assertIn('Pipelines', parsed)

    @async_test
    def test_list_presets(self):
        parsed = yield from self.client.list_presets(Ascending='true')
        self.assertIn('Presets', parsed)

    @async_test
    def test_create_pipeline(self):
        # In order to create a pipeline, we need to create 2 s3 buckets
        # and 1 iam role.
        input_bucket = yield from self.create_bucket()
        output_bucket = yield from self.create_bucket()
        role = yield from self.create_iam_role()
        pipeline_name = 'botocore-test-create-%s' % random_chars(10)

        parsed = yield from self.client.create_pipeline(
            InputBucket=input_bucket, OutputBucket=output_bucket,
            Role=role, Name=pipeline_name,
            Notifications={'Progressing': '', 'Completed': '',
                           'Warning': '', 'Error': ''})
        pipeline_id = parsed['Pipeline']['Id']
        self.addCleanup(self.client.delete_pipeline, Id=pipeline_id)
        self.assertIn('Pipeline', parsed)


if __name__ == '__main__':
    unittest.main()
