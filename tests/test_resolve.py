#!/usr/bin/env python
# coding=utf-8
import base
from pydns import client

resolver = client.Resolver()
print(resolver.query('gerald.top'))
print(resolver.query_ip('gerald.top'))
