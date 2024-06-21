#!/usr/bin/env python3

import pathlib
import yaml

class Config:

    _conf = None

    def __init__(self, file_name):
        if Config._conf is None:
            if pathlib.Path(file_name).exists():
                with open(file_name, 'r') as file:
                    Config._conf = yaml.safe_load(file)
            else:
                raise Exception('Config file is not found')

    def get(self):
        return Config._conf
