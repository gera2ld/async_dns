'''
This module starts a DNS server according to console arguments.
'''
import argparse
import logging
import asyncio
from . import start_server
from .. import logger, address
from ..resolver import ProxyResolver

def _init_logging():
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    fmt = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
    handler.setFormatter(fmt)
    logger.addHandler(handler)

def main():
    '''Start a DNS server from command line.'''
    _init_logging()
    parser = argparse.ArgumentParser(
        prog='python3 -m async_dns.server',
        description='DNS server by Gerald.')
    parser.add_argument(
        '-b', '--bind', default=':53',
        help='the address for the server to bind')
    parser.add_argument('--hosts', help='the path of a hosts file')
    parser.add_argument(
        '-x', '--proxy', nargs='+',
        default=ProxyResolver.DEFAULT_NAMESERVERS,
        help='the proxy DNS servers')
    parser.add_argument(
        '-p', '--protocol', choices=['udp', 'tcp'], default='udp',
        help='whether to use TCP protocol as default to query remote servers')
    args = parser.parse_args()
    addr = address.Address(args.bind, allow_domain=True)
    logger.info('DNS server v2 - by Gerald')
    loop = asyncio.get_event_loop()
    tcpserver, udp_transports = loop.run_until_complete(start_server(
        host=addr.host, port=addr.port, hosts=args.hosts,
        resolve_protocol=args.protocol, proxies=args.proxy))
    if tcpserver is not None:
        for sock in tcpserver.sockets:
            logger.info('Serving on %s, port %d, TCP', *(sock.getsockname()[:2]))
    for transport in udp_transports:
        logger.info('Serving on %s, port %d, UDP', *(transport.get_extra_info('sockname')[:2]))
    loop.run_forever()

main()
