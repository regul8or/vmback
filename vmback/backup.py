"""
Main backup orchestration module
"""

import os
import re
import logging
from pathlib import Path
from typing import Dict, Any

from .utils import str_format, run_shell_command, get_ymd, run_hook_commands
from .xapi import pool_connect
from .backup_vm import backup_vm
from .backup_vdi import backup_vdi
from .exporters import create_exporter


logger = logging.getLogger(__name__)


def validate_paths(conf: Dict[str, Any]) -> tuple[str, str]:
    """
    Validate and setup backup and log paths
    
    Args:
        conf: Configuration dictionary
        
    Returns:
        Tuple of (backup_path, log_path)
        
    Raises:
        RuntimeError: If paths are invalid or not writable
    """
    # Backup path
    backup_path = conf.get('env', {}).get('backup-path', os.getcwd())
    backup_path_obj = Path(backup_path)
    
    if not backup_path_obj.exists():
        raise RuntimeError(f"Backup path does not exist: {backup_path}")
    
    if not os.access(backup_path, os.W_OK):
        raise RuntimeError(f"Backup path is not writable: {backup_path}")
    
    logger.info(f"Backup path: {backup_path}")
    
    # Log path
    log_path = conf.get('env', {}).get('log-path', backup_path)
    log_path_obj = Path(log_path)
    
    # Create log path if it doesn't exist
    if not log_path_obj.exists():
        logger.warning(f"Log path does not exist, creating: {log_path}")
        try:
            log_path_obj.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning(f"Could not create log path, using backup path: {e}")
            log_path = backup_path
    
    if not os.access(log_path, os.W_OK):
        logger.warning(f"Log path is not writable, using backup path")
        log_path = backup_path
    
    logger.info(f"Log path: {log_path}")
    
    return backup_path, log_path


def pool_backup(pool: Dict[str, Any], conf: Dict[str, Any]) -> int:
    """
    Backup a single pool
    
    Args:
        pool: Pool configuration
        conf: Full configuration
        
    Returns:
        0 on success, -1 on error
    """
    pool_id = pool.get('id', 'unknown')
    logger.info(f"{'='*60}")
    logger.info(f"Starting backup for pool: {pool_id}")
    logger.info(f"{'='*60}")
    
    session = None
    exporter = None
    ret = 0
    
    try:
        # Connect to pool
        session = pool_connect(pool, conf)
        logger.info(f"Session ID: {session.xenapi.session.get_uuid(session._session)}")
        
        # Create exporter based on config
        exporter = create_exporter(session, conf)
        
        # Backup pool metadata
        if 'metadata' in pool['scope']:
            logger.info("Backing up pool metadata")
            run_before_metadata_commands(pool, conf)
            ret = backup_pool_metadata(pool, conf, exporter)
            if ret != 0:
                logger.error("Pool metadata backup failed")
        
        # Backup VMs
        if 'vm' in pool['scope']:
            logger.info("Backing up Virtual Machines")
            vm_ret = backup_vm(session, pool, conf, exporter)
            if vm_ret != 0:
                ret = vm_ret
        
        # Backup VDIs
        if 'vdi' in pool['scope']:
            logger.info("Backing up Virtual Disk Images")
            vdi_ret = backup_vdi(session, pool, conf, exporter)
            if vdi_ret != 0:
                ret = vdi_ret
        
    except Exception as e:
        logger.error(f"Error during pool backup: {e}", exc_info=True)
        ret = -1
    
    finally:
        if session is not None:
            try:
                logger.info("Closing session")
                session.logout()
            except Exception as e:
                logger.warning(f"Error closing session: {e}")
    
    logger.info(f"Pool {pool_id} backup {'completed successfully' if ret == 0 else 'completed with errors'}")
    return ret


def backup_pool_metadata(pool: Dict[str, Any], conf: Dict[str, Any], exporter) -> int:
    """
    Backup pool metadata (configuration database)
    
    Args:
        pool: Pool configuration
        conf: Full configuration
        exporter: Exporter instance (XeExporter or HttpExporter)
        
    Returns:
        0 on success, -1 on error
    """
    pool_meta_filename = str_format(
        conf['env']['pool-metadata-template'],
        pool_name=pool['name'],
        pool_uuid=pool['uuid']
    )
    
    conf['env']['pool_meta_filename'] = pool_meta_filename
    
    # Use exporter to export pool metadata
    if not exporter.export_pool_metadata(pool, pool_meta_filename):
        logger.error("Error exporting pool metadata")
        return -1
    
    # Run after-metadata commands
    run_after_metadata_commands(pool, conf)
    
    return 0


def run_before_metadata_commands(pool: Dict[str, Any], conf: Dict[str, Any]):
    """Run configured before-metadata commands"""
    run_hook_commands('before', 'metadata', conf, context={
        'pool_name': pool['name'],
        'pool_uuid': pool['uuid']
    })


def run_before_job_commands(conf: Dict[str, Any]):
    """Run configured before-job commands (executed once before all pools)"""
    run_hook_commands('before', 'job', conf)


def run_after_job_commands(conf: Dict[str, Any]):
    """Run configured after-job commands (executed once after all pools)"""
    run_hook_commands('after', 'job', conf)


def run_after_metadata_commands(pool: Dict[str, Any], conf: Dict[str, Any]):
    """Run configured after-metadata commands"""
    run_hook_commands('after', 'metadata', conf, context={
        'pool_name': pool['name'],
        'pool_uuid': pool['uuid']
    })


def backup(conf: Dict[str, Any]) -> int:
    """
    Main backup function - orchestrates backup of all configured pools
    
    Args:
        conf: Configuration dictionary
        
    Returns:
        0 on success, -1 on error
    """
    logger.info("Starting VM backup job")
    
    # Validate and setup paths
    try:
        backup_path, log_path = validate_paths(conf)
    except RuntimeError as e:
        logger.error(f"Path validation failed: {e}")
        return -1
    
    # Change to backup directory
    original_path = os.getcwd()
    try:
        os.chdir(backup_path)
        logger.info(f"Changed working directory to: {backup_path}")
    except Exception as e:
        logger.error(f"Could not change to backup directory: {e}")
        return -1
    
    ret = 0
    
    try:
        # Run before-job hooks
        run_before_job_commands(conf)
        
        # Process all pools
        if 'pools' not in conf or not conf['pools']:
            logger.warning("No pools configured for backup")
            return 0
        
        total_pools = len(conf['pools'])
        successful_pools = 0
        failed_pools = 0
        
        for idx, pool in enumerate(conf['pools'], 1):
            logger.info(f"Processing pool {idx}/{total_pools}")
            
            try:
                pool_ret = pool_backup(pool, conf)
                if pool_ret == 0:
                    successful_pools += 1
                else:
                    failed_pools += 1
                    ret = -1
            except Exception as e:
                logger.error(f"Unexpected error processing pool: {e}", exc_info=True)
                failed_pools += 1
                ret = -1
        
        # Summary
        logger.info(f"{'='*60}")
        logger.info(f"Backup job summary:")
        logger.info(f"  Total pools: {total_pools}")
        logger.info(f"  Successful: {successful_pools}")
        logger.info(f"  Failed: {failed_pools}")
        logger.info(f"{'='*60}")
        
        # Run after-job commands
        run_after_job_commands(conf)
        
    finally:
        # Restore original directory
        os.chdir(original_path)
    
    logger.info("Backup job completed")
    return ret
