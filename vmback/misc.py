#!/usr/bin/env python3

from .config import Config

def get_conf(c):
    conf = None
    try:
        conf = Config(c)
    except Exception as e:
        print(e)
        conf = None
    return conf
