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
import jmespath
import logging
#import time

from .exceptions import WaiterError, ClientError, WaiterConfigError
from . import xform_name
import asyncio


logger = logging.getLogger(__name__)


def create_waiter_with_client(waiter_name, waiter_model, client):
    """

    :type waiter_name: str
    :param waiter_name: The name of the waiter.  The name should match
        the name (including the casing) of the key name in the waiter
        model file (typically this is CamelCasing).

    :type waiter_model: botocore.waiter.WaiterModel
    :param waiter_model: The model for the waiter configuration.

    :type client: botocore.client.BaseClient
    :param client: The botocore client associated with the service.

    :rtype: botocore.waiter.Waiter
    :return: The waiter object.

    """
    single_waiter_config = waiter_model.get_waiter(waiter_name)
    operation_name = xform_name(single_waiter_config.operation)
    operation_method = NormalizedOperationMethod(
        getattr(client, operation_name))
    return Waiter(
        waiter_name, single_waiter_config, operation_method
    )

@asyncio.coroutine
def create_waiter_from_legacy(waiter_name, waiter_config,
                              service_object, endpoint):
    """

    :type waiter_name: str
    :param waiter_name: The name of the waiter.

    :type waiter_config: dict
    :param waiter_config: The loaded waiter model file.

    :type service_object: botocore.service.Service
    :param service_object: The service object associated with the waiter.

    :rtype: botocore.waiter.Waiter
    :return: The waiter object.

    """
    model = WaiterModel(waiter_config)
    single_waiter_config = model.get_waiter(waiter_name)
    operation_object = service_object.get_operation(single_waiter_config.operation)
    operation_method = LegacyOperationMethod(operation_object, endpoint)
    return Waiter(waiter_name, single_waiter_config, operation_method)


# The NormalizedOperationMethod and the LegacyOperationMethod
# below will normalize the differences between the client interface
# and the Service/Operation object interface.  This allows for a single
# Waiter class to be used for both clients and Service/Operation.
class NormalizedOperationMethod(object):
    def __init__(self, client_method):
        self._client_method = client_method

    def __call__(self, **kwargs):
        try:
            return self._client_method(**kwargs)
        except ClientError as e:
            return e.response


class LegacyOperationMethod(object):

    def __init__(self, operation_object, endpoint):
        self._operation_object = operation_object
        self._endpoint = endpoint

    @asyncio.coroutine
    def __call__(self, **kwargs):
        try:
            http, parsed = yield from self._operation_object.call(self._endpoint, **kwargs)
        except Exception as e:
            # In theory, a handler can raise an type of exception.
            # We're going to make a best effort attempt to handle
            # the ClientError attributes, but not require that
            # the exception is an instance of ClientError.
            if self._looks_like_client_error(e):
                return {
                    'Error': {
                        'Code': e.error_code,
                        'Message': e.error_message,
                    }
                }
            else:
                raise
        return parsed

    def _looks_like_client_error(self, e):
        return hasattr(e, 'error_code') and hasattr(e, 'error_message')


class WaiterModel(object):
    SUPPORTED_VERSION = 2

    def __init__(self, waiter_config):
        """

        Note that the WaiterModel takes ownership of the waiter_config.
        It may or may not mutate the waiter_config.  If this is a concern,
        it is best to make a copy of the waiter config before passing it to
        the WaiterModel.

        :type waiter_config: dict
        :param waiter_config: The loaded waiter config
            from the <service>*.waiters.json file.  This can be
            obtained from a botocore Loader object as well.

        """
        self._waiter_config = waiter_config['waiters']

        # These are part of the public API.  Changing these
        # will result in having to update the consuming code,
        # so don't change unless you really need to.
        version = waiter_config.get('version', 'unknown')
        self._verify_supported_version(version)
        self.version = version
        self.waiter_names = list(sorted(waiter_config['waiters'].keys()))

    def _verify_supported_version(self, version):
        if version != self.SUPPORTED_VERSION:
            raise WaiterConfigError(
                error_msg=("Unsupported waiter version, supported version "
                           "must be: %s, but version of waiter config "
                           "is: %s" % (self.SUPPORTED_VERSION,
                                       version)))

    def get_waiter(self, waiter_name):
        try:
            single_waiter_config = self._waiter_config[waiter_name]
        except KeyError:
            raise ValueError("Waiter does not exist: %s" % waiter_name)
        return SingleWaiterConfig(single_waiter_config)


class SingleWaiterConfig(object):
    """Represents the waiter configuration for a single waiter.

    A single waiter is considered the configuration for a single
    value associated with a named waiter (i.e TableExists).

    """
    def __init__(self, single_waiter_config):
        self._config = single_waiter_config

        # These attributes are part of the public API.
        self.description = single_waiter_config.get('description', '')
        # Per the spec, these three fields are required.
        self.operation = single_waiter_config['operation']
        self.delay = single_waiter_config['delay']
        self.max_attempts = single_waiter_config['maxAttempts']

    @property
    def acceptors(self):
        acceptors = []
        for acceptor_config in self._config['acceptors']:
            acceptor = AcceptorConfig(acceptor_config)
            acceptors.append(acceptor)
        return acceptors


class AcceptorConfig(object):
    def __init__(self, config):
        self.state = config['state']
        self.matcher = config['matcher']
        self.expected = config['expected']
        self.argument = config.get('argument')
        self.matcher_func = self._create_matcher_func()

    def _create_matcher_func(self):
        # An acceptor function is a callable that takes a single value.  The
        # parsed AWS response.  Note that the parsed error response is also
        # provided in the case of errors, so it's entirely possible to
        # handle all the available matcher capabilities in the future.
        # There's only three supported matchers, so for now, this is all
        # contained to a single method.  If this grows, we can expand this
        # out to separate methods or even objects.

        if self.matcher == 'path':
            return self._create_path_matcher()
        elif self.matcher == 'pathAll':
            return self._create_path_all_matcher()
        elif self.matcher == 'pathAny':
            return self._create_path_any_matcher()
        elif self.matcher == 'status':
            return self._create_status_matcher()
        elif self.matcher == 'error':
            return self._create_error_matcher()
        else:
            raise WaiterConfigError(
                error_msg="Unknown acceptor: %s" % self.matcher)

    def _create_path_matcher(self):
        expression = jmespath.compile(self.argument)
        expected = self.expected

        def acceptor_matches(response):
            return expression.search(response) == expected
        return acceptor_matches

    def _create_path_all_matcher(self):
        expression = jmespath.compile(self.argument)
        expected = self.expected

        def acceptor_matches(response):
            result = expression.search(response)
            if not isinstance(result, list) or not result:
                # pathAll matcher must result in a list.
                # Also we require at least one element in the list,
                # that is, an empty list should not result in this
                # acceptor match.
                return False
            for element in result:
                if element != expected:
                    return False
            return True
        return acceptor_matches

    def _create_path_any_matcher(self):
        expression = jmespath.compile(self.argument)
        expected = self.expected

        def acceptor_matches(response):
            result = expression.search(response)
            if not isinstance(result, list) or not result:
                # pathAny matcher must result in a list.
                # Also we require at least one element in the list,
                # that is, an empty list should not result in this
                # acceptor match.
                return False
            for element in result:
                if element == expected:
                    return True
            return False
        return acceptor_matches

    def _create_status_matcher(self):
        expected = self.expected

        def acceptor_matches(response):
            # We don't have any requirements on the expected incoming data
            # other than it is a dict, so we don't assume there's
            # a ResponseMetadata.HTTPStatusCode.
            status_code = response.get('ResponseMetadata', {}).get(
                'HTTPStatusCode')
            return status_code == expected
        return acceptor_matches

    def _create_error_matcher(self):
        expected = self.expected

        def acceptor_matches(response):
            # When the client encounters an error, it will normally raise
            # an exception.  However, the waiter implementation will catch
            # this exception, and instead send us the parsed error
            # response.  So response is still a dictionary, and in the case
            # of an error response will contain the "Error" and
            # "ResponseMetadata" key.
            return response.get("Error", {}).get("Code", "") == expected
        return acceptor_matches


class Waiter(object):
    def __init__(self, name, config, operation_method):
        """

        :type name: string
        :param name: The name of the waiter

        :type config: botocore.waiter.SingleWaiterConfig
        :param config: The configuration for the waiter.

        :type operation_method: callable
        :param operation_method: A callable that accepts **kwargs
            and returns a response.  For example, this can be
            a method from a botocore client.

        """
        self._operation_method = operation_method
        # The two attributes are exposed to allow for introspection
        # and documentation.
        self.name = name
        self.config = config

    @asyncio.coroutine
    def wait(self, **kwargs):
        acceptors = list(self.config.acceptors)
        current_state = 'waiting'
        sleep_amount = self.config.delay
        num_attempts = 0
        max_attempts = self.config.max_attempts

        while True:
            response = yield from self._operation_method(**kwargs)
            num_attempts += 1
            for acceptor in acceptors:
                if acceptor.matcher_func(response):
                    current_state = acceptor.state
                    break
            else:
                # If none of the acceptors matched, we should
                # transition to the failure state if an error
                # response was received.
                if 'Error' in response:
                    # Transition to the failure state, which we can
                    # just handle here by raising an exception.
                    raise WaiterError(name=self.name,
                                      reason='Unexpected error encountered.')
            if current_state == 'success':
                logger.debug("Waiting complete, waiter matched the "
                             "success state.")
                return
            if current_state == 'failure':
                raise WaiterError(
                    name=self.name,
                    reason='Waiter encountered a terminal failure state')
            if num_attempts >= max_attempts:
                raise WaiterError(name=self.name,
                                  reason='Max attempts exceeded')
            yield from asyncio.sleep(sleep_amount)