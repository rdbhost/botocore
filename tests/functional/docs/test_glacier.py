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
import asyncio
import sys

sys.path.extend(['..', '../..'])
from asyncio_test_utils import async_test
from docs import BaseDocsFunctionalTest


class TestGlacierDocs(BaseDocsFunctionalTest):
    @async_test
    def test_account_id(self):
        yield from self.assert_is_documented_as_autopopulated_param(
            service_name='glacier',
            method_name='abort_multipart_upload',
            param_name='accountId',
            doc_string='Note: this parameter is set to "-"')

    @async_test
    def test_checksum(self):
        yield from self.assert_is_documented_as_autopopulated_param(
            service_name='glacier',
            method_name='upload_archive',
            param_name='checksum')
