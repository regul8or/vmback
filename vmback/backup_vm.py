#!/usr/bin/env python3

import time
import re

from .config import Config
from .misc import *
from .xapi import *

#
# TODO: Check for free space
#

def backup_vm(session, pool, conf):
    for vm in conf['vm']:
        vm_uuid = vm['vm-uuid']
        vm_record = None
        vm_object = None
        try:
            vm_object = session.xenapi.VM.get_by_uuid(vm_uuid)
        except XenAPI.Failure as err:
            if err.details[0] != 'UUID_INVALID':
                raise err
        if vm_object is None:
            continue
        vm_record = session.xenapi.VM.get_record(vm_object)
        if vm_record['is_a_template']:
            continue
        # Skip control domain
        if vm_record['is_control_domain']:
            continue
        vm_name = vm_record['name_label']
        snapshot_name = 'Backup of ' + vm_name
        log(f'VM: {vm_name} ({vm_uuid})')
        vm_export_metadata(vm_record, pool, conf)

        log(f'1. Creating a snapshot')
        vm_snapshot_object = session.xenapi.VM.snapshot(vm_object, snapshot_name)
        vm_snapshot_record = session.xenapi.VM.get_record(vm_snapshot_object)
        vm_snapshot_uuid = vm_snapshot_record['uuid']
        log(f'   Created snapshot {vm_snapshot_uuid}')

        log(f'2. Changing snapshot parameners')
        session.xenapi.VM.set_is_a_template(vm_snapshot_object, False)
        session.xenapi.VM.set_ha_always_run(vm_snapshot_object, False)

        vm_filename = str_format(conf['env']['vm-template'], vm_name=vm_record['name_label'], vm_uuid=vm_record['uuid'])
        log(f'3. Exporting a snapshot to "{vm_filename}"')
        if Path(vm_filename).exists():
            log(f'   *** WARNING: {vm_filename} file exists, removing it')
            Path(vm_filename).unlink()
        cmd = str_format(conf['xe']['vm-export'], host=pool['master'], username=conf['auth']['username'], password=conf['auth']['password'], uuid=vm_snapshot_uuid, metadata='false', filename=vm_filename)
        start_time = time.time()
        if run_shell_command(cmd) != 0:
            log(f'   *** Error exporting a snapshot')
        else:
            log(f'   Export complete')
        elapsed = time.time() - start_time
        file_size = Path(vm_filename).stat().st_size
        log(f'   Exported {file_size:,} bytes in {round(elapsed)} seconds ({round(file_size / elapsed):,} Bps)')

        log(f'4. Removing a snapshot')
        session.xenapi.VM.destroy(vm_snapshot_object)
        log(f'   Removed')

        log(f'Running After VM Commands')
        if 'vm' in conf['after'] and conf['after']['vm'] is not None:
            now = get_ymd()
            vm_name = vm_record['name_label']
            vm_name_escaped = re.escape(vm_name)
            for str in conf['after']['vm']:
                cmd = str_format(str, vm_name=vm_name, vm_name_escaped=vm_name_escaped, vm_uuid=vm_record['uuid'], y=now['y'], m=now['m'], d=now['d'])
                run_shell_command(cmd)
    return 0
