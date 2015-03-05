__author__ = 'David'

import random
import time
import functools
import asyncio

from yieldfrom.requests import adapters
from yieldfrom.requests.exceptions import ConnectionError
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
def delete_bucket():

    session = botocore.session.get_session()
    session.set_debug_logger()
    service = yield from session.get_service('s3')
    region = 'us-east-1'
    endpoint = service.get_endpoint(region)

    operation = service.get_operation('DeleteBucket')
    response = yield from operation.call(endpoint, bucket=BUCKET_NAME)
    assert response[0].status_code == 204, response[0].status_code



if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(delete_bucket())

