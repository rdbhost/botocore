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
import logging
import datetime
import hashlib
import math
import binascii
import asyncio

from six import string_types, text_type
import dateutil.parser
from dateutil.tz import tzlocal, tzutc

from botocore.exceptions import InvalidExpressionError, ConfigNotFound
from botocore.compat import json, quote, zip_longest
from yieldfrom import requests
from botocore.compat import OrderedDict


logger = logging.getLogger(__name__)
DEFAULT_METADATA_SERVICE_TIMEOUT = 1
METADATA_SECURITY_CREDENTIALS_URL = (
    'http://169.254.169.254/latest/meta-data/iam/security-credentials/'
)
# These are chars that do not need to be urlencoded.
# Based on rfc2986, section 2.3
SAFE_CHARS = '-._~'


class _RetriesExceededError(Exception):
    """Internal exception used when the number of retries are exceeded."""
    pass


def normalize_url_path(path):
    if not path:
        return '/'
    return remove_dot_segments(path)


def remove_dot_segments(url):
    # RFC 2986, section 5.2.4 "Remove Dot Segments"
    output = []
    while url:
        if url.startswith('../'):
            url = url[3:]
        elif url.startswith('./'):
            url = url[2:]
        elif url.startswith('/./'):
            url = '/' + url[3:]
        elif url.startswith('/../'):
            url = '/' + url[4:]
            if output:
                output.pop()
        elif url.startswith('/..'):
            url = '/' + url[3:]
            if output:
                output.pop()
        elif url.startswith('/.'):
            url = '/' + url[2:]
        elif url == '.' or url == '..':
            url = ''
        elif url.startswith('//'):
            # As far as I can tell, this is not in the RFC,
            # but AWS auth services require consecutive
            # slashes are removed.
            url = url[1:]
        else:
            if url[0] == '/':
                next_slash = url.find('/', 1)
            else:
                next_slash = url.find('/', 0)
            if next_slash == -1:
                output.append(url)
                url = ''
            else:
                output.append(url[:next_slash])
                url = url[next_slash:]
    return ''.join(output)


def validate_jmespath_for_set(expression):
    # Validates a limited jmespath expression to determine if we can set a value
    # based on it. Only works with dotted paths.
    if not expression or expression == '.':
        raise InvalidExpressionError(expression=expression)

    for invalid in ['[', ']', '*']:
        if invalid in expression:
            raise InvalidExpressionError(expression=expression)


def set_value_from_jmespath(source, expression, value, is_first=True):
    # This takes a (limited) jmespath-like expression & can set a value based
    # on it.
    # Limitations:
    # * Only handles dotted lookups
    # * No offsets/wildcards/slices/etc.
    if is_first:
        validate_jmespath_for_set(expression)

    bits = expression.split('.', 1)
    current_key, remainder = bits[0], bits[1] if len(bits) > 1 else ''

    if not current_key:
        raise InvalidExpressionError(expression=expression)

    if remainder:
        if not current_key in source:
            # We've got something in the expression that's not present in the
            # source (new key). If there's any more bits, we'll set the key with
            # an empty dictionary.
            source[current_key] = {}

        return set_value_from_jmespath(
            source[current_key],
            remainder,
            value,
            is_first=False
        )

    # If we're down to a single key, set it.
    source[current_key] = value


class InstanceMetadataFetcher(object):
    def __init__(self, timeout=DEFAULT_METADATA_SERVICE_TIMEOUT,
                 num_attempts=1, url=METADATA_SECURITY_CREDENTIALS_URL):
        self._timeout = timeout
        self._num_attempts = num_attempts
        self._url = url

    @asyncio.coroutine
    def _get_request(self, url, timeout, num_attempts=1):
        for i in range(num_attempts):
            try:
                response = yield from requests.get(url, timeout=timeout)
            except (requests.Timeout, requests.ConnectionError) as e:
                logger.debug("Caught exception while trying to retrieve "
                             "credentials: %s", e, exc_info=True)
            else:
                if response.status_code == 200:
                    return response
        raise _RetriesExceededError()

    @asyncio.coroutine
    def retrieve_iam_role_credentials(self):
        data = {}
        url = self._url
        timeout = self._timeout
        num_attempts = self._num_attempts
        try:
            r = yield from self._get_request(url, timeout, num_attempts)
            if (yield from r.content):
                fields = (yield from r.content).decode('utf-8').split('\n')
                for field in fields:
                    if field.endswith('/'):
                        data[field[0:-1]] = yield from self.retrieve_iam_role_credentials(
                            url + field, timeout, num_attempts)
                    else:
                        rVal = yield from self._get_request(
                            url + field,
                            timeout=timeout,
                            num_attempts=num_attempts)
                        val = (yield from rVal.content).decode('utf-8')
                        if val[0] == '{':
                            val = json.loads(val)
                        data[field] = val
            else:
                rContent = yield from r.content
                logger.debug("Metadata service returned non 200 status code "
                             "of %s for url: %s, content body: %s",
                             r.status_code, url, rContent)
        except _RetriesExceededError:
            logger.debug("Max number of attempts exceeded (%s) when "
                         "attempting to retrieve data from metadata service.",
                         num_attempts)
        # We sort for stable ordering. In practice, this should only consist
        # of one role, but may need revisiting if this expands in the future.
        final_data = {}
        for role_name in sorted(data):
            final_data = {
                'role_name': role_name,
                'access_key': data[role_name]['AccessKeyId'],
                'secret_key': data[role_name]['SecretAccessKey'],
                'token': data[role_name]['Token'],
                'expiry_time': data[role_name]['Expiration'],
            }
        return final_data


def merge_dicts(dict1, dict2):
    """Given two dict, merge the second dict into the first.

    The dicts can have arbitrary nesting.

    """
    for key in dict2:
        if isinstance(dict2[key], dict):
            if key in dict1 and key in dict2:
                merge_dicts(dict1[key], dict2[key])
            else:
                dict1[key] = dict2[key]
        else:
            # At scalar types, we iterate and merge the
            # current dict that we're on.
            dict1[key] = dict2[key]


def parse_key_val_file(filename, _open=open):
    try:
        with _open(filename) as f:
            contents = f.read()
            return parse_key_val_file_contents(contents)
    except OSError as e:
        raise ConfigNotFound(path=filename)


def parse_key_val_file_contents(contents):
    # This was originally extracted from the EC2 credential provider, which was
    # fairly lenient in its parsing.  We only try to parse key/val pairs if
    # there's a '=' in the line.
    final = {}
    for line in contents.splitlines():
        if '=' not in line:
            continue
        key, val = line.split('=', 1)
        key = key.strip()
        val = val.strip()
        final[key] = val
    return final


def percent_encode_sequence(mapping, safe=SAFE_CHARS):
    """Urlencode a dict or list into a string.

    This is similar to urllib.urlencode except that:

    * It uses quote, and not quote_plus
    * It has a default list of safe chars that don't need
      to be encoded, which matches what AWS services expect.

    This function should be preferred over the stdlib
    ``urlencode()`` function.

    :param mapping: Either a dict to urlencode or a list of
        ``(key, value)`` pairs.

    """
    encoded_pairs = []
    if hasattr(mapping, 'items'):
        pairs = mapping.items()
    else:
        pairs = mapping
    for key, value in pairs:
        encoded_pairs.append('%s=%s' % (percent_encode(key),
                                        percent_encode(value)))
    return '&'.join(encoded_pairs)


def percent_encode(input_str, safe=SAFE_CHARS):
    """Urlencodes a string.

    Whereas percent_encode_sequence handles taking a dict/sequence and
    producing a percent encoded string, this function deals only with
    taking a string (not a dict/sequence) and percent encoding it.

    """
    if not isinstance(input_str, string_types):
        input_str = text_type(input_str)
    return quote(text_type(input_str).encode('utf-8'), safe=safe)


def parse_timestamp(value):
    """Parse a timestamp into a datetime object.

    Supported formats:

        * iso8601
        * rfc822
        * epoch (value is an integer)

    This will return a ``datetime.datetime`` object.

    """
    if isinstance(value, (int, float)):
        # Possibly an epoch time.
        return datetime.datetime.fromtimestamp(value, tzlocal())
    else:
        try:
            return datetime.datetime.fromtimestamp(float(value), tzlocal())
        except (TypeError, ValueError):
            pass
    try:
        return dateutil.parser.parse(value)
    except (TypeError, ValueError) as e:
        raise ValueError('Invalid timestamp "%s": %s' % (value, e))


def parse_to_aware_datetime(value):
    """Converted the passed in value to a datetime object with tzinfo.

    This function can be used to normalize all timestamp inputs.  This
    function accepts a number of different types of inputs, but
    will always return a datetime.datetime object with time zone
    information.

    The input param ``value`` can be one of several types:

        * A datetime object (both naive and aware)
        * An integer representing the epoch time (can also be a string
          of the integer, i.e '0', instead of 0).  The epoch time is
          considered to be UTC.
        * An iso8601 formatted timestamp.  This does not need to be
          a complete timestamp, it can contain just the date portion
          without the time component.

    The returned value will be a datetime object that will have tzinfo.
    If no timezone info was provided in the input value, then UTC is
    assumed, not local time.

    """
    # This is a general purpose method that handles several cases of
    # converting the provided value to a string timestamp suitable to be
    # serialized to an http request. It can handle:
    # 1) A datetime.datetime object.
    if isinstance(value, datetime.datetime):
        datetime_obj = value
    else:
        # 2) A string object that's formatted as a timestamp.
        #    We document this as being an iso8601 timestamp, although
        #    parse_timestamp is a bit more flexible.
        datetime_obj = parse_timestamp(value)
    if datetime_obj.tzinfo is None:
        # I think a case would be made that if no time zone is provided,
        # we should use the local time.  However, to restore backwards
        # compat, the previous behavior was to assume UTC, which is
        # what we're going to do here.
        datetime_obj = datetime_obj.replace(tzinfo=tzutc())
    else:
        datetime_obj = datetime_obj.astimezone(tzutc())
    return datetime_obj


def calculate_sha256(body, as_hex=False):
    """Calculate a sha256 checksum.

    This method will calculate the sha256 checksum of a file like
    object.  Note that this method will iterate through the entire
    file contents.  The caller is responsible for ensuring the proper
    starting position of the file and ``seek()``'ing the file back
    to its starting location if other consumers need to read from
    the file like object.

    :param body: Any file like object.  The file must be opened
        in binary mode such that a ``.read()`` call returns bytes.
    :param as_hex: If True, then the hex digest is returned.
        If False, then the digest (as binary bytes) is returned.

    :returns: The sha256 checksum

    """
    checksum = hashlib.sha256()
    for chunk in iter(lambda: body.read(1024 * 1024), b''):
        checksum.update(chunk)
    if as_hex:
        return checksum.hexdigest()
    else:
        return checksum.digest()


def calculate_tree_hash(body):
    """Calculate a tree hash checksum.

    For more information see:

    http://docs.aws.amazon.com/amazonglacier/latest/dev/checksum-calculations.html

    :param body: Any file like object.  This has the same constraints as
        the ``body`` param in calculate_sha256

    :rtype: str
    :returns: The hex version of the calculated tree hash

    """
    chunks = []
    required_chunk_size = 1024 * 1024
    sha256 = hashlib.sha256
    for chunk in iter(lambda: body.read(required_chunk_size), b''):
        chunks.append(sha256(chunk).digest())
    if not chunks:
        return sha256(b'').hexdigest()
    while len(chunks) > 1:
        new_chunks = []
        for first, second in _in_pairs(chunks):
            if second is not None:
                new_chunks.append(sha256(first + second).digest())
            else:
                # We're at the end of the list and there's no pair left.
                new_chunks.append(first)
        chunks = new_chunks
    return binascii.hexlify(chunks[0]).decode('ascii')


def _in_pairs(iterable):
    # Creates iterator that iterates over the list in pairs:
    # for a, b in _in_pairs([0, 1, 2, 3, 4]):
    #     print(a, b)
    #
    # will print:
    # 0, 1
    # 2, 3
    # 4, None
    shared_iter = iter(iterable)
    # Note that zip_longest is a compat import that uses
    # the itertools izip_longest.  This creates an iterator,
    # this call below does _not_ immediately create the list
    # of pairs.
    return zip_longest(shared_iter, shared_iter)


class CachedProperty(object):
    """A read only property that caches the initially computed value.

    This descriptor will only call the provided ``fget`` function once.
    Subsequent access to this property will return the cached value.

    """

    def __init__(self, fget):
        self._fget = fget

    def __get__(self, obj, cls):
        if obj is None:
            return self
        else:
            computed_value = self._fget(obj)
            obj.__dict__[self._fget.__name__] = computed_value
            return computed_value


class ArgumentGenerator(object):
    """Generate sample input based on a shape model.

    This class contains a ``generate_skeleton`` method that will take
    an input shape (created from ``botocore.model``) and generate
    a sample dictionary corresponding to the input shape.

    The specific values used are place holder values. For strings an
    empty string is used, for numbers 0 or 0.0 is used.  The intended
    usage of this class is to generate the *shape* of the input structure.

    This can be useful for operations that have complex input shapes.
    This allows a user to just fill in the necessary data instead of
    worrying about the specific structure of the input arguments.

    Example usage::

        s = botocore.session.get_session()
        ddb = s.get_service_model('dynamodb')
        arg_gen = ArgumentGenerator()
        sample_input = arg_gen.generate_skeleton(
            ddb.operation_model('CreateTable').input_shape)
        print("Sample input for dynamodb.CreateTable: %s" % sample_input)

    """
    def __init__(self):
        pass

    def generate_skeleton(self, shape):
        """Generate a sample input.

        :type shape: ``botocore.model.Shape``
        :param shape: The input shape.

        :return: The generated skeleton input corresponding to the
            provided input shape.

        """
        stack = []
        return self._generate_skeleton(shape, stack)

    def _generate_skeleton(self, shape, stack):
        stack.append(shape.name)
        try:
            if shape.type_name == 'structure':
                return self._generate_type_structure(shape, stack)
            elif shape.type_name == 'list':
                return self._generate_type_list(shape, stack)
            elif shape.type_name == 'map':
                return self._generate_type_map(shape, stack)
            elif shape.type_name == 'string':
                return ''
            elif shape.type_name in ['integer', 'long']:
                return 0
            elif shape.type_name == 'float':
                return 0.0
            elif shape.type_name == 'boolean':
                return True
        finally:
            stack.pop()

    def _generate_type_structure(self, shape, stack):
        if stack.count(shape.name) > 1:
            return {}
        skeleton = OrderedDict()
        for member_name, member_shape in shape.members.items():
            skeleton[member_name] = self._generate_skeleton(member_shape,
                                                            stack)
        return skeleton

    def _generate_type_list(self, shape, stack):
        # For list elements we've arbitrarily decided to
        # return two elements for the skeleton list.
        return [
            self._generate_skeleton(shape.member, stack),
        ]

    def _generate_type_map(self, shape, stack):
        key_shape = shape.key
        value_shape = shape.value
        assert key_shape.type_name == 'string'
        return OrderedDict([
            ('KeyName', self._generate_skeleton(value_shape, stack)),
        ])
