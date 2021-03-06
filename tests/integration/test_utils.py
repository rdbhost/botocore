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
import time
from tests import unittest

# This file altered by David Keeney 2015, as part of conversion to
# asyncio.
#
import os, sys
import logging

import yieldfrom.botocore.session
from yieldfrom.botocore.utils import ArgumentGenerator

sys.path.append('..')
from asyncio_test_utils import async_test

logging.basicConfig(level=logging.DEBUG)
os.environ['PYTHONASYNCIODEBUG'] = '1'


class ArgumentGeneratorError(AssertionError):
    def __init__(self, service_name, operation_name,
                 generated, message):
        full_msg = (
            'Error generating skeleton for %s:%s, %s\nActual:\n%s' % (
                service_name, operation_name, message, generated))
        super(AssertionError, self).__init__(full_msg)


def test_can_generate_all_inputs():
    session = yieldfrom.botocore.session.get_session()
    generator = ArgumentGenerator()
    for service_name in session.get_available_services():
        service_model = yield from session.get_service_model(service_name)
        for operation_name in service_model.operation_names:
            operation_model = service_model.operation_model(operation_name)
            input_shape = operation_model.input_shape
            if input_shape is not None and input_shape.members:
                yield (_test_can_generate_skeleton, generator,
                       input_shape, service_name, operation_name)


def _test_can_generate_skeleton(generator, shape, service_name,
                                operation_name):
    generated = generator.generate_skeleton(shape)
    # Do some basic sanity checks to make sure the generated shape
    # looks right.  We're mostly just ensuring that the generate_skeleton
    # doesn't throw an exception.
    if not isinstance(generated, dict):
        raise ArgumentGeneratorError(
            service_name, operation_name,
            generated, 'expected a dict')
    # The generated skeleton also shouldn't be empty (the test
    # generator has already filtered out input_shapes of None).
    if len(generated) == 0:
        raise ArgumentGeneratorError(
            service_name, operation_name,
            generated, "generated arguments were empty")
