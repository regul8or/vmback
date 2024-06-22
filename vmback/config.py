#!/usr/bin/env python3

import pathlib
import yaml

class Config:

    _conf = None
    _list = None

    def __init__(self, file_name):
        if Config._conf is None:
            if pathlib.Path(file_name).exists():
                with open(file_name, 'r') as file:
                    Config._conf = yaml.safe_load(file)
                    Config._list = list(Config._conf)
            else:
                raise Exception('Config file is not found')

    def __getitem__(self, index):
        if index in Config._conf:
            return Config._conf[index]
        else:
            return Config._list[index]

    def __repr__(self):
        return str(Config._conf)

    def add(self, key, value):
        Config._conf[key] = value
