#!/usr/bin/env python3
"""
VM Backup - Main entry point
Command-line interface for XCP-ng backup utility
"""

import sys
import argparse
import logging

from .config import load_config, ConfigError
from .logging_setup import setup_logging
from .backup import backup
from .list_vm import list_vm
from .list_vdi import list_vdi


def main():
    """Main entry point for vmback"""
    parser = argparse.ArgumentParser(
        prog='vmback',
        description='Backup XCP-ng Virtual Machines and Virtual Disk Images',
        epilog='For more information, see the documentation.'
    )
    
    parser.add_argument(
        'mode',
        choices=['backup', 'vm', 'vdi'],
        help='Action to perform: backup (run backup), vm (list VMs), vdi (list VDIs)'
    )
    
    parser.add_argument(
        '-c', '--config',
        dest='conf',
        default='config.yaml',
        help='Path to configuration YAML file (default: config.yaml)'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose (DEBUG) logging'
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version='%(prog)s 2.2.3'
    )
    
    args = parser.parse_args()
    
    # Load configuration
    try:
        print(f"Loading configuration from: {args.conf}")
        conf = load_config(args.conf)
    except ConfigError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error loading configuration: {e}", file=sys.stderr)
        return 1
    
    # Override log level if verbose
    if args.verbose:
        if 'logging' not in conf._config:
            conf._config['logging'] = {}
        conf._config['logging']['level'] = 'DEBUG'
    
    # Setup logging
    vmback_logger = setup_logging(conf._config)
    logger = logging.getLogger('vmback')
    
    logger.info(f"VM Backup v2.2.3 - Mode: {args.mode}")
    logger.info(f"Configuration file: {args.conf}")
    
    # Execute requested action
    ret = 0
    
    try:
        if args.mode == 'backup':
            ret = backup(conf)
        elif args.mode == 'vm':
            ret = list_vm(conf)
        elif args.mode == 'vdi':
            ret = list_vdi(conf)
        else:
            logger.error(f"Invalid mode: {args.mode}")
            ret = 1
    
    except KeyboardInterrupt:
        logger.warning("Operation cancelled by user")
        ret = 130
    
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        ret = 1
    
    if ret == 0:
        logger.info("Operation completed successfully")
    else:
        logger.error(f"Operation completed with errors (exit code: {ret})")
    
    return ret


if __name__ == '__main__':
    sys.exit(main())
