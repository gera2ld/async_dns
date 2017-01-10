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
MAP_TYPES = dict(map(lambda item: (item[1], item[0]), TYPES.items()))
globals().update(MAP_TYPES)
