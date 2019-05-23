#!/usr/bin/env python3
import sys
import os
from signal import signal
import time
import logging
import subprocess
import json
import re
from copy import deepcopy
import ssl
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from threading import Lock
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
import yaml
from r10kwebhook import webserver

logger = logging.getLogger(__name__)


class GracefulKiller(object):  # pylint: disable=too-few-public-methods
    """Catch signals to allow graceful shutdown."""

    def __init__(self):
        self.received_signal = self.received_term_signal = False
        self.last_signal = None
        caught_signals = [1, 2, 3, 10, 12, 15]
        for signum in caught_signals:
            signal(signum, self.handler)

    def handler(self, signum, frame):  # pylint: disable=unused-argument,missing-docstring
        self.last_signal = signum
        self.received_signal = True
        if signum in [2, 3, 15]:
            self.received_term_signal = True


class R10k(object):
    """ Wraps utility r10k"""

    def __new__(cls, *args):
        """ Makes singleton """
        if not hasattr(cls, 'instance'):
            cls.instance = super(R10k, cls).__new__(cls)
        return cls.instance

    def __init__(self, settings):
        self.last_run_state = 'ok'
        self.bin = settings.r10k_path
        self.generate_types = settings.generate_types
        try:
            if not self.bin or ' ' in self.bin or ';' in self.bin:  # looks like injection
                raise ValueError
            _name, self.version = subprocess.Popen([self.bin, 'version'], stdout=subprocess.PIPE, bufsize=1,
                                                   universal_newlines=True).stdout.read().strip().split()
            if _name != 'r10k':
                raise ValueError
        except (ValueError, FileNotFoundError):
            logger.error('Unable to find r10k. Set proper path to r10k binary in config, parameter \'r10k_path\'.')
            sys.exit(1)
        logger.info('Using r10k version %s', self.version)
        self.config = settings.r10k_config_path or '/etc/puppetlabs/r10k/r10k.yaml'
        if not os.path.isfile(self.config):
            logger.error('Unable to find config of r10k. Set proper path in parameter \'r10k_config_path\'.')
            sys.exit(1)
        if self.generate_types:
            self.puppet_bin = settings.puppet_path
            try:
                if not self.puppet_bin or ' ' in self.puppet_bin or ';' in self.puppet_bin:  # looks like injection
                    raise ValueError
                version = subprocess.Popen([self.puppet_bin, '-V'], stdout=subprocess.PIPE, bufsize=1,
                                           universal_newlines=True).stdout.read().strip()
            except (ValueError, FileNotFoundError):
                logger.error(
                    'Unable to find puppet. Set proper path to puppet binary in config, parameter \'puppet_path\'.')
                sys.exit(1)
            logger.info('Using puppet version %s', version)
        with open(self.config, 'r') as f:
            self.config = yaml.safe_load(f.read())
        self._r10_cfgpath = settings.r10k_tmpcfg
        if os.path.isfile(self._r10_cfgpath):
            os.remove(self._r10_cfgpath)
        self.args = settings.r10k_args.split()
        self.args.append('--config={}'.format(self._r10_cfgpath))
        self._lock = Lock()
        self._env_shelf = set()
        self.basedirs = dict()
        self.branch_to_env_map = settings.branch_to_env_map
        self.puppet_api = settings.puppet_api_uri if settings.flush_env_cache else None

    def set_config(self):
        if not os.path.isfile(self._r10_cfgpath):
            config = deepcopy(self.config)
            self.basedirs = dict()
            # r10k is going to put envs to temporary dirs, names of which will be appended with '.webhook'
            for source, cfg in config[':sources'].items():
                self.basedirs[cfg['basedir']] = source if cfg.get('prefix') is True else cfg.get('prefix')
                cfg['basedir'] += '.webhook'
            with open(self._r10_cfgpath, 'w') as f:
                f.write(yaml.safe_dump(config))

    def deploy_env(self, name='*'):
        if name in self._env_shelf or '*' in self._env_shelf:
            logger.warning('Requested to deploy branch %s. But it is already in queue.', name)
            return 'wait'
        self._env_shelf.add(name)
        logger.debug('Waiting for lock to deploy branch %s.', name)
        with self._lock:
            self._env_shelf.remove(name)
            logger.info('Deploying branch %s.', name)
            cmd = [self.bin, 'deploy', 'environment'] if name == '*' else [self.bin, 'deploy', 'environment', name]
            self.last_run_state = 'err' if self._exec_cmd(cmd + self.args) != 0 else 'ok'
            if self.last_run_state == 'ok':
                sync_output = self._sync_dirs()
                pack = [val for key, val in sync_output.items()] if name == '*' else [sync_output[name]]
                for basedir, env in pack:
                    if self.generate_types:  # https://puppet.com/docs/puppet/5.5/environment_isolation.html
                        logger.info('Generating types for environment \'%s\'.', env)
                        if self._exec_cmd(
                                (self.puppet_bin, 'generate', 'types', '--environment', env, '--codedir',
                                os.path.dirname(basedir))) != 0:
                            self.last_run_state = 'err'
                    if self.puppet_api:
                        logger.info('Flushing cache of environment %s. %s', env, urlopen(
                            Request('{}/environment-cache?{}'.format(self.puppet_api, urlencode({'environment': env})),
                                    method='DELETE'), context=ssl._create_unverified_context()).read().decode())
        return self.last_run_state

    def _rename_branch(self, name, prefix=None):
        """ rename prefixed branch according to setting branch_to_env_map """
        if prefix:
            name = name.replace('%s_' % prefix, '', 1)
        env = name
        for key, val in self.branch_to_env_map.items():
            if re.match(key, name):
                env = re.sub(key, val, name)
                break
        if prefix:
            return '_'.join((prefix, env))
        return env

    def _sync_dirs(self):
        """ Creates symlink from env in tmp basedir to environment in ultimate basedir. """
        renaming_map = dict()
        for basedir, prefix in self.basedirs.items():
            tmp_basedir = basedir + '.webhook'
            dir_map = dict()
            for src_dir in os.listdir(tmp_basedir):
                dir_map[src_dir] = basedir, self._rename_branch(src_dir, prefix)
            renaming_map.update(dir_map)
            os.makedirs(basedir, exist_ok=True)
            logging.debug('Cleaning symlinks which absent in r10k basedir')
            basedir_expected_content = [val[1] for val in dir_map.values()]
            for dst_dir in os.listdir(basedir):
                if dst_dir not in basedir_expected_content:
                    logger.info('Removing symlink %s', os.path.join(basedir, dst_dir))
                    os.remove(os.path.join(basedir, dst_dir))
            logger.debug('Ensuring existence of corespondent links in basedir')
            for src, dst in dir_map.items():
                if not os.path.islink(os.path.join(*dst)):
                    abs_src, abs_dst = os.path.join(tmp_basedir, src), os.path.join(*dst)
                    logger.info('Adding symlink from %s to %s', abs_src, abs_dst)
                    os.symlink(abs_src, abs_dst, True)
        return renaming_map

    def _exec_cmd(self, args):
        """ Runs external command
        :returns exit code
        """
        self.set_config()
        logger.debug("Executing command: %s", " ".join(args))
        proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=1,
                                universal_newlines=True)
        with proc.stdout:
            for line in proc.stdout:
                msg = line.split('-> ')
                if len(msg) == 2:
                    level, msg = msg
                else:
                    level, msg = 'INFO', msg[0]
                logger.log(logging.getLevelName(level.strip()), '%s -> %s', os.path.basename(args[0]), msg.strip())
        return proc.wait()


class Settings(object):
    """ Container with settings """

    def __init__(self, defaults=None):
        if isinstance(defaults, dict):
            self.__dict__.update(defaults)
        if hasattr(self, 'config_file'):
            config = self.read_config_file(self.config_file)
            if config:
                logger.info('Loading %s keys from %s', len(config), self.config_file)
                self.__dict__.update(config)
            else:
                delattr(self, 'config_file')

    @staticmethod
    def read_config_file(filepath):
        if filepath:
            if os.path.isfile(filepath):
                with open(filepath, 'r') as config_file:
                    content = json.loads(config_file.read())
                return content
            else:
                logger.warning('Cannot find config file %s', filepath)

    def __str__(self):
        return '---\n{}...'.format(json.dumps(self.__dict__, default_flow_style=False))


class App(object):

    def __init__(self):
        parser = ArgumentParser(formatter_class=ArgumentDefaultsHelpFormatter)
        parser.add_argument('-c', '--config_file', default=None, help='Path to json file containing settings')
        parser.add_argument('-rc', '--r10k_config_path', default='/etc/puppetlabs/r10k/r10k.yaml',
                            help='Path to configuration yaml file of r10k')
        parser.add_argument('-d', '--debug', action='store_true', default=False, help='Turn on debug logging')
        args = parser.parse_args()
        logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO, format='%(levelname)s: %(message)s')
        self.config = Settings({
            'config_file': args.config_file,
            'host': '0.0.0.0',
            'port': 8088,
            'r10k_path': 'r10k',
            'puppet_path': '/opt/puppetlabs/bin/puppet',
            'r10k_tmpcfg': '/tmp/r10k.yaml',
            'r10k_args': '-v',
            'r10k_config_path': args.r10k_config_path,
            'allowed_branches': '.*',
            'branch_to_env_map': dict(),
            'generate_types': True,
            'flush_env_cache': True,
            'initial_deployment': True,
            'puppet_api_uri': 'https://localhost:8140/puppet-admin-api/v1'
        })
        self.metrics = {'requests': {'rejected': 0, 'accepted': 0}, 'r10k': {'hits': 0, 'errors': 0}}
        self._r10k = R10k(self.config)
        self._webserver = webserver.WebServer(self.config.host, self.config.port)
        self._webserver.register_handlers(self)
        if isinstance(self.config.allowed_branches, str):
            self.config.allowed_branches = re.compile(self.config.allowed_branches)
        if self.config.initial_deployment:
            if self._r10k.deploy_env() == 'err':
                self.metrics['r10k']['errors'] += 1

    @staticmethod
    def flat_dict(_dict, pkey=''):
        out = dict()
        for key, val in _dict.items():
            if isinstance(val, dict):
                out.update(App.flat_dict(val, key))
            else:
                out['.'.join((pkey, key)) if pkey else key] = val
        return out

    @webserver.path('/status')
    def check_status(self, data):
        return self._r10k.last_run_state

    @webserver.path('/metrics')
    def get_metrics(self, data):
        return '\n'.join(['='.join((k, str(v))) for k, v in self.flat_dict(self.metrics).items()])

    @webserver.path('/api')  # TODO: make REST-ful e.g. '/api/environments/<env>/deploy'
    def do(self, data):
        if 'ref' in data:
            branch = data['ref'].split('/')[-1]
            if self.is_branch_valid(branch):
                self.metrics['requests']['accepted'] += 1
                response = self._r10k.deploy_env(branch)
                if response == 'err':
                    self.metrics['r10k']['errors'] += 1
                else:
                    self.metrics['r10k']['hits'] += 1
                return response
            logger.warning('Branch name \'%s\' is invalid. Check parameter \'allowed_branches\' in config.', branch)
        self.metrics['requests']['rejected'] += 1
        return 'err'

    def run(self):
        killer = GracefulKiller()
        while not killer.received_term_signal:
            if killer.received_signal:
                logger.info("Ignoring signal %s", killer.last_signal)
                killer.received_signal = False
            if not self._webserver.is_alive():
                logger.error('Webserver is stopped. Will try to restart in 5 s')
                time.sleep(5)
                self._webserver = webserver.WebServer()
            time.sleep(0.2)
        logger.info("Received signal %s. Gracefully exiting.", killer.last_signal)
        if os.path.isfile(self.config.r10k_tmpcfg):
            logger.debug('Removing %s', self.config.r10k_tmpcfg)
            os.remove(self.config.r10k_tmpcfg)
        self._webserver.stop()

    def is_branch_valid(self, branch):
        if isinstance(self.config.allowed_branches, list) and branch in self.config.allowed_branches:
            return True
        if self.config.allowed_branches.match(branch):
            return True
        return False

    @classmethod
    def entry(cls):
        return cls().run()
