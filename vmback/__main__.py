#!/usr/bin/env python3

import argparse
import os
import sys
import pathlib

from dotenv import dotenv_values

from .config import Config
from .misc import *
from .pool import pool_backup

def main(args):
    log(f'Using config file: {args.conf}')

    conf = get_conf(args.conf)
    if conf is None:
        return -1

    username = None
    password = None
    env = dotenv_values('.env')
    if 'XEN_USERNAME' in env:
        username = env['XEN_USERNAME']
    if 'XEN_PASSWORD' in env:
        password = env['XEN_PASSWORD']

    if username is None or password is None:
        log('*** FATAL: Missing username or password')
        return -1
    conf.add('auth', { 'username': username, 'password': password })

    prev_path = None
    if 'backup_location' in conf['env']:
        path = conf['env']['backup_location']
        if pathlib.Path(path).exists():
            prev_path = os.getcwd()
            os.chdir(path)

    log(f'Backup location: {os.getcwd()}')
    if not os.access(os.getcwd(), os.W_OK):
        log('*** FATAL: Location is not writable')
        return -1

    if 'pools' in conf:
        pools = conf['pools']
        for pool in pools:
            try:
                pool_backup(pool, conf)
            except Exception as err:
                print(f'Unexpected {err=}, {type(err)=}')

    if prev_path is not None:
        os.chdir(prev_path)

    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog='vmback', description='Backup Xen VMs')
    parser.add_argument('-c', '--config', dest='conf', default='config.yaml', help='Specify a config .yaml file')
    args = parser.parse_args()
    sys.exit(main(args))
