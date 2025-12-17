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

from enum import Enum


class ExternalModelState(str, Enum):
    """
    Different states the external ESSIM model can be in.
    """

    UNINITIALIZED = "UNINITIALIZED"
    RECEIVED_CONFIG = "RECEIVED_CONFIG"
    WAITING_FOR_BID_REQUEST = "WAITING_FOR_BID_REQUEST"
    WAITING_FOR_ALLOCATION = "WAITING_FOR_ALLOCATION"
    FIRST_BID_REQUEST_RECEIVED = "FIRST_BID_REQUEST_RECEIVED"
    COMPLETE = "COMPLETE"
    ERROR = "ERROR"
