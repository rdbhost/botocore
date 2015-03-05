__author__ = 'David'

import random
import time
import datetime
import functools
import asyncio

from yieldfrom.requests import adapters
from yieldfrom.requests.exceptions import ConnectionError
import botocore.session
import botocore.auth
import botocore.credentials
import yieldfrom.requests as requests
import mock

BUCKET_NAME = 'botocoretest%s-%s' % (1, 1)  # (int(time.time()), random.randint(1, 1000))
#BUCKET_NAME = 'botocoretest1424663228-876'
BUCKET_LOCATION = 'us-west-2'

import botocore.request_sessions_fixer

#import yieldfrom.requests.sessions
#def null_method(self, prep_req=None, resp=None): return
#setattr(yieldfrom.requests.sessions.SessionRedirectMixin, 'rebuild_auth', null_method)


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
    #session.set_debug_logger()
    service = yield from session.get_service('s3')
    region = 'us-east-1'
    endpoint = service.get_endpoint(region)

    operation = service.get_operation('DeleteBucket')
    response = yield from operation.call(endpoint, bucket=BUCKET_NAME)
    assert response[0].status_code == 204, response[0].status_code


@asyncio.coroutine
def _db():
    _n = datetime.datetime.now()
    with mock.patch('botocore.auth.datetime') as _datetime:
        min = 15 * int(_n.minute / 15)
        n = datetime.datetime(_n.year, _n.month, _n.day, _n.hour, min, 1)
        _datetime.datetime.utcnow.return_value = n
        t = time.mktime(n.timetuple())
        with mock.patch('email.utils.time') as _time:
            _time.gmtime.return_value = time.gmtime(t)
            _time.time.return_value = t
            yield from delete_bucket()


import logging
logging.basicConfig(level=logging.DEBUG)

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(_db())

