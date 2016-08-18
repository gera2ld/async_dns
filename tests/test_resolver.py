#!/usr/bin/env python
# coding=utf-8
import unittest, asyncio
from pydns.resolver import AsyncProxyResolver
from pydns import types

class TestResolver(unittest.TestCase):
    def test_query(self):
        loop = asyncio.get_event_loop()
        resolver = AsyncProxyResolver()
        res = loop.run_until_complete(resolver.query('www.baidu.com', types.A))
        self.assertTrue(res.an)
