Changelog
=========

0.0.6 (2019-04-11)
------------------
- changed documentation slightly

0.0.5 (2019-04-10)
------------------
- r10k_webhook may accept branch and list of servers as cli args. Also port is parametrized.
- changed defaults: host is '0.0.0.0', flush_env_cache is True
- added documentation

0.0.4 (2019-04-04)
------------------
- Run generating environments with parameter 'codedir'.
- Remove date from logging. It's already presented by journald.
- Cleaning r10k_tmpcfg at exit.
- Removed import http.client.RemoteDisconnected from hook.
- Added feature of flushing cache via puppetserver api. But seems it's only required for old versions of r10k.

0.0.3 (2019-04-03)
------------------
- made compatible with Python 3.4
- adjusted unit file
- added parameter for path of puppet binary

0.0.2 (2019-04-02)
------------------
- added MANIFEST.in.

0.0.1 (2019-03-26)
------------------
- inited the package.
