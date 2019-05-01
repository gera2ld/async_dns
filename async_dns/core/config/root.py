'''
Cache module.
'''

import os
from .. import logger, types, Record

__all__ = [
    'get_name_cache',
    'get_root_servers',
]

CACHE_FILE = os.path.expanduser('~/.async_dns/named.cache.txt')

def get_name_cache(
        url='ftp://rs.internic.net/domain/named.cache',
        filename=CACHE_FILE, timeout=10):
    '''
    Download root nameservers and save cache.
    '''
    from urllib import request
    logger.info('Fetching named.cache...')
    try:
        res = request.urlopen(url, timeout=timeout)
    except:
        logger.warning('Error fetching named.cache')
    else:
        open(filename, 'wb').write(res.read())

def get_root_servers(filename=CACHE_FILE):
    '''
    Load root servers from cache.
    '''
    if not os.path.isfile(filename):
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        get_name_cache(filename=filename)
    # in case failed fetching named.cache
    if not os.path.isfile(filename):
        return
    for line in open(filename, 'r'):
        if line.startswith(';'):
            continue
        parts = line.lower().split()
        if len(parts) < 4:
            continue
        yield Record(
            name=parts[0].rstrip('.'),   # name
            # parts[1] (expires) is ignored
            qtype=types.get_code(parts[2], 0),   # qtype
            data=parts[3].rstrip('.'),   # data
            ttl=-1,
        )
