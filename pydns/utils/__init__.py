#!/usr/bin/env python
# coding=utf-8
import struct, io, os
from .. import types
nameservers = []

def get_name(data, i):
    a = []
    k = None
    while True:
        l = ord(data[i: i + 1])
        i += 1
        if l == 0:
            if k is None: k = i
            break
        elif l >= 0xc0:
            if k is None: k = i + 1
            i = (l - 0xc0) * 256 + ord(data[i: i+1])
            continue
        a.append(data[i: i + l])
        i += l
    return k, b'.'.join(a).decode().lower()

def pack_string(s, b = 'B'):
    if not isinstance(s, bytes):
        s = s.encode()
    l = len(s)
    return struct.pack('%s%ds' % (b, l), l, s)

def get_bits(x, b):
    high = x >> b
    low = x - (high << b)
    return low, high

def type_name(code):
    return types.TYPES.get(code, str(code))

if os.name == 'nt':
    from .nt import get_servers
    host_file = os.path.expandvars(r'%windir%\System32\drivers\etc\hosts')
elif os.name == 'posix':
    from .posix import get_servers
    host_file = '/etc/hosts'
