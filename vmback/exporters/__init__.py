"""
Export module for XCP-ng VM and VDI exports

Provides pluggable export methods:
- XE CLI (legacy, requires xe tool)
- HTTP (direct API, recommended)
"""

from .base import BaseExporter, ExportError, create_exporter
from .xe_exporter import XeExporter
from .http_exporter import HttpExporter

__all__ = [
    'BaseExporter',
    'ExportError',
    'create_exporter',
    'XeExporter',
    'HttpExporter',
]
