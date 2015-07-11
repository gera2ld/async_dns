#!/usr/bin/env python
# coding=utf-8
import base, logging
from pydns import server, utils

logging.basicConfig(level = logging.INFO)
server.DNSServerProtocol.cache.update(utils.hosts)
server.DNSServerProtocol.cache.parse_file('~/.gerald/hosts')
server.serve()
