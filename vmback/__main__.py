#!/usr/bin/env python3

import argparse
import sys

from dotenv import dotenv_values


from .config import Config
from .misc import *


def main(args):
    print('Using', args.conf)

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
        print('Missing username or password')
        return -1
    auth = { 'username': username, 'password': password }
    conf.add('auth', auth)

    if 'pools' in conf:
        pools = conf['pools']
        print(pools)
        for pool in pools:
            print(pool)

    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog='vmback', description='Backup Xen VMs')
    parser.add_argument('-c', '--config', dest='conf', default='config.yaml', help='Specify a config .yaml file')
    args = parser.parse_args()
    ret = main(args)
    sys.exit(ret)
