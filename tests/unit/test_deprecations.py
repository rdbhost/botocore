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
import sys
import contextlib
import warnings

from nose.tools import assert_equal
from nose.tools import assert_true
import yieldfrom.botocore.session
from yieldfrom.botocore.exceptions import ImminentRemovalWarning

sys.path.extend(['..', '../..'])
from asyncio_test_utils import async_test
import unittest


@contextlib.contextmanager
def assert_warns(warning_type, contains=''):
    # The warnings module keeps state at the module level.
    # In order to give each test a clean slate we need to wipe
    # this state out before yielding back to the test.
    for v in sys.modules.values():
        if getattr(v, '__warningregistry__', None):
            v.__warningregistry__ = {}
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter('always')
        yield
    assert_true(len(w) > 0)
    assert_equal(w[0].category, warning_type)
    if contains:
        assert_true(contains in str(w[0].message),
                    '"%s" not in: %s"' % (contains, w[0].message))


class TestDeprecationsHaveWarnings(unittest.TestCase):
    def setUp(self):
        self.session = yieldfrom.botocore.session.get_session()

    def test_get_service_deprecated(self):
        with assert_warns(ImminentRemovalWarning, contains='get_service'):
            yield from self.session.get_service('cloudformation')

    def test_service_get_operation_deprecated(self):
        service = yield from self.session.get_service('cloudformation')
        with assert_warns(ImminentRemovalWarning, contains='get_operation'):
            yield from service.get_operation('ListStacks')

    def test_get_endpoint(self):
        service = self.session.get_service('cloudformation')
        with assert_warns(ImminentRemovalWarning, contains='get_endpoint'):
            yield from service.get_endpoint('us-east-1')
