#!/usr/bin/env python3

import prettytable

from .config import Config
from .misc import *
from .xapi import *

"""
xenapi_pool = session.xenapi.pool.get_all()[0]
print(xenapi_pool)
pool_record = session.xenapi.pool.get_record(xenapi_pool)
print(pool_record)
"""


def _list_pool_vdi(pool, conf):
    if 'id' in pool:
        log(f'Gettong the list of VDIs in pool: {pool["id"]}')
    else:
        log('Gettong the list of VDIs')

    session = pool_connect(pool, conf)
    if session is None:
        log('*** FATAL: Could not process a pool')
        return -1
    log(f'Connected, session id: {session.xenapi.session.get_uuid(session._session)}')

    table = prettytable.PrettyTable()
    table.field_names = ['vm uuid', 'vm name_label', 'power_state', 'device', 'name_label', 'virtual_size']
    table.border = False
    table.hrules = prettytable.HEADER
    table.vrules = prettytable.NONE
    table.preserve_internal_border = True
    table.left_padding_width = 0
    table.align = 'l'
    table.align['virtual_size'] = 'r'
    all_vm_objects = session.xenapi.VM.get_all()
    for vm_object in all_vm_objects:
        vm = session.xenapi.VM.get_record(vm_object)
        # Skip template
        if vm['is_a_template']:
            continue
        # Skip control domain
        if vm['is_control_domain']:
            continue
        for vbd_object in vm['VBDs']:
            vbd = session.xenapi.VBD.get_record(vbd_object)
            # Skip not disks
            if vbd['type'] != 'Disk':
                continue
            vdi = session.xenapi.VDI.get_record(vbd['VDI'])
            if vdi['is_a_snapshot']:
                continue
            size = f"{int(vdi['virtual_size']):,}"
            table.add_row([vm['uuid'], vm['name_label'], vm['power_state'], vbd['device'], vdi['name_label'], size])
    print(table)

    if session is not None:
        log('Closing session')
        session.logout()

    return 0


def list_vdi(conf):
    if 'pools' in conf:
        pools = conf['pools']
        for pool in pools:
            try:
                _list_pool_vdi(pool, conf)
            except Exception as err:
                log(f'Unexpected {err=}, {type(err)=}')

    return 0
