from setuptools import setup, find_packages
from os import path

here = path.abspath(path.dirname(__file__))
with open(path.join(here, 'README.rst')) as f:
    long_description = f.read()

setup(
    name='r10k-webhook',
    version='0.1.0',
    description='Wrapper for r10k',
    url='https://github.com/dashcheulov/r10k-webhook',
    long_description=long_description,
    author='Denis Ashcheulov',
    license='GPL-3.0+',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
    ],
    keywords='r10k puppet webhook gitolite git',
    packages=find_packages(),
    data_files=[('/usr/lib/systemd/system', ['r10k-webhook.service'])],
    include_package_data=True,
    install_requires=['pyaml'],
    setup_requires=['pytest-runner'],
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'r10k_daemon=r10kwebhook:App.entry',
            'r10k_webhook=r10kwebhook.hook:main'
        ],
    },
)
