#!/usr/bin/env python3

import prettytable

from .config import Config
from .misc import *
from .xapi import *


def _list_pool_vm(pool, conf):
    if 'id' in pool:
        log(f'Gettong the list of VMs in pool: {pool["id"]}')
    else:
        log('Gettong the list of VMs')

    session = pool_connect(pool, conf)
    if session is None:
        log('*** FATAL: Could not process a pool')
        return -1
    log(f'Connected, session id: {session.xenapi.session.get_uuid(session._session)}')

    table = prettytable.PrettyTable()
    table.border = False
    table.hrules = prettytable.HEADER
    table.vrules = prettytable.NONE
    table.preserve_internal_border = True
    table.align = 'l'
    table.left_padding_width = 0
    table.field_names = ['vm uuid', 'name_label', 'power_state']
    all_vm_objects = session.xenapi.VM.get_all()
    for vm_object in all_vm_objects:
        vm = session.xenapi.VM.get_record(vm_object)
        # Skip template
        if vm['is_a_template']:
            continue
        # Skip control domain
        if vm['is_control_domain']:
            continue
        table.add_row([vm['uuid'], vm['name_label'], vm['power_state']])
    print(table)

    if session is not None:
        log('Closing session')
        session.logout()

    return 0


def list_vm(conf):
    if 'pools' in conf:
        pools = conf['pools']
        for pool in pools:
            try:
                _list_pool_vm(pool, conf)
            except Exception as err:
                log(f'Unexpected {err=}, {type(err)=}')

    return 0
