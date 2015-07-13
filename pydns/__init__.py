#!/usr/bin/env python
# coding=utf-8
import os, asyncio
# Compatible with Python 3.4.3-
if not hasattr(asyncio, 'ensure_future'):
	asyncio.ensure_future = asyncio.async

from . import utils

try:
    utils.get_servers()
except:
    pass

if os.name == 'nt':
    utils.hosts = utils.Hosts(r'C:\Windows\System32\drivers\etc\hosts')
elif os.name == 'posix':
    utils.hosts = utils.Hosts('/etc/hosts')
