#!/usr/bin/env python3

import XenAPI

from pathlib import Path

from .misc import *


def pool_connect(pool, conf):
    session = None

    if not 'hosts' in pool:
        log('*** FATAL: No hosts defined for pool')
        return None
    if len(pool['hosts']) == 0:
        log('*** FATAL: No host addresses for pool')
        return None

    for host in pool['hosts']:
        log(f'Connecting to {host}')
        try:
            session = XenAPI.Session(f'http://{host}/')
            session.xenapi.login_with_password(conf['auth']['username'], conf['auth']['password'])
            pool['master'] = host
            break
        except Exception as err:
            log(f'Unexpected {err=}, {type(err)=}')
            log('*** ERROR: Could not connect')
    return session
