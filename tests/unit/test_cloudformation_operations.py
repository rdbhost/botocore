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

# This file altered by David Keeney 2015, as part of conversion to
# asyncio.
#
import os
os.environ['PYTHONASYNCIODEBUG'] = 1
import logging
logging.basicConfig(level=logging.DEBUG)

import sys
sys.path.append('..')
from asyncio_test_utils import async_test


from tests import TestParamSerialization
import yieldfrom.botocore.session


class TestCloudformationOperations(TestParamSerialization):

    @async_test
    def test_create_stack(self):
        result = {'StackName': 'foobar',
                  'TemplateURL': 'http://foo.com/bar.json',
                  'StackPolicyURL': 'http://fie.com/baz.json'}
        yield from self.assert_params_serialize_to(
            'cloudformation.CreateStack',
            input_params={'StackName': 'foobar',
                          'TemplateURL': 'http://foo.com/bar.json',
                          'StackPolicyURL': 'http://fie.com/baz.json'},
            serialized_params=result)

    @async_test
    def test_update_stack(self):
        result = {'StackName': 'foobar',
                  'TemplateURL': 'http://foo.com/bar.json',
                  'StackPolicyURL': 'http://fie.com/baz.json'}
        yield from self.assert_params_serialize_to(
            'cloudformation.UpdateStack',
            input_params={'StackName': 'foobar',
                          'TemplateURL': 'http://foo.com/bar.json',
                          'StackPolicyURL': 'http://fie.com/baz.json'},
            serialized_params=result)


if __name__ == "__main__":
    unittest.main()
