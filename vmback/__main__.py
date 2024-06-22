#!/usr/bin/env python3

import argparse
import sys

from .config import Config
from .misc import *


def main(args):
    print('Using', args.conf)

    conf = get_conf(args.conf)
    if conf is None:
        return -1

    print(conf['mysql'])

    for i in conf:
        print(i)

    if 'db' in conf:
        print(conf['db'])

    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog='vmback', description='Backup Xen VMs')
    parser.add_argument('-c', '--config', dest='conf', default='config.yaml', help='Specify a config .yaml file')
    args = parser.parse_args()
    ret = main(args)
    sys.exit(ret)
