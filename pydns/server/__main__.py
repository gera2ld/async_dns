#!/usr/bin/env python
# coding=utf-8
import argparse, logging
from . import DNSServer
from ..logger import logger

DEFAULT_PROXIES = [
    '114.114.114.114',
    '180.76.76.76',
    '223.5.5.5',
    '223.6.6.6',
]
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
fmt = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
ch.setFormatter(fmt)
logger.addHandler(ch)
parser = argparse.ArgumentParser(description='DNS server by Gerald.')
parser.add_argument('-b', '--bind', default=':',
        help='the address for the server to bind')
parser.add_argument('--hosts', help='the path of a hosts file')
parser.add_argument('-P', '--proxy', nargs='+',
        default=DEFAULT_PROXIES,
        help='the proxy DNS servers')
parser.add_argument('-p', '--protocol', choices=['udp', 'tcp'], default='udp',
        help='whether to use TCP protocol as default to query remote servers')
args = parser.parse_args()
host, _, port = args.bind.rpartition(':')
if not host: host = '0.0.0.0'
if port:
    port = int(port)
else:
    port = 53
DNSServer(host, port, hosts = args.hosts, resolve_protocol = args.protocol, proxies = args.proxy).serve()
