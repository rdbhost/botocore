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

from tests import unittest
import random
import asyncio
import sys
sys.path.append('..')
from asyncio_test_utils import async_test

import yieldfrom.botocore.session


class TestCognitoIdentity(unittest.TestCase):

    @asyncio.coroutine
    def set_up(self):
        self.session = yieldfrom.botocore.session.get_session()
        self.client = yield from self.session.create_client('cognito-identity', 'us-east-1')

    @async_test
    def test_can_create_and_delete_identity_pool(self):
        pool_name = 'botocoretest%s' % random.randint(1, 100000)
        response = yield from self.client.create_identity_pool(
            IdentityPoolName=pool_name, AllowUnauthenticatedIdentities=True)
        self.client.delete_identity_pool(IdentityPoolId=response['IdentityPoolId'])


if __name__ == '__main__':
    unittest.main()
