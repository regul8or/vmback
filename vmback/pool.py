#!/usr/bin/env python3

import pathlib
import XenAPI

from .misc import *

def pool_backup(pool, conf):

    ret = None
    if 'id' in pool:
        log(f'Backing up pool: {pool["id"]}')
    else:
        log('Backing up pool')

    if not 'hosts' in pool:
        log('*** FATAL: No hosts defined for pool')
        return -1
    if len(pool['hosts']) == 0:
        log('*** FATAL: No host addresses for pool')
        return -1

    session = None
    for host in pool['hosts']:
        log(f'Connecting to {host}')
        try:
            session = XenAPI.Session(f'http://{host}/')
            session.xenapi.login_with_password(conf['auth']['username'], conf['auth']['password'])
            break
        except Exception as err:
            log(f'Unexpected {err=}, {type(err)=}')
            log('*** ERROR: Could not connect')

    if session is not None:
        log('Connected')
    else:
        log('*** FATAL: Could not process a pool')
    """
    xenapi_pool = session.xenapi.pool.get_all()[0]
    print(xenapi_pool)
    pool_record = session.xenapi.pool.get_record(xenapi_pool)
    print(pool_record)
    """
    if 'metadata' in pool['scope']:
        meta_file = f'{pool["id"]}-meta.xml'
        log(f'Backing up pool metadata to {meta_file}')
        if 'pool-dump-database' not in conf['xe']:
            log('*** FATAL: No \'pool-dump-database\' config parameter specified')
            ret = -1
        else:
            if pathlib.Path(meta_file).exists():
                log(f'*** WARNING: {meta_file} file exists, removing it')
                pathlib.Path(meta_file).unlink()
            cmd = str_format(conf['xe']['pool-dump-database'], host=host, username=conf['auth']['username'], password=conf['auth']['password'], filename=meta_file)
            if run_shell_command(cmd) != 0:
                ret = -1

    if ret is None and 'vm' in pool['scope']:
        log(f'Backing up Virtual Machines')
        pass

    log(f'Clean Up')
    if 'metadata' in conf['after']:
        for str in conf['after']['metadata']:
            cmd = str_format(str, filename=meta_file)
            run_shell_command(cmd)

    if not session is None:
        session.logout()

    return 0
