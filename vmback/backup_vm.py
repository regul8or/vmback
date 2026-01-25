"""
VM (Virtual Machine) backup functionality
Exports complete VMs with all disks
"""

import time
import re
import logging
import XenAPI
from pathlib import Path
from typing import Dict, Any

from .utils import str_format, format_bytes, format_duration, get_ymd, run_shell_command, run_hook_commands
from .xapi import get_vm_by_uuid, is_vm_valid_for_backup, should_postpone_vm


logger = logging.getLogger(__name__)


def backup_single_vm_from_snapshot(
    session: XenAPI.Session,
    vm_snapshot_object: str,
    vm_snapshot_uuid: str,
    vm_record: Dict[str, Any],
    pool: Dict[str, Any],
    conf: Dict[str, Any],
    exporter
) -> bool:
    """
    Export a VM snapshot (snapshot already created and configured)
    
    Args:
        session: XenAPI session
        vm_snapshot_object: VM snapshot object reference
        vm_snapshot_uuid: VM snapshot UUID
        vm_record: Original VM record (for filename generation)
        pool: Pool configuration
        conf: Full configuration
        exporter: Exporter instance
        
    Returns:
        True if successful, False otherwise
    """
    vm_name = vm_record['name_label']
    vm_uuid = vm_record['uuid']
    
    # Export snapshot using exporter
    vm_filename = str_format(
        conf['env']['vm-template'],
        vm_name=vm_name,
        vm_uuid=vm_uuid
    )
    
    start_time = time.time()
    
    # Use exporter to export VM
    if not exporter.export_vm_full(vm_snapshot_uuid, pool, vm_filename):
        logger.error("Error exporting VM snapshot")
        return False
    
    elapsed = time.time() - start_time
    
    # Log export statistics (if exporter didn't already)
    try:
        vm_path = Path(vm_filename)
        file_size = vm_path.stat().st_size
        speed = file_size / elapsed if elapsed > 0 else 0
        logger.info(
            f"Export complete: {format_bytes(file_size)} in {format_duration(elapsed)} "
            f"({format_bytes(speed)}/s)"
        )
    except Exception as e:
        logger.debug(f"Could not get file statistics: {e}")
    
    return True


def cleanup_vm_snapshot(session: XenAPI.Session, vm_snapshot_object: str, vm_snapshot_uuid: str):
    """
    Clean up VM snapshot and associated VDI snapshots
    
    Args:
        session: XenAPI session
        vm_snapshot_object: VM snapshot object reference
        vm_snapshot_uuid: VM snapshot UUID for logging
    """
    try:
        logger.info("Removing VM snapshot and associated VDI snapshots")
        
        # First, get the snapshot record to find its VBDs
        try:
            vm_snapshot_record = session.xenapi.VM.get_record(vm_snapshot_object)
            logger.debug(f"VM snapshot UUID: {vm_snapshot_uuid}")
            logger.debug(f"VM snapshot has {len(vm_snapshot_record['VBDs'])} VBD(s)")
            
            # Destroy VDI snapshots explicitly (VM.destroy doesn't always clean them up)
            vbd_count = 0
            vdi_destroyed_count = 0
            
            for vbd_idx, vbd_object in enumerate(vm_snapshot_record['VBDs'], 1):
                try:
                    vbd_record = session.xenapi.VBD.get_record(vbd_object)
                    vbd_uuid = vbd_record['uuid']
                    vbd_device = vbd_record.get('device', 'unknown')
                    vbd_type = vbd_record['type']
                    
                    logger.debug(f"  VBD {vbd_idx}: UUID={vbd_uuid}, device={vbd_device}, type={vbd_type}")
                    
                    if vbd_type == 'Disk':
                        vdi_object = vbd_record['VDI']
                        vdi_record = session.xenapi.VDI.get_record(vdi_object)
                        vdi_uuid = vdi_record['uuid']
                        vdi_name = vdi_record.get('name_label', 'unnamed')
                        vdi_size = vdi_record.get('virtual_size', 0)
                        is_snapshot = vdi_record['is_a_snapshot']
                        
                        logger.debug(f"    VDI: UUID={vdi_uuid}, name={vdi_name}, size={vdi_size}, is_snapshot={is_snapshot}")
                        
                        # Only destroy if it's a snapshot
                        if is_snapshot:
                            logger.info(f"    Destroying VDI snapshot: {vdi_uuid} ({vdi_name})")
                            
                            # Retry logic for VDI_IN_USE errors (can happen after Ctrl+C)
                            max_retries = 3
                            retry_delay = 5  # seconds
                            
                            for retry in range(max_retries):
                                try:
                                    session.xenapi.VDI.destroy(vdi_object)
                                    vdi_destroyed_count += 1
                                    logger.debug(f"    VDI snapshot destroyed successfully")
                                    break  # Success, exit retry loop
                                    
                                except XenAPI.Failure as e:
                                    if 'VDI_IN_USE' in str(e.details) and retry < max_retries - 1:
                                        logger.warning(f"    VDI in use, retrying in {retry_delay}s (attempt {retry + 1}/{max_retries})...")
                                        time.sleep(retry_delay)
                                    else:
                                        raise  # Re-raise if not VDI_IN_USE or final retry
                        else:
                            logger.debug(f"    VDI is not a snapshot, skipping")
                        
                        vbd_count += 1
                    else:
                        logger.debug(f"  VBD {vbd_idx} is not a disk (type={vbd_type}), skipping")
                        
                except Exception as e:
                    logger.warning(f"  Could not process/destroy VBD {vbd_idx}: {e}")
            
            logger.info(f"Processed {vbd_count} disk VBD(s), destroyed {vdi_destroyed_count} VDI snapshot(s)")
                
        except Exception as e:
            logger.warning(f"Could not destroy VDI snapshots: {e}")
        
        # Now destroy the VM snapshot itself
        logger.info(f"Destroying VM snapshot: {vm_snapshot_uuid}")
        
        # Retry logic for OTHER_OPERATION_IN_PROGRESS (can happen after Ctrl+C)
        max_retries = 3
        retry_delay = 5  # seconds
        
        for retry in range(max_retries):
            try:
                session.xenapi.VM.destroy(vm_snapshot_object)
                logger.info("VM snapshot removed successfully")
                break  # Success, exit retry loop
                
            except XenAPI.Failure as e:
                if 'OTHER_OPERATION_IN_PROGRESS' in str(e.details) and retry < max_retries - 1:
                    logger.warning(f"Another operation in progress, retrying in {retry_delay}s (attempt {retry + 1}/{max_retries})...")
                    time.sleep(retry_delay)
                else:
                    raise  # Re-raise if not OTHER_OPERATION_IN_PROGRESS or final retry
        
    except XenAPI.Failure as e:
        logger.error(f"XenAPI error removing snapshot: {e.details}")
        logger.error("ORPHANED SNAPSHOT: Manual cleanup may be required!")
        logger.error(f"To manually clean up: xe snapshot-destroy uuid={vm_snapshot_uuid}")
    except Exception as e:
        logger.error(f"Error removing snapshot: {e}")
        logger.error("ORPHANED SNAPSHOT: Manual cleanup may be required!")
        logger.error(f"To manually clean up: xe snapshot-destroy uuid={vm_snapshot_uuid}")


def backup_vm(session: XenAPI.Session, pool: Dict[str, Any], conf: Dict[str, Any], exporter) -> int:
    """
    Backup VMs configured in the 'vm' section
    
    Args:
        session: XenAPI session
        pool: Pool configuration
        conf: Full configuration
        exporter: Exporter instance (XeExporter or HttpExporter)
        
    Returns:
        0 on success, -1 on error
    """
    if 'vm' not in conf or not conf['vm']:
        logger.info("No VMs configured for backup")
        return 0
    
    total_vms = len(conf['vm'])
    successful_vms = 0
    failed_vms = 0
    skipped_vms = 0
    
    # Get resilience policy for backup errors
    backup_on_error = conf.get('resilience', {}).get('backup', {}).get('on_error', 'fail')
    
    for idx, vm_config in enumerate(conf['vm'], 1):
        vm_uuid = vm_config['vm-uuid']
        vm_name = vm_config.get('vm-name', 'Unknown')
        
        logger.info(f"[{idx}/{total_vms}] Processing VM: {vm_name} ({vm_uuid})")
        
        try:
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
            
            # Run before-VM commands
            run_before_vm_commands(vm_record, conf)
            
            # Export VM metadata from ORIGINAL VM (snapshots cannot be used for metadata)
            if 'metadata' in pool['scope']:
                try:
                    logger.info(f"Exporting VM metadata for {vm_name}")
                    vm_metadata_filename = str_format(
                        conf['env']['vm-metadata-template'],
                        vm_name=vm_record['name_label'],
                        vm_uuid=vm_record['uuid']
                    )
                    # Use original VM record (NOT snapshot - XenAPI does not allow metadata export from snapshots)
                    if not exporter.export_vm_metadata(vm_record, pool, vm_metadata_filename):
                        logger.error(f"Failed to export metadata for {vm_name}")
                        
                        if backup_on_error == 'fail':
                            logger.error("Backup error policy is 'fail', stopping backup")
                            return -1
                        
                        # Continue to full VM backup even if metadata fails
                        logger.warning("Continuing to full VM backup despite metadata failure")
                
                except Exception as e:
                    logger.error(f"Error exporting VM metadata for {vm_name}: {e}")
                    
                    if backup_on_error == 'fail':
                        logger.error("Backup error policy is 'fail', stopping backup")
                        raise
                    
                    logger.warning("Continuing to full VM backup despite metadata error")
            
            # Create VM snapshot for full export
            vm_snapshot_object = None
            vm_snapshot_uuid = None
            backup_success = False
            
            try:
                # Step 1: Create VM snapshot
                snapshot_name = f'Backup of {vm_name}'
                logger.info(f"Creating VM snapshot: {snapshot_name}")
                vm_snapshot_object = session.xenapi.VM.snapshot(vm_object, snapshot_name)
                vm_snapshot_record = session.xenapi.VM.get_record(vm_snapshot_object)
                vm_snapshot_uuid = vm_snapshot_record['uuid']
                logger.info(f"Created snapshot: {vm_snapshot_uuid}")
                
                # Step 2: Configure snapshot to be exportable
                logger.info("Configuring snapshot for export")
                session.xenapi.VM.set_is_a_template(vm_snapshot_object, False)
                session.xenapi.VM.set_ha_always_run(vm_snapshot_object, False)
                logger.debug("Snapshot configured")
                
                # Step 3: Export full VM from snapshot
                if backup_single_vm_from_snapshot(
                    session, vm_snapshot_object, vm_snapshot_uuid, 
                    vm_record, pool, conf, exporter
                ):
                    logger.info(f"Successfully backed up VM: {vm_name}")
                    backup_success = True
                    successful_vms += 1
                else:
                    logger.error(f"Failed to backup VM: {vm_name}")
                    failed_vms += 1
                    
                    if backup_on_error == 'fail':
                        logger.error("Backup error policy is 'fail', stopping backup")
                        return -1
                    
            except Exception as e:
                logger.error(f"Error backing up VM {vm_name}: {e}")
                failed_vms += 1
                
                if backup_on_error == 'fail':
                    logger.error("Backup error policy is 'fail', stopping backup")
                    raise
                
                logger.warning(f"Continuing to next VM despite error in {vm_name}")
                
            finally:
                # Always clean up snapshot
                if vm_snapshot_object is not None:
                    cleanup_vm_snapshot(session, vm_snapshot_object, vm_snapshot_uuid)
            
            # Run after-VM commands only if backup succeeded
            if backup_success:
                run_after_vm_commands(vm_record, conf)
        
        except Exception as e:
            logger.error(f"Fatal error processing VM {vm_name}: {e}", exc_info=True)
            failed_vms += 1
            
            if backup_on_error == 'fail':
                logger.error("Backup error policy is 'fail', stopping backup")
                return -1
            
            logger.warning("Continuing to next VM despite fatal error")
    
    # Summary
    logger.info(
        f"VM backup complete: {successful_vms} successful, {failed_vms} failed, "
        f"{skipped_vms} skipped out of {total_vms} VMs"
    )
    
    return 0 if failed_vms == 0 else -1


def run_before_vm_commands(vm_record: Dict[str, Any], conf: Dict[str, Any]):
    """Run configured before-VM commands"""
    run_hook_commands('before', 'vm', conf, context={
        'vm_name': vm_record['name_label'],
        'vm_uuid': vm_record['uuid']
    })


def run_after_vm_commands(vm_record: Dict[str, Any], conf: Dict[str, Any]):
    """Run configured after-VM commands"""
    run_hook_commands('after', 'vm', conf, context={
        'vm_name': vm_record['name_label'],
        'vm_uuid': vm_record['uuid']
    })
