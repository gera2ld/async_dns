import asyncio


class Memoizer:
    def __init__(self):
        self.data = {}

    def memoize_async(self, key=None):
        data = self.data

        def wrapper(fn):
            async def wrapped(*k, **kw):
                key_str = '' if key is None else key(*k, **kw)
                future = data.get(key_str)
                if future is None:
                    future = asyncio.ensure_future(fn(*k, **kw))
                    data[key_str] = future

                    def clear(_):
                        data.pop(key_str, None)

                    future.add_done_callback(clear)
                return await future

            return wrapped

        return wrapper
