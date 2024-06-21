#!/usr/bin/env python3

import argparse
import sys

from .config import Config


def get_conf():
    conf = None
    try:
        conf = Config('config.yaml')
    except Exception as e:
        print(e)
        conf = None
    return conf


def main(args):
    print('Using', args.conf)

    conf = get_conf()
    if conf is None:
        return -1

    for i in conf.get():
        print(i)

    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog='vmback', description='Backup Xen VMs')
    parser.add_argument('-c', '--config', dest='conf', default='config.yaml', help='Specify a config .yaml file')
    args = parser.parse_args()
    ret = main(args)
    sys.exit(ret)
