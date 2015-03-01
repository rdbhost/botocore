__author__ = 'David'

import random
import time
import functools
import asyncio

from yieldfrom.requests import adapters
from yieldfrom.requests.exceptions import ConnectionError
from botocore.compat import six
import botocore.session
import botocore.auth
import botocore.credentials
import yieldfrom.requests as requests

BUCKET_NAME = 'botocoretest%s-%s' % (1, 1)  # (int(time.time()), random.randint(1, 1000))
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
def create_bucket():

    session = botocore.session.get_session()
    service = yield from session.get_service('s3')
    region = 'us-east-1'
    endpoint = service.get_endpoint(region)

    operation = service.get_operation('CreateBucket')
    location = {'LocationConstraint': BUCKET_LOCATION}
    response = yield from operation.call(endpoint, bucket=BUCKET_NAME,
        create_bucket_configuration=location)
    assert response[0].status_code == 200



if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(create_bucket())

