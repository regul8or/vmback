#!/usr/bin/env python3

import argparse
import sys

def main(args)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog='vmback', description='Backup Xen VMs')
    parser.add_argument('-m', '--mode', dest='mode', choices=['collect', 'broadcast', 'test'], help='Mode of operations: collect weather data or broadcast collected')
    parser.add_argument('-s', '--ssl', dest='ssl', action='store_true', default=False, help='Connect to broker using SSL')
    args = parser.parse_args()
    ret = -1
    if args.mode is not None:
        if args.mode == 'collect':
            ret = collect()
        elif args.mode == 'broadcast':
            ret = broadcast(args.ssl)
        elif args.mode == 'test':
            ret = test(args.ssl)
        else:
            ret = -1
    else:
        parser.print_help()
        ret = -1
    sys.exit(ret)
