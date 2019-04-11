============
R10k webhook
============

Overview
--------

It's the API to `r10k utility <https://github.com/puppetlabs/r10k>`_. With it you can get your puppet code automatically deployed to puppet server after pushing to git. Assumed that you use r10k for deployment puppet environments from git branches and want to get done it automatically after pushing.

Server application works as a daemon, listens at requests and invokes local r10k utility. It's complete wrapper: generates config, launches r10k, controls and performs post-run actions. Client application is launched as VCS hook and calls server application informing about branch which has been pushed.

Features
--------

- Allows **mapping of git branches to puppet environments** using regex. E.g. branch 'master' may be mapped to puppet environment 'production'.
- Accepts **regex pattern by which name of branch is filtered**. A branch will be deployed only if matches regex.
- Runs only **one instance of r10k simultaneously. Deduplicates and keeps all requests in a queue**, so that any request won't be missed.
- **Launches 'generate types'** after r10k for `environment isolation <https://puppet.com/docs/puppet/5.5/environment_isolation.html>`_.
- Sends command **flushing cache** for an environment to api of puppet server after r10k has finished.
- Depends on only one third-party package - pyaml.

Getting started
---------------

Installation at puppet server.
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Firstly, install and set `r10k utility <https://github.com/puppetlabs/r10k>`_ to your repository. Ensure that following command works.

.. code-block:: bash

    r10k deploy environment <env_name> -v

*env_name* has to be name of one of existent branches in your repo.

If you don't have errors, proceed with installation of r10k-webhook.

.. code-block:: bash

    pip3 install r10k-webhook
    systemctl daemon-reload

Enable and start service.

.. code-block:: bash

    systemctl enable r10k-webhook
    systemctl start r10k-webhook

Check logs and status.

.. code-block:: bash

    journalctl -xeu r10k-webhook
    curl localhost:8088/status

If daemon doesn't start, go on with `Configuration`_.

Installation at VCS.
~~~~~~~~~~~~~~~~~~~~

Install the package to server with your repository of puppet code.

.. code-block:: bash

    pip3 install r10k-webhook

Trigger your puppet server with <env_name>.

.. code-block:: bash

    r10k_webhook -s <puppetserver.hostname> -b <env_name>

Take <puppetserver.hostname> and <env_name> as you used at `Installation at puppet server.`_ You should see following output:

.. code-block:: bash

    Deployed the branch to 1 servers out of 1.

It means that your have deployed content of the branch to the directory of environment at puppet server host.

Use with gitolite.
^^^^^^^^^^^^^^^^^^

Create list with servers in json file looks like

.. code-block:: json

    [
      "server1",
      "server2"
    ]

Add a hook to your control repo consists of

.. code-block:: bash

    #!/usr/bin/env bash
    r10k_webhook --servers_file <path_to_servers.json>


Configuration
-------------

Create '/etc/r10k_webhook/config.json' and put there parameters.

- **host** *default: '0.0.0.0'* - Ip-address or hostname, on which http-server listening.
- **port** *default: 8088* - Port, on which http-server listening.
- **branch_to_env_map** *default: {}* - Map of name of branch in VCS and associated name of puppet environment. It may be regexp. E.g. '^env_(.\*)$': '\\g<1>' removes prefix `env_` from all branches having it.
- **allowed_branches** *default: '.\*'* - Regexp by which name of a branch is filtered. A branch will be deployed if matches regexp.
- **flush_env_cache** *default: true* - Determines whether send command flushing an environment's cache via puppet api after r10k run.
- **generate_types** *default: true* - Determines whether launch command '`puppet generate types <env> <https://puppet.com/docs/puppet/5.5/environment_isolation.html>`_' after r10k run.
- **r10k_path**: *default: 'r10k'* - Path to r10k binary
- **puppet_path**: *default: '/opt/puppetlabs/bin/puppet'* - Path to puppet binary
- **r10k_tmpcfg**: *default: '/tmp/r10k.yaml'* - Path to modified configuration yaml file of r10k being created and used by wrapper.
- **r10k_args**: *default: '-v'* - String with arguments are passed to r10k at every execution. Spaces are not allowed there.
- **r10k_config_path**: *default: '/etc/puppetlabs/r10k/r10k.yaml'* - Path to configuration yaml file of r10k.
- **puppet_api_uri** *default: 'https://localhost:8139/puppet-admin-api/v1'* - URI is called to flush cache of an environment.

Service r10k-webhook has to be restarted in order to apply changes of config::

    systemctl restart r10k-webhook

Example of configuration file.
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: json

    {
      "flush_env_cache": false,
      "branch_to_env_map": {
        "master": "production",
        "^env_(.*)$": "\g<1>"
      },
      "allowed_branches": "^(env_[\w]+|master)$"
    }

Example of configuration file of r10k.
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: yaml

    :cachedir: /opt/puppetlabs/puppet/cache/r10k
    :sources:
      puppet:
        basedir: /etc/puppetlabs/code/environments
        invalid_branches: error
        remote: git@git.example.net:puppet
