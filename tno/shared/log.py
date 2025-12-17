#!/usr/bin/env python
#  This work is based on original code developed and copyrighted by TNO 2025.
#  Subsequent contributions are licensed to you by the developers of such code and are
#  made available to the Project under one or several contributor license agreements.
#
#  This work is licensed to you under the Apache License, Version 2.0.
#  You may obtain a copy of the license at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Contributors:
#      TNO         - Initial implementation
#  Manager:
#      TNO

import os

import log4p

LOG4P_JSON_LOCATION = os.getenv('LOG4P_JSON_LOCATION', r'../shared/log4p.json')


def get_logger(name):
    return log4p.GetLogger(name, config=LOG4P_JSON_LOCATION).logger
