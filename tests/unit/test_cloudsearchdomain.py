#!/usr/bin/env python
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
import os
os.environ['PYTHONASYNCIODEBUG'] = '1'
import logging
logging.basicConfig(level=logging.DEBUG)

from tests import BaseSessionTest

from yieldfrom.botocore.exceptions import NoRegionError
import io

import sys
sys.path.append('..')
from asyncio_test_utils import async_test



class TestCloudsearchOperations(BaseSessionTest):

    @async_test
    def test_streaming_json_upload(self):
        stream = io.BytesIO(b'{"fakejson": true}')
        service = yield from self.session.get_service('cloudsearchdomain')
        operation = service.get_operation('UploadDocuments')
        built = operation.build_parameters(
            contentType='application/json', documents=stream)
        endpoint = service.get_endpoint(region_name='us-east-1',
                                        endpoint_url='http://example.com')
        request = yield from endpoint.create_request(built)
        self.assertEqual(request.body, stream)

    @async_test
    def test_region_required_due_to_sigv4(self):
        stream = io.StringIO('{"fakejson": true}')
        service = yield from self.session.get_service('cloudsearchdomain')
        operation = service.get_operation('UploadDocuments')
        built = operation.build_parameters(
            contentType='application/json', documents=stream)
        # Note we're not giving a region name.
        endpoint = service.get_endpoint(endpoint_url='http://example.com')
        with self.assertRaises(NoRegionError):
            yield from operation.call(endpoint, contentType='application/json', documents=stream)
