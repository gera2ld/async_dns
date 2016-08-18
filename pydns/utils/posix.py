#!/usr/bin/env python
# coding=utf-8

def get_servers(filename = '/etc/resolv.conf'):
    nameservers = []
    for line in open(filename, 'r'):
        if line.startswith('#'): continue
        parts = line.split()
        if len(parts) < 2: continue
        if parts[0] == 'nameserver':
            nameservers.append(parts[1])
    return nameservers
