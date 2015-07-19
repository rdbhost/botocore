#!/usr/bin/env
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

import unittest
import mock
import asyncio
import types

import yieldfrom.botocore
from yieldfrom.botocore import client, exceptions, hooks, retryhandler, translate
from yieldfrom.botocore.credentials import Credentials
from yieldfrom.botocore.exceptions import ParamValidationError
import sys
sys.path.append('..')
from asyncio_test_utils import async_test



class TestAutoGeneratedClient(unittest.TestCase):

    def setUp(self):
        self.service_description = {
            'metadata': {
                'apiVersion': '2014-01-01',
                'endpointPrefix': 'myservice',
                'signatureVersion': 'v4',
                'protocol': 'query'
            },
            'operations': {
                'TestOperation': {
                    'name': 'TestOperation',
                    'http': {
                        'method': 'POST',
                        'requestUri': '/',
                    },
                    'input': {'shape': 'TestOperationRequest'},
                }
            },
            'shapes': {
                'TestOperationRequest': {
                    'type': 'structure',
                    'required': ['Foo'],
                    'members': {
                        'Foo': {'shape': 'StringType'},
                        'Bar': {'shape': 'StringType'},
                    }
                },
                'StringType': {'type': 'string'}
            }
        }
        self.retry_config = {
            "retry": {
                "__default__": {
                    "max_attempts": 5,
                    "delay": {
                        "type": "exponential",
                        "base": "rand",
                        "growth_factor": 2
                    },
                    "policies": {}
                }
            }
        }
        self.loader = mock.Mock()
        self.loader.load_service_model.return_value = self.service_description
        self.loader.load_data.return_value = self.retry_config

        self.credentials = Credentials('access-key', 'secret-key')

        self.endpoint_creator_patch = mock.patch('yieldfrom.botocore.client.EndpointCreator')
        self.endpoint_creator_cls = self.endpoint_creator_patch.start()
        self.endpoint_creator = self.endpoint_creator_cls.return_value

        self.endpoint = mock.Mock()
        self.endpoint.host = 'https://myservice.amazonaws.com'
        rv = asyncio.Future()
        rv.set_result((mock.Mock(status_code=200), {}))
        self.endpoint.make_request.return_value = rv
        self.endpoint_creator.create_endpoint.return_value = self.endpoint

        self.resolver = mock.Mock()
        self.resolver.construct_endpoint.return_value = {
            'properties': {},
            'uri': 'http://foo'
        }

    def tearDown(self):
        self.endpoint_creator_patch.stop()

    def create_client_creator(self, endpoint_creator=None, event_emitter=None,
                              retry_handler_factory=None,
                              retry_config_translator=None,
                              response_parser_factory=None):
        if event_emitter is None:
            event_emitter = hooks.HierarchicalEmitter()
        if retry_handler_factory is None:
            retry_handler_factory = retryhandler
        if retry_config_translator is None:
            retry_config_translator = yieldfrom.botocore.translate

        if endpoint_creator is not None:
            self.endpoint_creator_cls.return_value = endpoint_creator
        creator = client.ClientCreator(
            self.loader, self.resolver, 'user-agent', event_emitter,
            retry_handler_factory, retry_config_translator,
            response_parser_factory)
        return creator

    @async_test
    def test_client_generated_from_model(self):
        creator = self.create_client_creator()
        service_client = yield from creator.create_client(
            'myservice', 'us-west-2', credentials=self.credentials)
        self.assertTrue(hasattr(service_client, 'test_operation'))

    @async_test
    def test_client_create_unicode(self):
        creator = self.create_client_creator()
        service_client = yield from creator.create_client(
            u'myservice', 'us-west-2', credentials=self.credentials)
        self.assertTrue(hasattr(service_client, 'test_operation'))

    @async_test
    def test_client_has_region_name_on_meta(self):
        creator = self.create_client_creator()
        region_name = 'us-west-2'
        self.endpoint.region_name = region_name
        service_client = yield from creator.create_client(
            'myservice', region_name, credentials=self.credentials)
        self.assertEqual(service_client.meta.region_name, region_name)

    @async_test
    def test_client_has_endpoint_url_on_meta(self):
        creator = self.create_client_creator()
        self.endpoint.host = 'https://foo.bar'
        service_client = yield from creator.create_client(
            'myservice', 'us-west-2', credentials=self.credentials)
        self.assertEqual(service_client.meta.endpoint_url,
                         'https://foo.bar')

    @async_test
    def test_api_version_is_passed_to_loader_if_provided(self):
        creator = self.create_client_creator()
        self.endpoint.host = 'https://foo.bar'
        specific_api_version = '2014-03-01'
        yield from creator.create_client(
            'myservice', 'us-west-2', credentials=self.credentials,
            api_version=specific_api_version)
        self.loader.load_service_model.assert_called_with(
            'myservice', 'service-2', api_version=specific_api_version)

    @async_test
    def test_create_client_class_creates_class(self):
        creator = self.create_client_creator()
        client_class = yield from creator.create_client_class('myservice')
        self.assertTrue(hasattr(client_class, 'test_operation'))

    @async_test
    def test_create_client_class_forwards_api_version(self):
        creator = self.create_client_creator()
        specific_api_version = '2014-03-01'
        yield from creator.create_client_class('myservice',
                                    api_version=specific_api_version)
        self.loader.load_service_model.assert_called_with(
            'myservice', 'service-2', api_version=specific_api_version)

    @async_test
    def test_client_uses_region_from_client_config(self):
        client_config = client.Config()
        client_config.region_name = 'us-west-1'
        creator = self.create_client_creator()
        service_client = yield from creator.create_client(
            'myservice', None, client_config=client_config)
        self.assertEqual(service_client.meta.region_name, 'us-west-1')

    @async_test
    def test_client_region_overrides_region_from_client_config(self):
        client_config = client.Config()
        client_config.region_name = 'us-west-1'
        creator = self.create_client_creator()
        service_client = yield from creator.create_client(
            'myservice', 'us-west-2', client_config=client_config)
        self.assertEqual(service_client.meta.region_name, 'us-west-2')

    @async_test
    def test_client_uses_region_from_endpoint_resolver(self):
        resolver_region_override = 'us-east-1'
        self.resolver.construct_endpoint.return_value = {
            'uri': 'https://endpoint.url',
            'properties': {
                'credentialScope': {
                    'region': resolver_region_override,
                }
            }
        }
        creator = self.create_client_creator()
        client = yield from creator.create_client(
            'myservice', 'us-west-2', credentials=self.credentials)
        self.assertEqual(client.meta.region_name, resolver_region_override)

    @async_test
    def test_client_no_uses_region_from_resolver_with_endpoint_url(self):
        resolver_region_override = 'us-east-1'
        self.resolver.construct_endpoint.return_value = {
            'uri': 'https://endpoint.url',
            'properties': {
                'credentialScope': {
                    'region': resolver_region_override,
                }
            }
        }
        creator = self.create_client_creator()
        service_client = yield from creator.create_client(
            'myservice', 'us-west-2', credentials=self.credentials,
            endpoint_url='https://foo')
        self.assertEqual(service_client.meta.region_name, 'us-west-2')

    @async_test
    def test_client_uses_resolver_region_with_endpoint_url_and_no_region(self):
        resolver_region_override = 'us-east-1'
        self.resolver.construct_endpoint.return_value = {
            'uri': 'https://endpoint.url',
            'properties': {
                'credentialScope': {
                    'region': resolver_region_override,
                }
            }
        }
        creator = self.create_client_creator()
        service_client = yield from creator.create_client(
            'myservice', None, credentials=self.credentials,
            endpoint_url='https://foo')
        self.assertEqual(service_client.meta.region_name,
                         resolver_region_override)

    @mock.patch('yieldfrom.botocore.client.RequestSigner')
    @async_test
    def test_client_signature_no_override(self, request_signer):
        creator = self.create_client_creator()
        yield from creator.create_client(
            'myservice', 'us-west-2', credentials=self.credentials,
            scoped_config={})
        request_signer.assert_called_with(
            mock.ANY, mock.ANY, mock.ANY, 'v4', mock.ANY, mock.ANY)

    @mock.patch('yieldfrom.botocore.client.RequestSigner')
    @async_test
    def test_client_signature_override_config_file(self, request_signer):
        creator = self.create_client_creator()
        config = {
            'myservice': {'signature_version': 'foo'}
        }
        yield from creator.create_client(
            'myservice', 'us-west-2', credentials=self.credentials,
            scoped_config=config)
        request_signer.assert_called_with(
            mock.ANY, mock.ANY, mock.ANY, 'foo', mock.ANY, mock.ANY)

    @mock.patch('yieldfrom.botocore.client.RequestSigner')
    def test_client_signature_override_arg(self, request_signer):
        creator = self.create_client_creator()
        config = yieldfrom.botocore.client.Config(signature_version='foo')
        service_client = yield from creator.create_client(
            'myservice', 'us-west-2', credentials=self.credentials,
            client_config=config)
        request_signer.assert_called_with(
            mock.ANY, mock.ANY, mock.ANY, 'foo', mock.ANY, mock.ANY)

    @async_test
    def test_client_method_to_api_mapping(self):
        creator = self.create_client_creator()
        service_client = yield from creator.create_client('myservice', 'us-west-2')
        self.assertEqual(service_client.meta.method_to_api_mapping,
                         {'test_operation': 'TestOperation'})

    @async_test
    def test_anonymous_client_request(self):
        creator = self.create_client_creator()
        config = yieldfrom.botocore.client.Config(signature_version=yieldfrom.botocore.UNSIGNED)
        service_client = yield from creator.create_client('myservice', 'us-west-2', client_config=config)

        response = yield from service_client.test_operation(Foo='one')

        # Make sure a request has been attempted
        self.assertTrue(self.endpoint.make_request.called)

        # Make sure the request parameters do NOT include auth
        # information. The service defined above for these tests
        # uses sigv4 by default (which we disable).
        params = dict((k.lower(), v) for k, v in
                      self.endpoint.make_request.call_args[0][1].items())
        self.assertNotIn('authorization', params)
        self.assertNotIn('x-amz-signature', params)

    def test_client_user_agent_in_request(self):
        creator = self.create_client_creator()
        service_client = yield from creator.create_client(
            'myservice', 'us-west-2')

        service_client.test_operation(Foo='one')

        self.assertTrue(self.endpoint.make_request.called)
        params = dict((k.lower(), v) for k, v in
                      self.endpoint.make_request.call_args[0][1].items())
        self.assertEqual(params['headers']['User-Agent'], 'user-agent')

    def test_client_custom_user_agent_in_request(self):
        creator = self.create_client_creator()
        config = yieldfrom.botocore.client.Config(user_agent='baz')
        service_client = yield from creator.create_client(
            'myservice', 'us-west-2', client_config=config)

        service_client.test_operation(Foo='one')

        self.assertTrue(self.endpoint.make_request.called)
        params = dict((k.lower(), v) for k, v in
                      self.endpoint.make_request.call_args[0][1].items())
        self.assertEqual(params['headers']['User-Agent'], 'baz')

    def test_client_custom_user_agent_extra_in_request(self):
        creator = self.create_client_creator()
        config = yieldfrom.botocore.client.Config(user_agent_extra='extrastuff')
        service_client = yield from creator.create_client(
            'myservice', 'us-west-2', client_config=config)
        service_client.test_operation(Foo='one')
        headers = self.endpoint.make_request.call_args[0][1]['headers']
        self.assertEqual(headers['User-Agent'], 'user-agent extrastuff')

    @async_test
    def test_client_registers_request_created_handler(self):
        # provide future here in lieu of Mock
        event_emitter = mock.Mock()
        rv = asyncio.Future()
        rv.set_result(None)
        event_emitter.emit.return_value = rv
        creator = self.create_client_creator(event_emitter=event_emitter)
        yield from creator.create_client(
            'myservice', 'us-west-2', credentials=self.credentials)
        event_emitter.register.assert_called_with('request-created.myservice',
                                                  mock.ANY)

    @async_test
    def test_client_makes_call(self):
        creator = self.create_client_creator()
        service_client = yield from creator.create_client(
            'myservice', 'us-west-2', credentials=self.credentials)

        self.assertTrue(self.endpoint_creator.create_endpoint.called)

        response = yield from service_client.test_operation(Foo='one', Bar='two')
        self.assertEqual(response, {})

    @async_test
    def test_client_error_message_for_positional_args(self):
        creator = self.create_client_creator()
        service_client = yield from creator.create_client(
            'myservice', 'us-west-2', credentials=self.credentials)
        with self.assertRaisesRegexp(TypeError,
                                     'only accepts keyword arguments') as e:
            yield from service_client.test_operation('foo')

    @mock.patch('yieldfrom.botocore.client.RequestSigner')
    @async_test
    def test_client_signs_call(self, signer_mock):
        creator = self.create_client_creator()
        service_client = yield from creator.create_client(
            'myservice', 'us-west-2', credentials=self.credentials)
        request = mock.Mock()
        request.headers = {}
        request.url = ''

        # Emit the request created event to see if it would be signed.
        # We tested above to ensure this event is registered when
        # a client is created. This prevents testing the entire client
        # call logic.
        yield from service_client.meta.events.emit(
            'request-created.myservice.test_operation', request=request,
            operation_name='test_operation')

        signer_mock.return_value.sign.assert_called_with(
            'test_operation', request)

    @async_test
    def test_client_makes_call_with_error(self):
        error_response = {
            'Error': {'Code': 'code', 'Message': 'error occurred'}
        }
        rv = asyncio.Future()
        rv.set_result((mock.Mock(status_code=400), error_response))
        self.endpoint.make_request.return_value = rv

        creator = self.create_client_creator()

        service_client = yield from creator.create_client(
            'myservice', 'us-west-2', credentials=self.credentials)
        with self.assertRaises(client.ClientError):
            yield from service_client.test_operation(Foo='one', Bar='two')

    @async_test
    def test_client_validates_params(self):
        creator = self.create_client_creator()

        service_client = yield from creator.create_client(
            'myservice', 'us-west-2', credentials=self.credentials)
        with self.assertRaises(ParamValidationError):
            # Missing required 'Foo' param.
            yield from service_client.test_operation(Bar='two')

    @async_test
    def test_client_with_custom_params(self):
        creator = self.create_client_creator()

        yield from creator.create_client('myservice', 'us-west-2',
                              is_secure=False, verify=False)
        self.endpoint_creator.create_endpoint.assert_called_with(
            mock.ANY, 'us-west-2', is_secure=False,
            endpoint_url=None, verify=False,
            response_parser_factory=None)

    @async_test
    def test_client_with_endpoint_url(self):
        creator = self.create_client_creator()

        yield from creator.create_client('myservice', 'us-west-2',
                              endpoint_url='http://custom.foo')
        self.endpoint_creator.create_endpoint.assert_called_with(
            mock.ANY, 'us-west-2', is_secure=True,
            endpoint_url='http://custom.foo', verify=None,
            response_parser_factory=None)

    @async_test
    def test_client_with_response_parser_factory(self):
        factory = mock.Mock()
        creator = self.create_client_creator(response_parser_factory=factory)
        yield from creator.create_client('myservice', 'us-west-2')
        self.endpoint_creator.create_endpoint.assert_called_with(
            mock.ANY, 'us-west-2', is_secure=True,
            endpoint_url=None, verify=None,
            response_parser_factory=factory)

    @async_test
    def test_operation_cannot_paginate(self):
        pagination_config = {
            'pagination': {
                # Note that there's no pagination config for
                # 'TestOperation', indicating that TestOperation
                # is not pageable.
                'SomeOtherOperation': {
                    "input_token": "Marker",
                    "output_token": "Marker",
                    "more_results": "IsTruncated",
                    "limit_key": "MaxItems",
                    "result_key": "Users"
                }
            }
        }
        self.loader.load_service_model.side_effect = [
            self.service_description, pagination_config]
        creator = self.create_client_creator()
        service_client = yield from creator.create_client('myservice', 'us-west-2')
        self.assertFalse(service_client.can_paginate('test_operation'))

    @async_test
    def test_operation_can_paginate(self):
        pagination_config = {
            'pagination': {
                'TestOperation': {
                    "input_token": "Marker",
                    "output_token": "Marker",
                    "more_results": "IsTruncated",
                    "limit_key": "MaxItems",
                    "result_key": "Users"
                }
            }
        }
        self.loader.load_service_model.side_effect = [
            self.service_description, pagination_config]
        creator = self.create_client_creator()
        service_client = yield from creator.create_client('myservice', 'us-west-2')
        self.assertTrue(service_client.can_paginate('test_operation'))
        # Also, the config is cached, but we want to make sure we get
        # the same answer when we ask again.
        self.assertTrue(service_client.can_paginate('test_operation'))

    @async_test
    def test_service_has_no_pagination_configs(self):
        # This is the case where there is an actual *.paginator.json, file,
        # but the specific operation itself is not actually pageable.
        # If the loader cannot load pagination configs, it communicates
        # this by raising a DataNotFoundError.
        self.loader.load_service_model.side_effect = [
            self.service_description,
            exceptions.DataNotFoundError(data_path='/foo')]
        creator = self.create_client_creator()
        service_client = yield from creator.create_client('myservice', 'us-west-2')
        self.assertFalse(service_client.can_paginate('test_operation'))

    @async_test
    def test_waiter_config_uses_service_name_not_endpoint_prefix(self):
        waiter_config = {
            'version': 2,
            'waiters': {}
        }
        self.loader.load_service_model.side_effect = [
            self.service_description,
            waiter_config
        ]
        creator = self.create_client_creator()
        # We're going to verify that the loader loads a service called
        # 'other-service-name', and even though the endpointPrefix is
        # 'myservice', we use 'other-service-name' for waiters/paginators, etc.
        service_client = yield from creator.create_client('other-service-name',
                                               'us-west-2')
        self.assertEqual(service_client.waiter_names, [])
        # Note we're using other-service-name, not
        # 'myservice', which is the endpointPrefix.
        self.loader.load_service_model.assert_called_with(
            'other-service-name', 'waiters-2', '2014-01-01')

    @async_test
    def test_service_has_waiter_configs(self):
        waiter_config = {
            'version': 2,
            'waiters': {
                "Waiter1": {
                    'operation': 'TestOperation',
                    'delay': 5,
                    'maxAttempts': 20,
                    'acceptors': [],
                },
                "Waiter2": {
                    'operation': 'TestOperation',
                    'delay': 5,
                    'maxAttempts': 20,
                    'acceptors': [],
                },
            }
        }
        self.loader.load_service_model.side_effect = [
            self.service_description,
            waiter_config
        ]
        creator = self.create_client_creator()
        service_client = yield from creator.create_client('myservice', 'us-west-2')
        self.assertEqual(sorted(service_client.waiter_names),
                         sorted(['waiter_1', 'waiter_2']))
        self.assertTrue(hasattr(service_client.get_waiter('waiter_1'), 'wait'))

    @async_test
    def test_service_has_no_waiter_configs(self):
        self.loader.load_service_model.side_effect = [
            self.service_description,
            exceptions.DataNotFoundError(data_path='/foo')]
        creator = self.create_client_creator()
        service_client = yield from creator.create_client('myservice', 'us-west-2')
        self.assertEqual(service_client.waiter_names, [])
        with self.assertRaises(ValueError):
            service_client.get_waiter("unknown_waiter")

    @async_test
    def test_service_has_retry_event(self):
        # A retry event should be registered for the service.
        event_emitter = mock.Mock()
        rv = asyncio.Future()
        rv.set_result(None)
        event_emitter.emit.return_value = rv
        creator = self.create_client_creator(event_emitter=event_emitter)
        yield from creator.create_client('myservice', 'us-west-2')

        event_emitter.register.assert_any_call(
            'needs-retry.myservice', mock.ANY,
            unique_id='retry-config-myservice')

    @async_test
    def test_service_creates_retryhandler(self):
        # A retry handler with the expected configuration should be
        # created when instantiating a client.
        retry_handler_factory = mock.Mock()
        creator = self.create_client_creator(
            retry_handler_factory=retry_handler_factory)
        yield from creator.create_client('myservice', 'us-west-2')

        retry_handler_factory.create_retry_handler.assert_called_with({
            '__default__': {
                'delay': {
                    'growth_factor': 2,
                    'base': 'rand',
                    'type': 'exponential'
                },
                'policies': {},
                'max_attempts': 5
            }
        }, 'myservice')

    @async_test
    def test_service_registers_retry_handler(self):
        # The retry handler returned from ``create_retry_handler``
        # that was tested above needs to be set as the handler for
        # the event emitter.
        retry_handler_factory = mock.Mock()
        handler = mock.Mock()
        event_emitter = mock.Mock()
        rv = asyncio.Future()
        rv.set_result(None)
        event_emitter.emit.return_value = rv
        retry_handler_factory.create_retry_handler.return_value = handler

        creator = self.create_client_creator(
            event_emitter=event_emitter,
            retry_handler_factory=retry_handler_factory)
        yield from creator.create_client('myservice', 'us-west-2')

        event_emitter.register.assert_any_call(
            mock.ANY, handler, unique_id=mock.ANY)

    @async_test
    def test_service_retry_missing_config(self):
        # No config means we should never see any retry events registered.
        self.loader.load_data.return_value = {}

        event_emitter = mock.Mock()
        rv = asyncio.Future()
        rv.set_result(None)
        event_emitter.emit.return_value = rv
        creator = self.create_client_creator(event_emitter=event_emitter)
        yield from creator.create_client('myservice', 'us-west-2')

        for call in event_emitter.register.call_args_list:
            self.assertNotIn('needs-retry', call[0][0])

    @async_test
    def test_try_to_paginate_non_paginated(self):
        self.loader.load_service_model.side_effect = [
            self.service_description,
            exceptions.DataNotFoundError(data_path='/foo')
        ]
        creator = self.create_client_creator()
        service_client = yield from creator.create_client('myservice', 'us-west-2')
        with self.assertRaises(exceptions.OperationNotPageableError):
            service_client.get_paginator('test_operation')

    @async_test
    def test_successful_pagination_object_created(self):
        pagination_config = {
            'pagination': {
                'TestOperation': {
                    "input_token": "Marker",
                    "output_token": "Marker",
                    "more_results": "IsTruncated",
                    "limit_key": "MaxItems",
                    "result_key": "Users"
                }
            }
        }
        self.loader.load_service_model.side_effect = [
            self.service_description,
            pagination_config
        ]
        creator = self.create_client_creator()
        service_client = yield from creator.create_client('myservice', 'us-west-2')
        paginator = service_client.get_paginator('test_operation')
        # The pagination logic itself is tested elsewhere (test_paginate.py),
        # but we can at least make sure it looks like a paginator.
        self.assertTrue(hasattr(paginator, 'paginate'))

    @async_test
    def test_can_set_credentials_in_client_init(self):
        creator = self.create_client_creator()
        credentials = Credentials(
            access_key='access_key', secret_key='secret_key',
            token='session_token')
        client = yield from creator.create_client(
            'myservice', 'us-west-2', credentials=credentials)

        # Verify that we create an endpoint with a credentials object
        # matching our creds arguments.
        self.assertEqual(client._request_signer._credentials, credentials)

    @async_test
    def test_event_emitted_when_invoked(self):
        event_emitter = hooks.HierarchicalEmitter()
        creator = self.create_client_creator(event_emitter=event_emitter)

        calls = []
        handler = lambda **kwargs: calls.append(kwargs)
        event_emitter.register('before-call', handler)

        service_client = yield from creator.create_client(
            'myservice', 'us-west-2', credentials=self.credentials)
        yield from service_client.test_operation(Foo='one', Bar='two')
        self.assertEqual(len(calls), 1)

    @async_test
    def test_events_are_per_client(self):
        event_emitter = hooks.HierarchicalEmitter()
        creator = self.create_client_creator(event_emitter=event_emitter)

        first_calls = []
        first_handler = lambda **kwargs: first_calls.append(kwargs)

        second_calls = []
        second_handler = lambda **kwargs: second_calls.append(kwargs)

        first_client = yield from creator.create_client(
            'myservice', 'us-west-2', credentials=self.credentials)
        second_client = yield from creator.create_client(
            'myservice', 'us-west-2', credentials=self.credentials)

        first_client.meta.events.register('before-call', first_handler)
        second_client.meta.events.register('before-call', second_handler)

        # Now, if we invoke an operation from either client, only
        # the handlers registered with the specific client will be invoked.
        # So if we invoke the first client.
        yield from first_client.test_operation(Foo='one', Bar='two')
        # Only first_calls is populated, not second_calls.
        self.assertEqual(len(first_calls), 1)
        self.assertEqual(len(second_calls), 0)

        # If we invoke an operation from the second client,
        # only second_calls will be populated, not first_calls.
        yield from second_client.test_operation(Foo='one', Bar='two')
        # first_calls == 1 from the previous first_client.test_operation()
        # call.
        self.assertEqual(len(first_calls), 1)
        self.assertEqual(len(second_calls), 1)

    @async_test
    def test_clients_inherit_handlers_from_session(self):
        # Even though clients get their own event emitters, they still
        # inherit any handlers that were registered on the event emitter
        # at the time the client was created.
        event_emitter = hooks.HierarchicalEmitter()
        creator = self.create_client_creator(event_emitter=event_emitter)

        # So if an event handler is registered before any clients are created:

        base_calls = []
        #base_handler = lambda **kwargs: base_calls.append(kwargs)
        def base_handler(**kwargs):
            base_calls.append(kwargs)
        event_emitter.register('before-call', base_handler)

        # Then any client created from this point forward from the
        # event_emitter passed into the ClientCreator will have this
        # handler.
        first_client = yield from creator.create_client(
            'myservice', 'us-west-2', credentials=self.credentials)
        yield from first_client.test_operation(Foo='one', Bar='two')
        self.assertEqual(len(base_calls), 1)

        # Same thing if we create another client.
        second_client = yield from creator.create_client(
            'myservice', 'us-west-2', credentials=self.credentials)
        yield from second_client.test_operation(Foo='one', Bar='two')
        self.assertEqual(len(base_calls), 2)

    @async_test
    def test_clients_inherit_only_at_create_time(self):
        # If event handlers are added to the copied event emitter
        # _after_ a client is created, we don't pick those up.
        event_emitter = hooks.HierarchicalEmitter()
        creator = self.create_client_creator(event_emitter=event_emitter)

        # 1. Create a client.
        first_client = yield from creator.create_client(
            'myservice', 'us-west-2', credentials=self.credentials)

        # 2. Now register an event handler from the originating event emitter.
        base_calls = []
        base_handler = lambda **kwargs: base_calls.append(kwargs)
        event_emitter.register('before-call', base_handler)

        # 3. The client will _not_ see this because it already has its
        #    own copy of the event handlers.
        yield from first_client.test_operation(Foo='one', Bar='two')
        self.assertEqual(len(base_calls), 0)

    # @async_test
    # def test_client_can_be_cloned(self):
    #     # Even though we're verifying that clone_client() works, we want
    #     # to avoid testing internal attributes.
    #     # Instead we try to test this via the public API:
    #     #   - Cloning the API with a new endpoint will use the new endopint.
    #     event_emitter = hooks.HierarchicalEmitter()
    #     creator = self.create_client_creator(event_emitter=event_emitter)
    #
    #     rv = asyncio.Future()
    #     rv.set_result((mock.Mock(status_code=200), {'type': 'from-replaced-endpoint'}))
    #     new_endpoint = mock.Mock()
    #     new_endpoint.make_request.return_value = rv
    #
    #     service_client = yield from creator.create_client(
    #         'myservice', 'us-west-2', credentials=self.credentials)
    #     cloned = service_client.clone_client(endpoint=new_endpoint)
    #     response = yield from cloned.test_operation(Foo='one', Bar='two')
    #
    #     self.assertEqual(response['type'], 'from-replaced-endpoint')
    #
    # @async_test
    # def test_client_cloned_has_copied_event_emitter(self):
    #     # We have a specific test for this because this value gets
    #     # mapped to the .meta object, so it has custom behavior.
    #     creator = self.create_client_creator()
    #     original = yield from creator.create_client('myservice', 'us-west-2')
    #
    #     cloned = original.clone_client()
    #     assert not isinstance(cloned, types.GeneratorType)
    #     self.assertTrue(cloned.meta.events is not original.meta.events)

    @async_test
    def test_clients_have_meta_object(self):
        creator = self.create_client_creator()
        service_client = yield from creator.create_client('myservice', 'us-west-2')
        self.assertTrue(hasattr(service_client, 'meta'))
        self.assertTrue(hasattr(service_client.meta, 'events'))
        # Sanity check the event emitter has an .emit() method.
        self.assertTrue(hasattr(service_client.meta.events, 'emit'))

    @async_test
    def test_client_register_seperate_unique_id_event(self):
        event_emitter = hooks.HierarchicalEmitter()
        creator = self.create_client_creator(event_emitter=event_emitter)

        client1 = yield from creator.create_client('myservice', 'us-west-2')
        client2 = yield from creator.create_client('myservice', 'us-west-2')

        def ping(**kwargs):
            return 'foo'

        client1.meta.events.register('some-event', ping, 'my-unique-id')
        client2.meta.events.register('some-event', ping, 'my-unique-id')

        # Ensure both clients can register a function with an unique id
        client1_responses = yield from client1.meta.events.emit('some-event')
        self.assertEqual(len(client1_responses), 1)
        self.assertEqual(client1_responses[0][1], 'foo')

        client2_responses = yield from client2.meta.events.emit('some-event')
        self.assertEqual(len(client2_responses), 1)
        self.assertEqual(client2_responses[0][1], 'foo')

        # Ensure when a client is unregistered the other client has
        # the unique-id event still registered.
        client1.meta.events.unregister('some-event', ping, 'my-unique-id')
        client1_responses = yield from client1.meta.events.emit('some-event')
        self.assertEqual(len(client1_responses), 0)

        client2_responses = yield from client2.meta.events.emit('some-event')
        self.assertEqual(len(client2_responses), 1)
        self.assertEqual(client2_responses[0][1], 'foo')

        # Ensure that the other client can unregister the event
        client2.meta.events.unregister('some-event', ping, 'my-unique-id')
        client2_responses = yield from client2.meta.events.emit('some-event')
        self.assertEqual(len(client2_responses), 0)

    @async_test
    def test_client_created_emits_events(self):
        called = []

        def on_client_create(class_attributes, **kwargs):
            called.append(class_attributes)

        event_emitter = hooks.HierarchicalEmitter()
        event_emitter.register('creating-client-class', on_client_create)

        creator = self.create_client_creator(event_emitter=event_emitter)
        yield from creator.create_client(
            'myservice', 'us-west-2', credentials=self.credentials)

        self.assertEqual(len(called), 1)
        self.assertIn('test_operation', called[0])

    def test_client_method_called_event(self):
        event_emitter = hooks.HierarchicalEmitter()

        def inject_params(params, **kwargs):
            new_params = params.copy()
            new_params['Foo'] = 'zero'
            return new_params

        event_emitter.register(
            'provide-client-params.myservice.TestOperation', inject_params)

        wrapped_emitter = mock.Mock(wraps=event_emitter)
        creator = self.create_client_creator(event_emitter=wrapped_emitter)
        service_client = yield from creator.create_client(
            'myservice', 'us-west-2', credentials=self.credentials)

        params = {'Foo': 'one', 'Bar': 'two'}
        yield from service_client.test_operation(**params)

        # Ensure that the initial params were not modified in the handler
        self.assertEqual(params, {'Foo': 'one', 'Bar': 'two'})

        # Ensure the handler passed on the correct param values.
        body = self.endpoint.make_request.call_args[0][1]['body']
        self.assertEqual(body['Foo'], 'zero')
