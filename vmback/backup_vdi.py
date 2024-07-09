#!/usr/bin/env python3

import time

from .config import Config
from .misc import *
from .xapi import *


def _backup_vdi(session, vdi_object, vm_name, vbd_device, pool, conf):
    log(f'1. Creating a snapshot')
    vdi_snapshot_object = session.xenapi.VDI.snapshot(vdi_object)
    vdi_snapshot_record = session.xenapi.VDI.get_record(vdi_snapshot_object)
    vdi_snapshot_uuid = vdi_snapshot_record['uuid']
    log(f'   Created snapshot {vdi_snapshot_uuid}')

    vdi_filename = vm_name + ' - ' + vbd_device + '.vhd'
    log(f'2. Exporting a snapshot to "{vdi_filename}"')
    if Path(vdi_filename).exists():
        log(f'   *** WARNING: {vdi_filename} file exists, removing it')
        Path(vdi_filename).unlink()
    cmd = str_format(conf['xe']['vdi-export'], host=pool['master'], username=conf['auth']['username'], password=conf['auth']['password'], uuid=vdi_snapshot_uuid, filename=vdi_filename)
    start_time = time.time()
    if run_shell_command(cmd) != 0:
        log(f'   *** Error exporting a snapshot')
    else:
        log(f'   Export complete')
    elapsed = time.time() - start_time
    file_size = Path(vdi_filename).stat().st_size
    log(f'   Exported {file_size:,} bytes in {round(elapsed)} seconds ({round(file_size / elapsed):,} Bps)')

    log(f'3. Removing a snapshot')
    session.xenapi.VDI.destroy(vdi_snapshot_object)
    log(f'   Removed')
    return 0

#
# TODO: Check for free space
#

def backup_vdi(session, pool, conf):
    for vm in conf['vdi']:
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
        log(f'VM: {vm_name} ({vm_uuid})')
        for vbd_object in vm_record['VBDs']:
            vbd_record = session.xenapi.VBD.get_record(vbd_object)
            vbd_uuid = vbd_record['uuid']
            # Skip not disks
            if vbd_record['type'] != 'Disk':
                continue
            vbd_device = vbd_record['device']
            if vbd_device != vm['device']:
                continue
            log(f'VBD: {vbd_device} ({vbd_uuid})')
            vdi_object = vbd_record['VDI']
            vdi_record = session.xenapi.VDI.get_record(vdi_object)
            vdi_uuid = vdi_record['uuid']
            if vdi_record['is_a_snapshot']:
                continue
            log(f'VDI UUID: {vdi_uuid}')
            vm_export_metadata(vm_record, pool, conf)
            _backup_vdi(session, vdi_object, vm_name, vbd_device, pool, conf)

    return 0
