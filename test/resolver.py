#!/usr/bin/env python
# coding=utf-8
from pydns import resolver

def test():
    print(resolver.query('www.baidu.com'))
    print(resolver.query_ip('gerald.top'))
