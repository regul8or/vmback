#!/usr/bin/env python3

import argparse
import sys


def main(args):
    print(args)
    return -1

if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog='vmback', description='Backup Xen VMs')
    parser.add_argument('-c', '--config', dest='conf', default='config.yaml', help='Specify a config .yaml file')
    args = parser.parse_args()
    ret = main(args)
    sys.exit(ret)
