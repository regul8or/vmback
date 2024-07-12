#!/usr/bin/env python3

import subprocess

from datetime import datetime
from pathlib import Path
from dotenv import dotenv_values

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


def check_conf_parameter(node, param):
    if node is not None and param not in node:
        log('*** FATAL: No \'' + param + '\' config parameter specified')
        return -1
    return 0


def get_env(conf):
    username = None
    password = None
    env = dotenv_values('.env')
    if 'XEN_USERNAME' in env:
        username = env['XEN_USERNAME']
    if 'XEN_PASSWORD' in env:
        password = env['XEN_PASSWORD']

    if username is None or password is None:
        return -1
    conf.add('auth', { 'username': username, 'password': password })
    return 0


def log(msg):
    global complete_log

    now = datetime.now()
    dt = now.strftime('%Y-%m-%d %H:%M:%S')
    print(dt, msg)
    complete_log += dt + ' ' + msg + '\n'


def log_export(log_path):
    global complete_log

    now = datetime.now()
    file_name = 'vmback-' + now.strftime('%Y%m%d-%H%M%S') + '.log'
    file = Path(log_path) / file_name
    with file.open('w') as f:
        f.write(complete_log)


def run_shell_command(cmd):
    log(cmd)
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
    for line in process.stdout:
        log(line.decode("utf-8").rstrip())
    errcode = process.wait()
    log(str(errcode))
    return errcode


def str_format(str, **kwargs):
    return str.format(**kwargs)


def get_ymd():
    now = datetime.now()
    return { 'y':now.year, 'm':now.month, 'd':now.day }
