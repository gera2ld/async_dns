'''
Cache module.
'''

import os
from . import logger, types, hosts, Record

__all__ = ['DNSMemCache']

class DNSMemCache(hosts.Hosts):
    '''
    Memory cache for DNS.
    '''
