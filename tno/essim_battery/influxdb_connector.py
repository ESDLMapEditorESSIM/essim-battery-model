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

from influxdb import InfluxDBClient

from tno.shared.log import get_logger

logger = get_logger(__name__)

INFLUX_USER = os.getenv('INFLUX_USER', 'admin')
INFLUX_PASS = os.getenv('INFLUX_PASS', 'admin')


class InfluxDBConnector:
    """ A connector writes data to an InfluxDB database.
    """

    def __init__(self, influx_server, influx_port, influx_database):
        """ Create an InfluxDB connector.
        :param influx_server: The server that hosts InfluxDB.
        :param influx_port: The port of InfluxDB.
        :param influx_database: The target influx database.
        """
        self.influx_server = influx_server.split('//')[-1]
        self.influx_port = influx_port
        self.influx_database = influx_database

        logger.debug("influx server: {}".format(self.influx_server))
        logger.debug("influx port: {}".format(self.influx_port))
        logger.debug("influx database: {}".format(self.influx_database))

        self.client = None

    def __connect(self):
        try:
            logger.debug("Connecting InfluxDBClient")
            client = InfluxDBClient(host=self.influx_server, port=self.influx_port, database=self.influx_database,
                                    username=INFLUX_USER, password=INFLUX_PASS)
            logger.debug("InfluxDBClient ping: {}".format(client.ping()))
            self.client = client
        except Exception as e:
            logger.debug("Caught exception: {}".format(e))
            if client is not None:
                client.close()
            self.client = None

    def query(self, query):
        if self.client is None:
            self.__connect()

        return self.client.query(query)

    def write(self, msgs):
        # if self.client is None:
        self.__connect()

        # Send message to database.
        self.client.write_points(msgs, database=self.influx_database, time_precision='s')

    def close(self):
        if self.client:
            self.client.close()
        self.client = None
