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
    return session


def vm_export_metadata(vm, pool, conf):
    vm_uuid = vm['uuid']
    vm_name = vm['name_label']
    filename = vm_name + '-meta.tar'
    log(f'Exporting VM metadata to "{filename}"')
    if Path(filename).exists():
        log(f'*** WARNING: {filename} file exists, removing it')
        Path(filename).unlink()
    cmd = str_format(conf['xe']['vm-export'], host=pool['master'], username=conf['auth']['username'], password=conf['auth']['password'], uuid=vm_uuid, metadata='true', filename=filename)
    if run_shell_command(cmd) != 0:
        log(f'*** Error exporting VM metadata')
    else:
        log(f'VM metadata export complete')
