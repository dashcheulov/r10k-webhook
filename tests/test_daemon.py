#!/usr/bin/env python3
import re
import os
import pytest
import r10kwebhook


def test_is_branch_valid():
    class App(object):
        config = r10kwebhook.Settings({'allowed_branches': '^env_[a-zA-Z0-9_]+$'})
        config.allowed_branches = re.compile(config.allowed_branches)

    assert r10kwebhook.App.is_branch_valid(App, 'env_sample')
    assert not r10kwebhook.App.is_branch_valid(App, 'env_Dc-s')
    assert not r10kwebhook.App.is_branch_valid(App, 'sample')
    assert r10kwebhook.App.is_branch_valid(App, 'env_Sam_ple_')
    assert not r10kwebhook.App.is_branch_valid(App, '_env_sample')


def test_r10k_set_config(tmpdir):
    cfg_file = tmpdir.join('tmp_r10k_config.yaml')

    class R10k(object):
        config = {':cachedir': '/tmp/cache/r10k', ':sources': {
            'puppet': {'basedir': '/etc/puppetlabs/code/environments', 'invalid_branches': 'error',
                       'remote': 'dev@git.starfaking.da:puppet-dev'}}}
        _r10_cfgpath = cfg_file.realpath()
        basedirs = dict()

    r10kwebhook.R10k.set_config(R10k)
    assert cfg_file.read() == ''':cachedir: /tmp/cache/r10k
:sources:
  puppet:
    basedir: /etc/puppetlabs/code/environments.webhook
    invalid_branches: error
    remote: dev@git.starfaking.da:puppet-dev
'''
    assert R10k.basedirs == {'/etc/puppetlabs/code/environments': None}

    R10k.config = {':cachedir': '/tmp/cache/r10k', ':sources': {
        'p1': {'basedir': '/etc/puppet1', 'remote': 'dev@git.da:dev', 'prefix': '_env'},
        'p2': {'basedir': '/etc/puppet2', 'remote': 'dev@git.da:dev'},
        'p3': {'basedir': '/etc/puppet3', 'invalid_branches': 'error', 'remote': 'dev@git.da:dev', 'prefix': True}}}
    os.remove(cfg_file.realpath())
    r10kwebhook.R10k.set_config(R10k)
    assert cfg_file.read() == ''':cachedir: /tmp/cache/r10k
:sources:
  p1:
    basedir: /etc/puppet1.webhook
    prefix: _env
    remote: dev@git.da:dev
  p2:
    basedir: /etc/puppet2.webhook
    remote: dev@git.da:dev
  p3:
    basedir: /etc/puppet3.webhook
    invalid_branches: error
    prefix: true
    remote: dev@git.da:dev
'''
    assert R10k.basedirs == {'/etc/puppet1': '_env', '/etc/puppet2': None, '/etc/puppet3': 'p3'}


def test_r10k_rename_branch():
    class R10k(object):
        branch_to_env_map = {'master': 'production', '^env_(.*)$': '\g<1>'}

    assert r10kwebhook.R10k._rename_branch(R10k, 'original_name') == 'original_name'
    assert r10kwebhook.R10k._rename_branch(R10k, 'master') == 'production'
    assert r10kwebhook.R10k._rename_branch(R10k, 'pre_master', 'pre') == 'pre_production'
    assert r10kwebhook.R10k._rename_branch(R10k, 'env_original') == 'original'
    assert r10kwebhook.R10k._rename_branch(R10k, 'env_original', 'pre') == 'pre_original'
    assert r10kwebhook.R10k._rename_branch(R10k, 'pre_env_original', 'pre') == 'pre_original'


def test_metrics():
    assert r10kwebhook.App.flat_dict(
        {'requests': {'rejected': 0, 'accepted': 0}, 'r10k': {'hits': 0, 'errors': 0}}) == {
               'requests.rejected': 0, 'requests.accepted': 0, 'r10k.hits': 0, 'r10k.errors': 0}
