import asyncio
import ipaddress
import unittest
from unittest.mock import (
    Mock,
    call,
)

from aiofastforward import (
    FastForward,
)

from aiodnsresolver import (
    types,
    Resolver,
    deduplicate_concurrent,
    timeout,
)


def async_test(func):
    def wrapper(*args, **kwargs):
        future = func(*args, **kwargs)
        loop = asyncio.get_event_loop()
        loop.run_until_complete(future)
    return wrapper


def until_called(num_times):
    num_times_called = 0
    future = asyncio.Future()

    def func():
        nonlocal num_times_called
        num_times_called += 1
        if num_times_called == num_times:
            future.set_result(None)
        return future

    return func


class TestResolver(unittest.TestCase):

    @async_test
    async def test_a_query(self):
        resolve = Resolver()
        res = await resolve('www.google.com', types.A)
        self.assertEqual(res.an[0].name, 'www.google.com')
        self.assertIsInstance(ipaddress.ip_address(res.an[0].data), ipaddress.IPv4Address)

    @async_test
    async def test_a_query_twice_sequential(self):
        resolve = Resolver()
        res_a = await resolve('www.google.com', types.A)
        self.assertIsInstance(ipaddress.ip_address(res_a.an[0].data), ipaddress.IPv4Address)

        res_b = await resolve('www.google.com', types.A)
        self.assertIsInstance(ipaddress.ip_address(res_b.an[0].data), ipaddress.IPv4Address)

    @async_test
    async def test_a_query_twice_concurrent(self):
        resolve = Resolver()
        res_a = asyncio.ensure_future(resolve('www.google.com', types.A))
        res_b = asyncio.ensure_future(resolve('www.google.com', types.A))
        self.assertIsInstance(ipaddress.ip_address((await res_a).an[0].data), ipaddress.IPv4Address)
        self.assertIsInstance(ipaddress.ip_address((await res_b).an[0].data), ipaddress.IPv4Address)

    @async_test
    async def test_a_query_different_concurrent(self):
        resolve = Resolver()
        res_a = asyncio.ensure_future(resolve('www.google.com', types.A))
        res_b = asyncio.ensure_future(resolve('charemza.name', types.A))
        self.assertIsInstance(ipaddress.ip_address((await res_a).an[0].data), ipaddress.IPv4Address)
        self.assertIsInstance(ipaddress.ip_address((await res_b).an[0].data), ipaddress.IPv4Address)

    @async_test
    async def test_aaaa_query(self):
        resolve = Resolver()
        res = await resolve('www.google.com', types.AAAA)
        self.assertEqual(res.an[0].name, 'www.google.com')
        self.assertIsInstance(ipaddress.ip_address(res.an[0].data), ipaddress.IPv6Address)

    @async_test
    async def test_a_query_not_exists(self):
        resolve = Resolver()
        res = await resolve('doenotexist.charemza.name', types.A)
        self.assertEqual(len(res.an), 0)

    @async_test
    async def test_aaaa_query_not_exists(self):
        resolve = Resolver()
        res = await resolve('doenotexist.charemza.name', types.AAAA)
        self.assertEqual(len(res.an), 0)

    @async_test
    async def test_a_query_cname(self):
        resolve = Resolver()
        res = await resolve('support.dnsimple.com', types.A)
        self.assertEqual(res.an[0].name, 'support.dnsimple.com')
        self.assertIsInstance(ipaddress.ip_address(res.an[1].data), ipaddress.IPv4Address)


class TestDeduplicate(unittest.TestCase):

    @async_test
    async def test_identical_concurrent_deduplicated_coroutine(self):
        loop = asyncio.get_event_loop()
        mock = Mock()

        async def func(*args, **kwargs):
            mock(*args, **kwargs)
            # Yield so the other task can run
            await asyncio.sleep(0)
            return 'value'

        deduplicated = deduplicate_concurrent(func)

        task_a = asyncio.ensure_future(deduplicated(10, 20, a='val_a', b='val_b'))
        task_b = asyncio.ensure_future(deduplicated(10, 20, a='val_a', b='val_b'))

        task_a_result = await task_a
        task_b_result = await task_b
        self.assertEqual(task_a_result, 'value')
        self.assertEqual(task_b_result, 'value')
        self.assertEqual(mock.mock_calls, [call(10, 20, a='val_a', b='val_b')])

    @async_test
    async def test_identical_concurrent_deduplicated_future(self):
        loop = asyncio.get_event_loop()
        mock = Mock()
        future = asyncio.Future()

        def func(*args, **kwargs):
            mock(*args, **kwargs)
            return future

        deduplicated = deduplicate_concurrent(func)

        task_a = asyncio.ensure_future(deduplicated(10, 20, a='val_a', b='val_b'))
        task_b = asyncio.ensure_future(deduplicated(10, 20, a='val_a', b='val_b'))

        await asyncio.sleep(0)
        future.set_result('value')

        task_a_result = await task_a
        task_b_result = await task_b
        self.assertEqual(task_a_result, 'value')
        self.assertEqual(task_b_result, 'value')
        self.assertEqual(mock.mock_calls, [call(10, 20, a='val_a', b='val_b')])

    @async_test
    async def test_different_concurrent_not_deduplicated(self):
        loop = asyncio.get_event_loop()
        mock = Mock()
        func_done = asyncio.Event()
        until_called_twice = until_called(num_times=2)

        async def func(*args, **kwargs):
            mock(*args, **kwargs)
            await until_called_twice()
            return 'value'

        deduplicated = deduplicate_concurrent(func)

        task_a = asyncio.ensure_future(deduplicated(10, 20, a='val_a', b='val_b'))
        task_b = asyncio.ensure_future(deduplicated(10, 20, a='val_a', b='val_d'))

        task_a_result = await task_a
        task_b_result = await task_b
        self.assertEqual(task_a_result, 'value')
        self.assertEqual(task_b_result, 'value')
        self.assertEqual(mock.mock_calls, [
            call(10, 20, a='val_a', b='val_b'),
            call(10, 20, a='val_a', b='val_d'),
        ])

    @async_test
    async def test_identical_sequential_not_deduplicated(self):
        loop = asyncio.get_event_loop()
        mock = Mock()

        async def func(*args, **kwargs):
            mock(*args, **kwargs)
            return 'value'

        deduplicated = deduplicate_concurrent(func)

        task_a = asyncio.ensure_future(deduplicated(10, 20, a='val_a', b='val_b'))
        task_a_result = await task_a

        task_b = asyncio.ensure_future(deduplicated(10, 20, a='val_a', b='val_b'))

        task_b_result = await task_b
        self.assertEqual(task_a_result, 'value')
        self.assertEqual(task_b_result, 'value')
        self.assertEqual(mock.mock_calls, [
            call(10, 20, a='val_a', b='val_b'),
            call(10, 20, a='val_a', b='val_b'),
        ])

    @async_test
    async def test_identical_concurrent_deduplicated_exception(self):
        loop = asyncio.get_event_loop()
        mock = Mock()

        async def func(*args, **kwargs):
            mock(*args, **kwargs)
            # Yield so the other task can run
            await asyncio.sleep(0)
            raise Exception('inner')

        deduplicated = deduplicate_concurrent(func)

        task_a = asyncio.ensure_future(deduplicated(10, 20, a='val_a', b='val_b'))
        task_b = asyncio.ensure_future(deduplicated(10, 20, a='val_a', b='val_b'))

        with self.assertRaisesRegex(Exception, 'inner'):
            await task_a

        with self.assertRaisesRegex(Exception, 'inner'):
            await task_b

        self.assertEqual(mock.mock_calls, [call(10, 20, a='val_a', b='val_b')])

    @async_test
    async def test_identical_concurrent_deduplicated_cancelled(self):
        loop = asyncio.get_event_loop()
        mock = Mock()
        called = asyncio.Event()

        async def func(*args, **kwargs):
            mock(*args, **kwargs)
            called.set()
            await asyncio.Future()

        deduplicated = deduplicate_concurrent(func)

        task_a = asyncio.ensure_future(deduplicated(10, 20, a='val_a', b='val_b'))
        task_b = asyncio.ensure_future(deduplicated(10, 20, a='val_a', b='val_b'))
        await called.wait()
        task_a.cancel()

        with self.assertRaises(asyncio.CancelledError):
            await task_b



class TestTimeout(unittest.TestCase):

    @async_test
    async def test_shorter_than_timeout_not_raises(self):
            loop = asyncio.get_event_loop()

            async def worker():
                with timeout(1):
                    await asyncio.sleep(0.5)

            with FastForward(loop) as forward:
                task = asyncio.ensure_future(worker())

                await forward(0.5)
                await task

    @async_test
    async def test_longer_than_timeout_raises_timeout_error(self):
            loop = asyncio.get_event_loop()

            async def worker():
                with timeout(1):
                    await asyncio.sleep(1.5)

            with FastForward(loop) as forward:
                task = asyncio.ensure_future(worker())

                await forward(1)
                with self.assertRaises(asyncio.TimeoutError):
                    await task

    @async_test
    async def test_cancel_raises_cancelled_error(self):
            loop = asyncio.get_event_loop()

            async def worker():
                with timeout(1):
                    await asyncio.sleep(0.5)

            with FastForward(loop) as forward:
                task = asyncio.ensure_future(worker())

                await forward(0.25)
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await task

    @async_test
    async def test_exception_propagates(self):
            loop = asyncio.get_event_loop()

            async def worker():
                with timeout(2):
                    raise Exception('inner')

            with FastForward(loop) as forward:
                task = asyncio.ensure_future(worker())

                await forward(1)
                with self.assertRaisesRegex(Exception, 'inner'):
                    await task

    @async_test
    async def test_cleanup(self):
            loop = asyncio.get_event_loop()
            cleanup = asyncio.Event()

            async def worker():
                with timeout(1):
                    try:
                        await asyncio.sleep(2)
                    except asyncio.CancelledError:
                        cleanup.set()
                        raise

            with FastForward(loop) as forward:
                task = asyncio.ensure_future(worker())

                await forward(1)
                with self.assertRaises(asyncio.TimeoutError):
                    await task

                self.assertTrue(cleanup.is_set())

    @async_test
    async def test_ignore_timeout(self):
            loop = asyncio.get_event_loop()
            ignored = asyncio.Event()

            async def worker():
                with timeout(1):
                    try:
                        await asyncio.sleep(2)
                    except asyncio.CancelledError:
                        # Swallow the exception
                        pass
                ignored.set()

            with FastForward(loop) as forward:
                task = asyncio.ensure_future(worker())

                await forward(1)
                await task
                self.assertTrue(ignored.is_set())
