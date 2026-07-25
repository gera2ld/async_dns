import asyncio


def get_or_create_event_loop():
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop


def async_test(fn):
    def wrapped(*k, **kw):
        loop = get_or_create_event_loop()
        return loop.run_until_complete(fn(*k, **kw))

    return wrapped
