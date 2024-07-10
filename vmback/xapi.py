#!/usr/bin/env python3

import XenAPI

from pathlib import Path

from .misc import *


def pool_connect(pool, conf):
    session = None

    if not 'hosts' in pool:
        log('*** FATAL: No hosts defined for pool')
        return None
    if len(pool['hosts']) == 0:
        log('*** FATAL: No host addresses for pool')
        return None

    for host in pool['hosts']:
        log(f'Connecting to {host}')
        try:
            session = XenAPI.Session(f'http://{host}/')
            session.xenapi.login_with_password(conf['auth']['username'], conf['auth']['password'])
            pool['master'] = host
            break
        except Exception as err:
            log(f'Unexpected {err=}, {type(err)=}')
            log('*** ERROR: Could not connect')
    pool_objects = session.xenapi.pool.get_all()
    pool_object = pool_objects[0]
    pool_record = session.xenapi.pool.get_record(pool_object)
    master_object = pool_record['master']
    master_record = session.xenapi.host.get_record(master_object)
    pool['uuid'] = pool_record['uuid']
    pool['master'] = master_record['address']
    pool['name'] = pool_record['name_label'] if pool_record['name_label'] != '' else master_record['name_label']
    return session


def vm_export_metadata(vm, pool, conf):
    vm_uuid = vm['uuid']
    vm_name = vm['name_label']
    vm_metadata_filename = str_format(conf['env']['vm-metadata-template'], vm_name=vm['name_label'], vm_uuid=vm['uuid'])
    conf['env']['vm-metadata-filename'] = vm_metadata_filename
    log(f'Exporting VM metadata to "{vm_metadata_filename}"')
    if Path(vm_metadata_filename).exists():
        log(f'*** WARNING: {vm_metadata_filename} file exists, removing it')
        Path(vm_metadata_filename).unlink()
    cmd = str_format(conf['xe']['vm-export'], host=pool['master'], username=conf['auth']['username'], password=conf['auth']['password'], uuid=vm_uuid, metadata='true', filename=vm_metadata_filename)
    if run_shell_command(cmd) != 0:
        log(f'*** Error exporting VM metadata')
    else:
        log(f'VM metadata export complete')
