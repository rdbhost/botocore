__author__ = 'David'

import functools
import time
import random
import asyncio

from yieldfrom.requests import adapters
from yieldfrom.requests.exceptions import ConnectionError
#from botocore.compat import six
import botocore.session
import botocore.auth
import botocore.credentials
import yieldfrom.requests as requests

BUCKET_NAME = 'botocoretest%s-%s' % (2, 2)  # (int(time.time()), random.randint(1, 1000))
BUCKET_LOCATION = 'us-west-2'

def async_test(f):

    testLoop = asyncio.get_event_loop()

    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        coro = asyncio.coroutine(f)
        future = coro(*args, **kwargs)
        testLoop.run_until_complete(future)
    return wrapper

async_test.__test__ = False # not a test


@asyncio.coroutine
def get_bucket_location():

    session = botocore.session.get_session()
    service = yield from session.get_service('s3')
    region = 'us-east-1'
    endpoint = service.get_endpoint(region)

    operation = service.get_operation('GetBucketLocation')
    http, result = yield from operation.call(endpoint, bucket=BUCKET_NAME)
    assert http.status_code == 200
    assert 'LocationConstraint' in result
    # For buckets in us-east-1 (US Classic Region) this will be None
    assert result['LocationConstraint'] == BUCKET_LOCATION


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(get_bucket_location())

