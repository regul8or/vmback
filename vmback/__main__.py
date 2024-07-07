#!/usr/bin/env python3

import argparse
import sys

from .backup import backup
from .list_vm import list_vm
from .list_vdi import list_vdi
from .misc import *

"""
    Some links:
        https://github.com/NAUbackup/VmBackup/blob/master/VmBackup.py
        https://xapi-project.github.io/xen-api/usage.html
        https://xapi-project.github.io/xen-api/classes/pool.html
        https://docs.xenserver.com/en-us/citrix-hypervisor/command-line-interface.html
        https://docs.xenserver.com/en-us/citrix-hypervisor/vms/import-export.html
        https://github.com/xapi-project/xen-api/blob/master/scripts/examples/python/exportimport.py
        https://docs.xenserver.com/en-us/xenserver/8/dr/backup.html
        https://docs.xenserver.com/en-us/xenserver/developer/sdk-guide/python
        https://docs.xenserver.com/en-us/xenserver/developer/sdk-guide/using-http
"""


if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog='vmback', description='Backup Xen VMs')
    parser.add_argument('mode', choices=['backup', 'vm', 'vdi'], help='Action to perform')
    parser.add_argument('-c', '--config', dest='conf', default='config.yaml', help='Specify a config .yaml file')
    args = parser.parse_args()

    log(f'Using config file: {args.conf}')
    conf = get_conf(args.conf)
    if conf is None:
        log('*** FATAL: Config file does not exist')
        sys.exit(-1)

    if get_env(conf) != 0:
        log('*** FATAL: Missing username or password')
        sys.exit(-1)

    ret = 0
    if args.mode == 'backup':
        ret = backup(conf)
    elif args.mode == 'vm':
        ret = list_vm(conf)
    elif args.mode == 'vdi':
        ret = list_vdi(conf)
    else:
        print('Invalid command')
        ret = -1
    sys.exit(ret)
