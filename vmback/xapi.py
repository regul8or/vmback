"""
XenAPI wrapper functions for VM Backup
"""

import XenAPI
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from .utils import str_format, run_shell_command, redact_credentials


logger = logging.getLogger(__name__)


class XenConnectionError(Exception):
    """XenAPI connection error"""
    pass


def pool_connect(pool: Dict[str, Any], conf: Dict[str, Any]) -> Optional[XenAPI.Session]:
    """
    Connect to XCP-ng pool and retrieve pool information
    
    Args:
        pool: Pool configuration
        conf: Full configuration
        
    Returns:
        XenAPI Session object or None if connection failed
        
    Raises:
        XenConnectionError: If no hosts defined or connection fails
    """
    if 'hosts' not in pool:
        raise XenConnectionError("No hosts defined for pool")
    
    if not pool['hosts']:
        raise XenConnectionError("Empty hosts list for pool")
    
    session = None
    last_error = None
    
    for host in pool['hosts']:
        logger.info(f"Attempting to connect to {host}")
        
        try:
            session = XenAPI.Session(f'http://{host}/')
            session.xenapi.login_with_password(
                conf['auth']['username'],
                conf['auth']['password']
            )
            logger.info(f"Successfully connected to {host}")
            pool['master'] = host
            break
            
        except XenAPI.Failure as e:
            last_error = e
            logger.warning(f"XenAPI failure connecting to {host}: {e.details}")
            
        except Exception as e:
            last_error = e
            logger.warning(f"Error connecting to {host}: {e}")
    
    if session is None:
        raise XenConnectionError(f"Could not connect to any host in pool: {last_error}")
    
    # Get pool information
    try:
        pool_objects = session.xenapi.pool.get_all()
        if not pool_objects:
            raise XenConnectionError("No pools found")
        
        pool_object = pool_objects[0]
        pool_record = session.xenapi.pool.get_record(pool_object)
        
        master_object = pool_record['master']
        master_record = session.xenapi.host.get_record(master_object)
        
        pool['uuid'] = pool_record['uuid']
        pool['master'] = master_record['address']
        pool['name'] = pool_record['name_label'] if pool_record['name_label'] else master_record['name_label']
        
        logger.info(f"Pool: {pool['name']} (UUID: {pool['uuid']})")
        logger.info(f"Master: {pool['master']}")
        
    except Exception as e:
        if session:
            session.logout()
        raise XenConnectionError(f"Error retrieving pool information: {e}")
    
    return session


def vm_export_metadata(vm: Dict[str, Any], pool: Dict[str, Any], conf: Dict[str, Any]) -> bool:
    """
    Export VM metadata (configuration) without disks
    
    Args:
        vm: VM record from XenAPI
        pool: Pool configuration
        conf: Full configuration
        
    Returns:
        True if successful, False otherwise
    """
    vm_uuid = vm['uuid']
    vm_name = vm['name_label']
    
    vm_metadata_filename = str_format(
        conf['env']['vm-metadata-template'],
        vm_name=vm_name,
        vm_uuid=vm_uuid
    )
    
    conf['env']['vm-metadata-filename'] = vm_metadata_filename
    
    logger.info(f"Exporting VM metadata to '{vm_metadata_filename}'")
    
    # Remove existing file
    metadata_path = Path(vm_metadata_filename)
    if metadata_path.exists():
        logger.warning(f"File '{vm_metadata_filename}' exists, removing it")
        try:
            metadata_path.unlink()
        except Exception as e:
            logger.error(f"Error removing existing metadata file: {e}")
            return False
    
    # Execute export command
    cmd = str_format(
        conf['xe']['vm-export'],
        host=pool['master'],
        username=conf['auth']['username'],
        password=conf['auth']['password'],
        uuid=vm_uuid,
        metadata='true',
        filename=vm_metadata_filename
    )
    
    # Redact credentials for logging
    log_cmd = redact_credentials(cmd, conf['auth']['username'], conf['auth']['password'])
    
    if run_shell_command(cmd, log_cmd) != 0:
        logger.error("Error exporting VM metadata")
        return False
    
    logger.info("VM metadata export complete")
    return True


def get_vm_by_uuid(session: XenAPI.Session, vm_uuid: str) -> Optional[tuple]:
    """
    Get VM object and record by UUID
    
    Args:
        session: XenAPI session
        vm_uuid: VM UUID
        
    Returns:
        Tuple of (vm_object, vm_record) or (None, None) if not found
    """
    try:
        vm_object = session.xenapi.VM.get_by_uuid(vm_uuid)
        vm_record = session.xenapi.VM.get_record(vm_object)
        return vm_object, vm_record
        
    except XenAPI.Failure as e:
        if e.details[0] == 'UUID_INVALID':
            logger.warning(f"VM with UUID {vm_uuid} not found")
            return None, None
        raise
    
    except Exception as e:
        logger.error(f"Error retrieving VM {vm_uuid}: {e}")
        return None, None


def is_vm_valid_for_backup(vm_record: Dict[str, Any]) -> bool:
    """
    Check if VM is valid for backup (not a template, not a control domain)
    
    Args:
        vm_record: VM record from XenAPI
        
    Returns:
        True if VM should be backed up, False otherwise
    """
    if vm_record['is_a_template']:
        logger.debug(f"Skipping template: {vm_record['name_label']}")
        return False
    
    if vm_record['is_control_domain']:
        logger.debug(f"Skipping control domain: {vm_record['name_label']}")
        return False
    
    return True


def should_postpone_vm(vm_record: Dict[str, Any], conf: Dict[str, Any]) -> bool:
    """
    Check if VM should be postponed (skipped) based on configuration
    
    Args:
        vm_record: VM record from XenAPI
        conf: Full configuration
        
    Returns:
        True if VM should be skipped, False otherwise
    """
    if 'vm-postpone' not in conf or not conf['vm-postpone']:
        return False
    
    vm_uuid = vm_record['uuid']
    vm_name = vm_record['name_label']
    
    for postpone_entry in conf['vm-postpone']:
        if postpone_entry.get('vm-uuid') == vm_uuid:
            logger.info(f"VM '{vm_name}' is in postpone list, skipping")
            return True
    
    return False
