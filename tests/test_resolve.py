#!/usr/bin/env python
# coding=utf-8
import base
from pydns import resolver

rsv = resolver.Resolver()
print(rsv.query('www.baidu.com'))
print(rsv.query_ip('gerald.top'))
