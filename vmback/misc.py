#!/usr/bin/env python3

import subprocess
from datetime import datetime

from .config import Config


complete_log = ''

def get_conf(c):
    conf = None
    try:
        conf = Config(c)
    except Exception as e:
        print(e)
        conf = None
    return conf


def log(msg):
    global complete_log

    now = datetime.now()
    dt = now.strftime('%Y-%m-%d %H:%M:%S')
    print(dt, msg)
    complete_log += dt + ' ' + msg + '\n'


def run_shell_command(cmd):
    log(cmd)
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
    for line in process.stdout:
        log(line.decode("utf-8"))
    errcode = process.wait()
    log(str(errcode))
    return errcode


def str_format(str, **kwargs):
    return str.format(**kwargs)
