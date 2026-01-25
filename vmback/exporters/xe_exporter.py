"""
XE CLI exporter - legacy method using xe command-line tool
"""

import logging
from pathlib import Path
from typing import Dict, Any

from .base import BaseExporter, ExportError
from ..utils import str_format, run_shell_command, redact_credentials

logger = logging.getLogger(__name__)


class XeExporter(BaseExporter):
    """
    Exporter using xe CLI tool
    
    Requires:
    - xe command-line tool installed
    - Network access to XCP-ng host
    
    Advantages:
    - Battle-tested, mature
    - Works with all XCP-ng versions
    
    Disadvantages:
    - Requires xe CLI installation (hard dependency)
    - Shell command overhead
    - No native progress tracking
    """
    
    def export_pool_metadata(self, pool: Dict[str, Any], filename: str) -> bool:
        """Export pool metadata using xe pool-dump-database"""
        logger.info(f"Exporting pool metadata to '{filename}' (via xe CLI)")
        
        # Remove existing file
        file_path = Path(filename)
        if file_path.exists():
            logger.warning(f"File '{filename}' exists, removing it")
            try:
                file_path.unlink()
            except Exception as e:
                logger.error(f"Error removing existing file: {e}")
                return False
        
        # Build command
        cmd = str_format(
            self.config['xe']['pool-dump-database'],
            host=pool['master'],
            username=self.config['auth']['username'],
            password=self.config['auth']['password'],
            filename=filename
        )
        
        # Execute with redacted logging
        log_cmd = redact_credentials(cmd, self.config['auth']['username'], self.config['auth']['password'])
        
        if run_shell_command(cmd, log_cmd) != 0:
            logger.error("Pool metadata export failed")
            return False
        
        logger.info("Pool metadata export complete")
        return True
    
    def export_vm_metadata(self, vm: Dict[str, Any], pool: Dict[str, Any], filename: str) -> bool:
        """Export VM metadata using xe vm-export"""
        vm_uuid = vm['uuid']
        vm_name = vm['name_label']
        
        logger.info(f"Exporting VM metadata to '{filename}' (via xe CLI)")
        
        # Remove existing file
        file_path = Path(filename)
        if file_path.exists():
            logger.warning(f"File '{filename}' exists, removing it")
            try:
                file_path.unlink()
            except Exception as e:
                logger.error(f"Error removing existing file: {e}")
                return False
        
        # Build command
        cmd = str_format(
            self.config['xe']['vm-export'],
            host=pool['master'],
            username=self.config['auth']['username'],
            password=self.config['auth']['password'],
            uuid=vm_uuid,
            metadata='true',
            filename=filename
        )
        
        # Execute with redacted logging
        log_cmd = redact_credentials(cmd, self.config['auth']['username'], self.config['auth']['password'])
        
        if run_shell_command(cmd, log_cmd) != 0:
            logger.error("VM metadata export failed")
            return False
        
        logger.info("VM metadata export complete")
        return True
    
    def export_vm_full(self, vm_snapshot_uuid: str, pool: Dict[str, Any], filename: str) -> bool:
        """Export full VM using xe vm-export"""
        logger.info(f"Exporting VM to '{filename}' (via xe CLI)")
        
        # Remove existing file
        file_path = Path(filename)
        if file_path.exists():
            logger.warning(f"File '{filename}' exists, removing it")
            try:
                file_path.unlink()
            except Exception as e:
                logger.error(f"Error removing existing file: {e}")
                return False
        
        # Build command
        cmd = str_format(
            self.config['xe']['vm-export'],
            host=pool['master'],
            username=self.config['auth']['username'],
            password=self.config['auth']['password'],
            uuid=vm_snapshot_uuid,
            metadata='false',  # Full export with disks
            filename=filename
        )
        
        # Execute with redacted logging
        log_cmd = redact_credentials(cmd, self.config['auth']['username'], self.config['auth']['password'])
        
        if run_shell_command(cmd, log_cmd) != 0:
            logger.error("VM export failed")
            return False
        
        logger.info("VM export complete")
        return True
    
    def export_vdi(self, vdi_snapshot_uuid: str, pool: Dict[str, Any], filename: str) -> bool:
        """Export VDI using xe vdi-export"""
        logger.info(f"Exporting VDI to '{filename}' (via xe CLI)")
        
        # Remove existing file
        file_path = Path(filename)
        if file_path.exists():
            logger.warning(f"File '{filename}' exists, removing it")
            try:
                file_path.unlink()
            except Exception as e:
                logger.error(f"Error removing existing file: {e}")
                return False
        
        # Build command
        cmd = str_format(
            self.config['xe']['vdi-export'],
            host=pool['master'],
            username=self.config['auth']['username'],
            password=self.config['auth']['password'],
            uuid=vdi_snapshot_uuid,
            filename=filename
        )
        
        # Execute with redacted logging
        log_cmd = redact_credentials(cmd, self.config['auth']['username'], self.config['auth']['password'])
        
        if run_shell_command(cmd, log_cmd) != 0:
            logger.error("VDI export failed")
            return False
        
        logger.info("VDI export complete")
        return True
