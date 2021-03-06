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

import os
import logging
import asyncio

from yieldfrom.requests.sessions import Session
from yieldfrom.requests.utils import get_environ_proxies
from yieldfrom.requests.exceptions import ConnectionError

from . import response as botoresponse
from . import exceptions as botoexceptions
from .exceptions import UnknownEndpointError
from .exceptions import EndpointConnectionError, BaseEndpointResolverError
from .awsrequest import AWSRequest, create_request_object, prepare_request_dict
from .compat import urljoin, urlsplit, urlunsplit
from .utils import percent_encode_sequence
from .hooks import first_non_none_response
from .response import StreamingBody
from . import parsers
from .utils import is_valid_endpoint_url

from . import request_sessions_fixer
#import time

logger = logging.getLogger(__name__)
DEFAULT_TIMEOUT = 60
NOT_SET = object()


@asyncio.coroutine
def convert_to_response_dict(http_response, operation_model):
    """Convert an HTTP response object to a request dict.

    This converts the requests library's HTTP response object to
    a dictionary.

    :type http_response: botocore.vendored.requests.model.Response
    :param http_response: The HTTP response from an AWS service request.

    :rtype: dict
    :return: A response dictionary which will contain the following keys:
        * headers (dict)
        * status_code (int)
        * body (string or file-like object)

    """
    response_dict = {
        'headers': http_response.headers,
        'status_code': http_response.status_code,
    }
    if response_dict['status_code'] >= 300:
        response_dict['body'] = yield from http_response.content
    elif operation_model.has_streaming_output:
        response_dict['body'] = StreamingBody(
            http_response.raw, response_dict['headers'].get('content-length'))
    else:
        response_dict['body'] = yield from http_response.content
    return response_dict


class PreserveAuthSession(Session):
    def rebuild_auth(self, prepared_request, response):
        pass


class Endpoint(object):
    """
    Represents an endpoint for a particular service in a specific
    region.  Only an endpoint can make requests.

    :ivar service: The Service object that describes this endpoints
        service.
    :ivar host: The fully qualified endpoint hostname.
    :ivar session: The session object.
    """

    def __init__(self, host, endpoint_prefix,
                 event_emitter, proxies=None, verify=True,
                 timeout=DEFAULT_TIMEOUT, response_parser_factory=None):
        self._endpoint_prefix = endpoint_prefix
        self._event_emitter = event_emitter
        self.host = host
        self.verify = verify
        if proxies is None:
            proxies = {}
        self.proxies = proxies
        self.http_session = PreserveAuthSession()
        self.timeout = timeout
        #self._lock = threading.Lock()  # perhaps eliminate
        if response_parser_factory is None:
            response_parser_factory = parsers.ResponseParserFactory()
        self._response_parser_factory = response_parser_factory

    def __repr__(self):
        return '%s(%s)' % (self._endpoint_prefix, self.host)

    @asyncio.coroutine
    def make_request(self, operation_model, request_dict):
        logger.debug("Making request for %s (verify_ssl=%s) with params: %s",
                     operation_model, self.verify, request_dict)
        return (yield from self._send_request(request_dict, operation_model))

    @asyncio.coroutine
    def create_request(self, params, operation_model=None):
        request = create_request_object(params)
        if operation_model:
            event_name = 'request-created.{endpoint_prefix}.{op_name}'.format(
                endpoint_prefix=self._endpoint_prefix,
                op_name=operation_model.name)
            yield from self._event_emitter.emit(event_name, request=request,
                operation_name=operation_model.name)
        prepared_request = self.prepare_request(request)
        return prepared_request

    def _encode_headers(self, headers):
        # In place encoding of headers to utf-8 if they are unicode.
        for key, value in headers.items():
            if isinstance(value, str):
                headers[key] = value.encode('utf-8')

    def prepare_request(self, request):
        self._encode_headers(request.headers)
        return request.prepare()

    @asyncio.coroutine
    def _send_request(self, request_dict, operation_model):
        attempts = 1
        request = yield from self.create_request(request_dict, operation_model)
        response, exception = yield from self._get_response(
            request, operation_model, attempts)
        while (yield from self._needs_retry(attempts, operation_model,
                                response, exception)):
            attempts += 1
            # If there is a stream associated with the request, we need
            # to reset it before attempting to send the request again.
            # This will ensure that we resend the entire contents of the
            # body.
            request.reset_stream()
            # Create a new request when retried (including a new signature).
            request = yield from self.create_request(
                request_dict, operation_model=operation_model)
            response, exception = yield from self._get_response(request, operation_model,
                                                     attempts)

        if exception is not None:
            raise exception
        else:
            return response

    @asyncio.coroutine
    def _get_response(self, request, operation_model, attempts):
        # This will return a tuple of (success_response, exception)
        # and success_response is itself a tuple of
        # (http_response, parsed_dict).
        # If an exception occurs then the success_response is None.
        # If no exception occurs then exception is None.
        try:
            logger.debug("Sending http request: %s", request)
            http_response = yield from self.http_session.send(
                request, verify=self.verify,
                stream=operation_model.has_streaming_output,
                proxies=self.proxies, timeout=self.timeout)
        except ConnectionError as e:
            # For a connection error, if it looks like it's a DNS
            # lookup issue, 99% of the time this is due to a misconfigured
            # region/endpoint so we'll raise a more specific error message
            # to help users.
            if self._looks_like_dns_error(e):
                endpoint_url = e.request.url
                better_exception = EndpointConnectionError(
                    endpoint_url=endpoint_url, error=e)
                return (None, better_exception)
            else:
                return (None, e)
        except Exception as e:
            logger.debug("Exception received when sending HTTP request.",
                         exc_info=True)
            return (None, e)
        # This returns the http_response and the parsed_data.
        response_dict = yield from convert_to_response_dict(http_response,
                                                 operation_model)
        parser = self._response_parser_factory.create_parser(
            operation_model.metadata['protocol'])
        return ((http_response, parser.parse(response_dict,
                                             operation_model.output_shape)),
                None)

    def _looks_like_dns_error(self, e):
        return 'gaierror' in str(e) and e.request is not None

    @asyncio.coroutine
    def _needs_retry(self, attempts, operation_model, response=None,
                     caught_exception=None):
        event_name = 'needs-retry.%s.%s' % (self._endpoint_prefix, operation_model.name)
        responses = yield from self._event_emitter.emit(
            event_name, response=response, endpoint=self,
            operation=operation_model, attempts=attempts,
            caught_exception=caught_exception)
        handler_response = first_non_none_response(responses)
        if handler_response is None:
            return False
        else:
            # Request needs to be retried, and we need to sleep
            # for the specified number of times.
            logger.debug("Response received to retry, sleeping for "
                         "%s seconds", handler_response)
            yield from asyncio.sleep(handler_response)
            return True


class EndpointCreator(object):
    def __init__(self, endpoint_resolver, configured_region, event_emitter):
        self._endpoint_resolver = endpoint_resolver
        self._configured_region = configured_region
        self._event_emitter = event_emitter

    def create_endpoint(self, service_model, region_name=None, is_secure=True,
                        endpoint_url=None, verify=None,
                        response_parser_factory=None):
        if region_name is None:
            region_name = self._configured_region
        # Use the endpoint resolver heuristics to build the endpoint url.
        scheme = 'https' if is_secure else 'http'
        try:
            endpoint = self._endpoint_resolver.construct_endpoint(
                service_model.endpoint_prefix,
                region_name, scheme=scheme)
        except BaseEndpointResolverError:
            if endpoint_url is not None:
                # If the user provides an endpoint_url, it's ok
                # if the heuristics didn't find anything.  We use the
                # user provided endpoint_url.
                endpoint = {'uri': endpoint_url, 'properties': {}}
            else:
                raise

        if endpoint_url is not None:
            # If the user provides an endpoint url, we'll use that
            # instead of what the heuristics rule gives us.
            final_endpoint_url = endpoint_url
        else:
            final_endpoint_url = endpoint['uri']
        if not is_valid_endpoint_url(final_endpoint_url):
            raise ValueError("Invalid endpoint: %s" % final_endpoint_url)
        return self._get_endpoint(
            service_model, final_endpoint_url, verify, response_parser_factory)

    def _get_endpoint(self, service_model, endpoint_url,
                      verify, response_parser_factory):
        endpoint_prefix = service_model.endpoint_prefix
        event_emitter = self._event_emitter
        return self._get_endpoint_complex(endpoint_prefix, endpoint_url,
                                          verify, event_emitter,
                                          response_parser_factory)

    def _get_proxies(self, url):
        # We could also support getting proxies from a config file,
        # but for now proxy support is taken from the environment.
        return get_environ_proxies(url)

    def _get_verify_value(self, verify):
        # This is to account for:
        # https://github.com/kennethreitz/requests/issues/1436
        # where we need to honor REQUESTS_CA_BUNDLE because we're creating our
        # own request objects.
        # First, if verify is not None, then the user explicitly specified
        # a value so this automatically wins.
        if verify is not None:
            return verify
        # Otherwise use the value from REQUESTS_CA_BUNDLE, or default to
        # True if the env var does not exist.
        return os.environ.get('REQUESTS_CA_BUNDLE', True)

    def _get_endpoint_complex(self, endpoint_prefix,
                              endpoint_url, verify,
                              event_emitter,
                              response_parser_factory=None):
        proxies = self._get_proxies(endpoint_url)
        verify = self._get_verify_value(verify)
        return Endpoint(
            endpoint_url,
            endpoint_prefix=endpoint_prefix,
            event_emitter=event_emitter,
            proxies=proxies,
            verify=verify,
            response_parser_factory=response_parser_factory)
