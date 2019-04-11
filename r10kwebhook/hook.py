#!/usr/bin/env python3
import json
from urllib.request import Request, urlopen
from multiprocessing.pool import ThreadPool
from urllib.error import URLError, HTTPError
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter


class MgmtServer(object):

    def __init__(self, fqdn, port):
        self.name = fqdn.split('.')[0]
        self._api_url = 'http://{}:{}/api'.format(fqdn, port)

    def _get_request(self, data):
        return Request(self._api_url, data.encode(), {'Content-Type': 'application/json'})

    def _execute(self, request):
        try:
            return urlopen(request).read().decode()
        except (URLError, HTTPError):
            return 'err'

    def deploy_ref(self, ref):
        return self._execute(self._get_request(json.dumps({'ref': ref})))


def deploy(ref, servers, port):
    pool = ThreadPool(processes=min(len(servers), 10))
    servers = [MgmtServer(fqdn, port) for fqdn in set(servers)]
    results = [pool.apply_async(srv.deploy_ref, (ref,)) for srv in servers]
    counter = [0, 0]
    for result in results:
        response = result.get()
        if response == 'ok':
            counter[0] += 1
        if response == 'wait':
            counter[1] += 1
    return counter


def main():
    parser = ArgumentParser(formatter_class=ArgumentDefaultsHelpFormatter)
    parser.add_argument('-b', '--branch', default=None, help='Branch to deploy')
    parser.add_argument('-p', '--port', default=8088, type=int, help='Port of server application')
    srvs = parser.add_mutually_exclusive_group(required=True)
    srvs.add_argument('-s', '--server', default=None, help='One or more servers', nargs='+')
    srvs.add_argument('--servers_file', default=None, help='Path to json file containing list of servers')
    args = parser.parse_args()
    if args.servers_file:
        with open(args.servers_file, 'r') as f:
            servers = json.loads(f.read())
    else:
        servers = args.server
    if args.branch:
        ref = args.branch
    else:
        ref = input().split()[2]
    deployed, triggered = deploy(ref, servers, args.port)
    if triggered:
        print('Triggered deployment of the branch at {} servers out of {}.'.format(triggered, len(servers)))
    if deployed:
        print('Deployed the branch to {} servers out of {}.'.format(deployed, len(servers)))


if __name__ == '__main__':
    main()
