'''
Script to resolve hostnames.
'''
import argparse
import asyncio
from .. import *
from . import ProxyResolver

def _parse_args():
    parser = argparse.ArgumentParser(description='Async DNS resolver')
    parser.add_argument('hostnames', nargs='+', help='the hostnames to query')
    parser.add_argument(
        '-p', '--protocol', choices=['udp', 'tcp'], default='udp',
        help='whether to use TCP protocol as default to query remote servers')
    parser.add_argument('-n', '--nameservers', nargs='+', help='name servers')
    return parser.parse_args()

async def resolve_hostname(resolver, hostname):
    '''Resolve a hostname with the given resolver.'''
    addr = address.Address(hostname, allow_domain=True)
    if addr.ip_type is None:
        return await resolver.query(hostname, types.A)
    else:
        res = DNSMessage()
        res.qd.append(Record(REQUEST, name=hostname, qtype=addr.ip_type))
        res.an.append(Record(qtype=addr.ip_type, data=hostname))
        return res

def resolve_hostnames(args):
    '''Resolve hostnames passed from process arguments.'''
    resolver = ProxyResolver(args.protocol)
    if args.nameservers:
        resolver.set_proxies(args.nameservers)
    results = []
    for hostname in args.hostnames:
        results.append(resolve_hostname(resolver, hostname))
    loop = asyncio.get_event_loop()
    wait = asyncio.wait(results, timeout=3, loop=loop)
    done, _ = loop.run_until_complete(wait)
    for fut in done:
        res = fut.result()
        hostname = res.qd[0].name
        for item in res.an:
            print(hostname, '=>[%s]' % types.get_name(item.qtype), item.data)

resolve_hostnames(_parse_args())
