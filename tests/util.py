import asyncio


def async_test(fn):
    loop = asyncio.get_event_loop()

    def wrapped(*k, **kw):
        return loop.run_until_complete(fn(*k, **kw))

    return wrapped
