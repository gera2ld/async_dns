#!/usr/bin/env python
# coding=utf-8
import base
from pydns import resolver

print(resolver.query('www.baidu.com'))
print(resolver.query_ip('gerald.top'))
