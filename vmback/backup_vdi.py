"""
VDI (Virtual Disk Image) backup functionality
"""

import time
import re
import logging
import XenAPI
from pathlib import Path
from typing import Dict, Any, Optional

from .utils import str_format, format_bytes, format_duration, get_ymd, run_shell_command, run_hook_commands
from .xapi import get_vm_by_uuid, is_vm_valid_for_backup, should_postpone_vm, vm_export_metadata


logger = logging.getLogger(__name__)


def backup_vdi_snapshot(
    session: XenAPI.Session,
    vdi_object: str,
    vm_record: Dict[str, Any],
    vbd_device: str,
    pool: Dict[str, Any],
    conf: Dict[str, Any],
    exporter
) -> bool:
    """
    Backup a single VDI by creating a snapshot and exporting it
    
    This function includes proper cleanup even if export fails.
    The snapshot is always destroyed at the end, preventing orphaned snapshots.
    
    Args:
        session: XenAPI session
        vdi_object: VDI object reference
        vm_record: VM record
        vbd_device: VBD device name (e.g., 'xvda')
        pool: Pool configuration
        conf: Full configuration
        exporter: Exporter instance (XeExporter or HttpExporter)
        
    Returns:
        True if backup successful, False otherwise
    """
    vdi_snapshot_object = None
    
    try:
        # Step 1: Create snapshot
        logger.info(f"Creating VDI snapshot for device {vbd_device}")
        vdi_snapshot_object = session.xenapi.VDI.snapshot(vdi_object)
        vdi_snapshot_record = session.xenapi.VDI.get_record(vdi_snapshot_object)
        vdi_snapshot_uuid = vdi_snapshot_record['uuid']
        logger.info(f"Created snapshot: {vdi_snapshot_uuid}")
        
        # Step 2: Export snapshot using exporter
        vdi_filename = str_format(
            conf['env']['vdi-template'],
            vm_name=vm_record['name_label'],
            vm_uuid=vm_record['uuid'],
            device=vbd_device
        )
        
        start_time = time.time()
        
        # Use exporter to export VDI
        if not exporter.export_vdi(vdi_snapshot_uuid, pool, vdi_filename):
            logger.error(f"Error exporting snapshot for device {vbd_device}")
            return False
        
        elapsed = time.time() - start_time
        
        # Log export statistics (if exporter didn't already)
        try:
            vdi_path = Path(vdi_filename)
            file_size = vdi_path.stat().st_size
            speed = file_size / elapsed if elapsed > 0 else 0
            logger.info(
                f"Export complete: {format_bytes(file_size)} in {format_duration(elapsed)} "
                f"({format_bytes(speed)}/s)"
            )
        except Exception as e:
            logger.debug(f"Could not get file statistics: {e}")
        
        return True
        
    except XenAPI.Failure as e:
        logger.error(f"XenAPI error during VDI backup: {e.details}")
        return False
        
    except Exception as e:
        logger.error(f"Unexpected error during VDI backup: {e}")
        return False
        
    finally:
        # CRITICAL: Always destroy snapshot, even if export failed
        # This prevents orphaned snapshots that accumulate over time
        if vdi_snapshot_object is not None:
            try:
                logger.info("Removing VDI snapshot")
                session.xenapi.VDI.destroy(vdi_snapshot_object)
                logger.info("Snapshot removed successfully")
            except XenAPI.Failure as e:
                # Check if it's a VDI_IN_USE error - export might still be releasing locks
                if e.details[0] == 'VDI_IN_USE':
                    logger.warning("VDI in use, retrying in 5s (attempt 1/3)...")
                    time.sleep(5)
                    
                    for attempt in range(2, 4):  # Attempts 2 and 3
                        try:
                            session.xenapi.VDI.destroy(vdi_snapshot_object)
                            logger.info("Snapshot removed successfully")
                            break
                        except XenAPI.Failure as retry_e:
                            if retry_e.details[0] == 'VDI_IN_USE' and attempt < 3:
                                logger.warning(f"VDI still in use, retrying in 5s (attempt {attempt}/3)...")
                                time.sleep(5)
                            else:
                                logger.error(f"XenAPI error removing snapshot after retries: {retry_e.details}")
                                logger.error("ORPHANED SNAPSHOT: Manual cleanup may be required!")
                                break
                else:
                    logger.error(f"XenAPI error removing snapshot: {e.details}")
                    logger.error("ORPHANED SNAPSHOT: Manual cleanup may be required!")
            except Exception as e:
                logger.error(f"Error removing snapshot: {e}")
                logger.error("ORPHANED SNAPSHOT: Manual cleanup may be required!")


def backup_vdi(session: XenAPI.Session, pool: Dict[str, Any], conf: Dict[str, Any], exporter) -> int:
    """
    Backup VDIs for configured VMs
    
    Args:
        session: XenAPI session
        pool: Pool configuration
        conf: Full configuration
        
    Returns:
        0 on success, -1 on error
    """
    if 'vdi' not in conf or not conf['vdi']:
        logger.info("No VDIs configured for backup")
        return 0
    
    total_vms = len(conf['vdi'])
    successful_vms = 0
    failed_vms = 0
    skipped_vms = 0
    
    # Get resilience policy for backup errors
    backup_on_error = conf.get('resilience', {}).get('backup', {}).get('on_error', 'fail')
    
    for idx, vm_config in enumerate(conf['vdi'], 1):
        vm_uuid = vm_config['vm-uuid']
        vm_name = vm_config.get('vm-name', 'Unknown')
        
        logger.info(f"[{idx}/{total_vms}] Processing VM: {vm_name} ({vm_uuid})")
        
        # Get VM from XenAPI
        vm_object, vm_record = get_vm_by_uuid(session, vm_uuid)
        if vm_object is None:
            logger.warning(f"VM {vm_uuid} not found, skipping")
            failed_vms += 1
            
            if backup_on_error == 'fail':
                logger.error("Backup error policy is 'fail', stopping backup")
                return -1
            continue
        
        # Validate VM is suitable for backup
        if not is_vm_valid_for_backup(vm_record):
            logger.info(f"VM {vm_name} is not valid for backup, skipping")
            skipped_vms += 1
            continue
        
        # Check if VM should be postponed
        if should_postpone_vm(vm_record, conf):
            skipped_vms += 1
            continue
        
        # Determine which devices to backup
        devices = []
        if 'device' in vm_config:
            if isinstance(vm_config['device'], str):
                devices = [vm_config['device']]
            else:
                devices = vm_config['device']
        else:
            # If no devices specified, backup all disks
            logger.debug("No devices specified, discovering all disks")
            for vbd_object in vm_record['VBDs']:
                vbd_record = session.xenapi.VBD.get_record(vbd_object)
                if vbd_record['type'] == 'Disk':
                    devices.append(vbd_record['device'])
        
        if not devices:
            logger.warning(f"No devices found for VM {vm_name}")
            failed_vms += 1
            continue
        
        logger.info(f"Backing up {len(devices)} device(s): {', '.join(devices)}")
        
        # Export VM metadata once
        vm_meta_exported = False
        vm_backup_failed = False
        
        # Backup each device
        device_success_count = 0
        for device in devices:
            try:
                logger.info(f"Processing device: {device}")
                
                # Run before-VDI commands for this device
                run_before_vdi_commands(vm_record, conf, device)
                
                # Find VBD and VDI for this device
                vdi_object = None
                for vbd_object in vm_record['VBDs']:
                    vbd_record = session.xenapi.VBD.get_record(vbd_object)
                    if vbd_record['device'] == device and vbd_record['type'] == 'Disk':
                        vdi_object = vbd_record['VDI']
                        break
                
                if vdi_object is None:
                    logger.error(f"Device {device} not found for VM {vm_name}")
                    
                    if backup_on_error == 'fail':
                        logger.error("Backup error policy is 'fail', stopping backup")
                        return -1
                    continue
                
                # Export VM metadata before first VDI (if not already exported)
                if not vm_meta_exported and 'metadata' in pool['scope']:
                    logger.info("Exporting VM metadata")
                    if vm_export_metadata(vm_record, pool, conf):
                        vm_meta_exported = True
                    else:
                        logger.warning("VM metadata export failed, continuing with VDI backup")
                
                # Backup the VDI
                if backup_vdi_snapshot(session, vdi_object, vm_record, device, pool, conf, exporter):
                    device_success_count += 1
                    # Run after-VDI commands for successful device
                    run_after_vdi_commands(vm_record, conf, device)
                else:
                    logger.error(f"Failed to backup device {device}")
                    
                    if backup_on_error == 'fail':
                        logger.error("Backup error policy is 'fail', stopping backup")
                        return -1
                        
            except Exception as e:
                logger.error(f"Error backing up device {device}: {e}")
                
                if backup_on_error == 'fail':
                    logger.error("Backup error policy is 'fail', stopping backup")
                    raise
                
                logger.warning(f"Continuing to next device despite error in {device}")
        
        # Check if any devices were successful
        if device_success_count > 0:
            logger.info(f"Successfully backed up {device_success_count}/{len(devices)} device(s)")
            successful_vms += 1
        else:
            logger.error(f"Failed to backup any devices for VM {vm_name}")
            failed_vms += 1
            
            if backup_on_error == 'fail':
                logger.error("Backup error policy is 'fail', stopping backup")
                return -1
    
    # Summary
    logger.info(
        f"VDI backup complete: {successful_vms} successful, {failed_vms} failed, "
        f"{skipped_vms} skipped out of {total_vms} VMs"
    )
    
    return 0 if failed_vms == 0 else -1


def run_before_vdi_commands(vm_record: Dict[str, Any], conf: Dict[str, Any], device: str):
    """Run configured before-VDI commands"""
    run_hook_commands('before', 'vdi', conf, context={
        'vm_name': vm_record['name_label'],
        'vm_uuid': vm_record['uuid'],
        'device': device
    })


def run_after_vdi_commands(vm_record: Dict[str, Any], conf: Dict[str, Any], device: str):
    """Run configured after-VDI commands"""
    run_hook_commands('after', 'vdi', conf, context={
        'vm_name': vm_record['name_label'],
        'vm_uuid': vm_record['uuid'],
        'device': device
    })
