#!/usr/bin/env python
# coding=utf-8
TYPES = {
    0: 'NONE',
    1: 'A',
    2: 'NS',
    5: 'CNAME',
    6: 'SOA',
    12: 'PTR',
    15: 'MX',
    28: 'AAAA',
    33: 'SRV',
    255: 'ANY',
}
globals().update(dict(map(lambda item: (item[1], item[0]), TYPES.items())))

def type_name(code):
	return TYPES.get(code, str(code))
