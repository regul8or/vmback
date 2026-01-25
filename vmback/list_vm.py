"""
List virtual machines in pools
"""

import logging
import prettytable
from typing import Dict, Any

from .xapi import pool_connect


logger = logging.getLogger(__name__)


def list_pool_vm(pool: Dict[str, Any], conf: Dict[str, Any]) -> int:
    """
    List all VMs in a pool
    
    Args:
        pool: Pool configuration
        conf: Full configuration
        
    Returns:
        0 on success, -1 on error
    """
    pool_id = pool.get('id', 'unknown')
    logger.info(f"Getting VM list for pool: {pool_id}")
    
    session = None
    
    try:
        # Connect to pool
        session = pool_connect(pool, conf)
        logger.info(f"Session ID: {session.xenapi.session.get_uuid(session._session)}")
        
        # Create table
        table = prettytable.PrettyTable()
        table.border = False
        table.hrules = prettytable.HEADER
        table.vrules = prettytable.NONE
        table.preserve_internal_border = True
        table.align = 'l'
        table.left_padding_width = 0
        table.field_names = ['VM UUID', 'Name', 'Power State', 'Host', 'Address']
        
        # Get all VMs
        all_vm_objects = session.xenapi.VM.get_all()
        
        for vm_object in all_vm_objects:
            vm = session.xenapi.VM.get_record(vm_object)
            
            # Skip templates
            if vm['is_a_template']:
                continue
            
            # Skip control domains
            if vm['is_control_domain']:
                continue
            
            # Get host information
            host_object = vm['resident_on']
            if 'NULL' in host_object:
                host_name = ''
                host_address = ''
            else:
                host = session.xenapi.host.get_record(host_object)
                host_name = host['hostname']
                host_address = host['address']
            
            table.add_row([
                vm['uuid'],
                vm['name_label'],
                vm['power_state'],
                host_name,
                host_address
            ])
        
        print(table)
        return 0
        
    except Exception as e:
        logger.error(f"Error listing VMs: {e}", exc_info=True)
        return -1
        
    finally:
        if session is not None:
            try:
                logger.info("Closing session")
                session.logout()
            except Exception as e:
                logger.warning(f"Error closing session: {e}")


def list_vm(conf: Dict[str, Any]) -> int:
    """
    List VMs for all configured pools
    
    Args:
        conf: Full configuration
        
    Returns:
        0 on success, -1 on error
    """
    if 'pools' not in conf or not conf['pools']:
        logger.warning("No pools configured")
        return 0
    
    ret = 0
    
    for pool in conf['pools']:
        try:
            pool_ret = list_pool_vm(pool, conf)
            if pool_ret != 0:
                ret = -1
        except Exception as e:
            logger.error(f"Unexpected error listing VMs: {e}", exc_info=True)
            ret = -1
    
    return ret
