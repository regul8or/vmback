#!/usr/bin/env python3

import os

from pathlib import Path

from .config import Config
from .misc import *
from .xapi import *
from .backup_vdi import backup_vdi
from .backup_vm import backup_vm


def backup(conf):
    prev_path = None
    if 'backup-path' in conf['env']:
        backup_path = conf['env']['backup-path']
        if Path(backup_path).exists():
            prev_path = os.getcwd()
            os.chdir(backup_path)
        else:
            log(f'*** WARNING: Backup path {backup_path} does not exist')
    log(f'Backup path: {os.getcwd()}')
    if not os.access(os.getcwd(), os.W_OK):
        log('*** FATAL: Backup path is not writable')
        return -1

    if 'log-path' in conf['env']:
        log_path = conf['env']['log-path']
        if not Path(log_path).exists():
            log(f'*** WARNING: Log path {log_path} does not exist')
            log_path = os.getcwd()
    log(f'Log path: {log_path}')
    if not os.access(log_path, os.W_OK):
        log('*** FATAL: Log path is not writable')
        return -1

    if 'pool-dump-database' not in conf['xe']:
        log('*** FATAL: No \'pool-dump-database\' config parameter specified')
        return -1
    if 'vdi-export' not in conf['xe']:
        log('*** FATAL: No \'vdi-export\' config parameter specified')
        return -1
    if 'vm-export' not in conf['xe']:
        log('*** FATAL: No \'vm-export\' config parameter specified')
        return -1

    if 'pools' in conf:
        pools = conf['pools']
        for pool in pools:
            try:
                pool_backup(pool, conf)
            except Exception as err:
                log(f'Unexpected {err=}, {type(err)=}')

    log('Closing Log')
    log_export(log_path)

    if prev_path is not None:
        os.chdir(prev_path)

    return 0


def pool_backup(pool, conf):

    ret = None
    if 'id' in pool:
        log(f'Backing up pool: {pool["id"]}')
    else:
        log('Backing up pool')

    session = pool_connect(pool, conf)
    if session is None:
        log('*** FATAL: Could not process a pool')
        return -1
    log(f'Connected, session id: {session.xenapi.session.get_uuid(session._session)}')

    if 'metadata' in pool['scope']:
        meta_file = f'{pool["id"]}-meta.xml'
        log(f'Backing up pool metadata to {meta_file}')
        if Path(meta_file).exists():
            log(f'*** WARNING: {meta_file} file exists, removing it')
            Path(meta_file).unlink()
        cmd = str_format(conf['xe']['pool-dump-database'], host=pool['master'], username=conf['auth']['username'], password=conf['auth']['password'], filename=meta_file)
        if run_shell_command(cmd) != 0:
            ret = -1

    if ret is None and 'vm' in pool['scope'] and 'vm' in conf and conf['vm'] is not None:
        log(f'Backing up Virtual Machines')
        ret = backup_vm(session, pool, conf)

    if ret is None and 'vdi' in pool['scope'] and 'vdi' in conf and conf['vdi'] is not None:
        log(f'Backing up Virtual Disk Images')
        ret = backup_vdi(session, pool, conf)

    log(f'Clean Up')
    if 'metadata' in conf['after'] and conf['after']['metadata'] is not None:
        for str in conf['after']['metadata']:
            cmd = str_format(str, filename=meta_file)
            run_shell_command(cmd)

    if session is not None:
        log('Closing session')
        session.logout()

    return ret
