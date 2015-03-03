__author__ = 'David'

import asyncio
import functools

def async_test(f):

    testLoop = asyncio.get_event_loop()
    #asyncio.set_event_loop(testLoop)

    @functools.wraps(f)
    def wrapper(inst, *args, **kwargs):
        if hasattr(inst, 'set_up'):
            testLoop.run_until_complete(inst.set_up())
        coro = asyncio.coroutine(f)
        future = coro(inst, *args, **kwargs)
        testLoop.run_until_complete(future)
        if hasattr(inst, 'tear_down'):
            testLoop.run_until_complete(inst.tear_down())
        inst._cleanups.reverse()
        for cu in inst._cleanups:
            meth, args, kws = cu
            testLoop.run_until_complete(meth(*args, **kws))
        inst._cleanups = []
    return wrapper

async_test.__test__ = False  # not a test


