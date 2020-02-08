'''
This module starts a DNS server according to console arguments.
'''
import argparse
import asyncio
from . import start_server
from ..core import logger, Address

def main():
    '''Start a DNS server from command line.'''
    parser = argparse.ArgumentParser(
        prog='python3 -m async_dns.server',
        description='DNS server by Gerald.')
    parser.add_argument(
        '-b', '--bind', default=':53',
        help='the address for the server to bind')
    parser.add_argument(
        '--hosts', default='local',
        help='the path of a hosts file, `none` to disable hosts, `local` to read from local hosts file')
    parser.add_argument(
        '-x', '--proxy', nargs='*', default=None,
        help='the proxy DNS servers, `none` to serve as a recursive server, `default` to proxy to default nameservers')
    parser.add_argument(
        '-p', '--protocol', choices=['udp', 'tcp'], default='udp',
        help='whether to use TCP protocol as default to query remote servers')
    args = parser.parse_args()
    addr = Address(args.bind, allow_domain=True)
    logger.info('DNS server v2 - by Gerald')
    loop = asyncio.get_event_loop()
    tcpserver, udp_transports, resolver = loop.run_until_complete(start_server(
        host=addr.host, port=addr.port, hosts=args.hosts,
        resolve_protocol=args.protocol, proxies=args.proxy))
    logger.info('%s started', resolver.name)
    if tcpserver is not None:
        for sock in tcpserver.sockets:
            logger.info('Serving on %s, port %d, TCP', *(sock.getsockname()[:2]))
    for transport in udp_transports:
        logger.info('Serving on %s, port %d, UDP', *(transport.get_extra_info('sockname')[:2]))
    loop.run_forever()

main()
