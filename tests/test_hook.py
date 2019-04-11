#!/usr/bin/env python3
from urllib.request import Request
from r10kwebhook import hook

SERVERS = [
    'fe2-t-stg-1.ae.core.sw',
    'kt-mgmt-2.starfaking.da'
]


def test_requests():
    data = '{"ref": "sampleref"}'
    servers = [hook.MgmtServer(fqdn, 8088) for fqdn in SERVERS]
    requests = [srv._get_request(data) for srv in servers]
    assert [r.full_url for r in requests] == ['http://fe2-t-stg-1.ae.core.sw:8088/api', 'http://kt-mgmt-2.starfaking.da:8088/api']
    assert [r.data for r in requests] == [data.encode(), data.encode()]
