#!/usr/bin/env python
# coding=utf-8
import os
from . import utils

try:
    utils.get_servers()
except:
    pass

if os.name == 'nt':
    utils.hosts = utils.Hosts(r'C:\Windows\System32\drivers\etc\hosts')
elif os.name == 'posix':
    utils.hosts = utils.Hosts('/etc/hosts')
