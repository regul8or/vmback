#!/usr/bin/env python3

import os
import re

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

    if check_conf_parameter(conf['xe'], 'pool-dump-database') == -1: return -1
    if check_conf_parameter(conf['xe'], 'vdi-export') == -1: return -1
    if check_conf_parameter(conf['xe'], 'vm-export') == -1: return -1
    if check_conf_parameter(conf['env'], 'pool-metadata-template') == -1: return -1
    if check_conf_parameter(conf['env'], 'vdi-template') == -1: return -1
    if check_conf_parameter(conf['env'], 'vm-metadata-template') == -1: return -1
    if check_conf_parameter(conf['env'], 'vm-template') == -1: return -1

    if 'pools' in conf:
        pools = conf['pools']
        for pool in pools:
            try:
                pool_backup(pool, conf)
            except Exception as err:
                log(f'Unexpected {err=}, {type(err)=}')

    log(f'Running After Job Commands')
    if 'job' in conf['after'] and conf['after']['job'] is not None:
        now = get_ymd()
        for str in conf['after']['job']:
            cmd = str_format(str, y=now['y'], m=now['m'], d=now['d'])
            run_shell_command(cmd)

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

    pool_meta_filename = str_format(conf['env']['pool-metadata-template'], pool_name=pool['name'], pool_uuid=pool['uuid'])
    conf['env']['pool_meta_filename'] = pool_meta_filename
    if 'metadata' in pool['scope']:
        log(f'Backing up pool metadata to "{pool_meta_filename}"')
        if Path(pool_meta_filename).exists():
            log(f'*** WARNING: {pool_meta_filename} file exists, removing it')
            Path(pool_meta_filename).unlink()
        cmd = str_format(conf['xe']['pool-dump-database'], host=pool['master'], username=conf['auth']['username'], password=conf['auth']['password'], filename=pool_meta_filename)
        if run_shell_command(cmd) != 0:
            ret = -1

    log(f'Running After Metadata Commands')
    if 'metadata' in conf['after'] and conf['after']['metadata'] is not None:
        now = get_ymd()
        for str in conf['after']['metadata']:
            cmd = str_format(str, pool_name=re.escape(pool['name']), pool_uuid=pool['uuid'], y=now['y'], m=now['m'], d=now['d'])
            run_shell_command(cmd)

    if ret is None and 'vm' in pool['scope'] and 'vm' in conf and conf['vm'] is not None:
        log(f'Backing up Virtual Machines')
        ret = backup_vm(session, pool, conf)

    if ret is None and 'vdi' in pool['scope'] and 'vdi' in conf and conf['vdi'] is not None:
        log(f'Backing up Virtual Disk Images')
        ret = backup_vdi(session, pool, conf)

    if session is not None:
        log('Closing session')
        session.logout()

    return ret
