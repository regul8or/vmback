"""
Base exporter class for XCP-ng exports
"""

from abc import ABC, abstractmethod
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class ExportError(Exception):
    """Export operation error"""
    pass


class BaseExporter(ABC):
    """
    Abstract base class for XCP-ng exporters
    
    Implementations:
    - XeExporter: Uses xe CLI (legacy, requires xe tools installed)
    - HttpExporter: Uses direct HTTP API calls (recommended, no dependencies)
    """
    
    def __init__(self, session, config: Dict[str, Any]):
        """
        Initialize exporter
        
        Args:
            session: XenAPI session
            config: Full configuration dictionary
        """
        self.session = session
        self.config = config
    
    @abstractmethod
    def export_pool_metadata(self, pool: Dict[str, Any], filename: str) -> bool:
        """
        Export pool metadata (database dump)
        
        Args:
            pool: Pool configuration
            filename: Output filename
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def export_vm_metadata(self, vm: Dict[str, Any], pool: Dict[str, Any], filename: str) -> bool:
        """
        Export VM metadata (configuration without disks)
        
        IMPORTANT: Must use original VM record, NOT snapshot
        XenAPI does not allow metadata export from snapshots
        
        Args:
            vm: VM record from XenAPI (original VM, not snapshot)
            pool: Pool configuration
            filename: Output filename
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def export_vm_full(self, vm_snapshot_uuid: str, pool: Dict[str, Any], filename: str) -> bool:
        """
        Export full VM (metadata + all disks as .xva)
        
        Args:
            vm_snapshot_uuid: UUID of VM snapshot to export
            pool: Pool configuration
            filename: Output filename
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def export_vdi(self, vdi_snapshot_uuid: str, pool: Dict[str, Any], filename: str) -> bool:
        """
        Export VDI (virtual disk image)
        
        Args:
            vdi_snapshot_uuid: UUID of VDI snapshot to export
            pool: Pool configuration
            filename: Output filename
            
        Returns:
            True if successful, False otherwise
        """
        pass


def create_exporter(session, config: Dict[str, Any]) -> BaseExporter:
    """
    Factory function to create appropriate exporter based on config
    
    Args:
        session: XenAPI session
        config: Full configuration dictionary
        
    Returns:
        Exporter instance (XeExporter or HttpExporter)
    """
    from .xe_exporter import XeExporter
    from .http_exporter import HttpExporter
    
    # Determine export method
    export_config = config.get('export', {})
    method = export_config.get('method', 'xe')  # Default to 'xe' for backward compat
    
    if method == 'http':
        logger.info("Using HTTP export method (direct XenAPI)")
        return HttpExporter(session, config)
    elif method == 'xe':
        logger.info("Using XE CLI export method (legacy)")
        return XeExporter(session, config)
    else:
        raise ValueError(f"Unknown export method: {method}. Valid options: 'xe', 'http'")
