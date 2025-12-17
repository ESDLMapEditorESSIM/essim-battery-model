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

import base64
import json
import os
import struct
import traceback
from datetime import datetime
from urllib.parse import urlparse

import paho.mqtt.client as mqtt

from tno.essim_battery.battery_node import BatteryNode
from tno.essim_battery.enums import ExternalModelState
from tno.essim_battery.esdl_processor import ESDLProcessor
from tno.essim_battery.influxdb_connector import InfluxDBConnector
from tno.shared.log import get_logger

ESSIM_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S%z"

logger = get_logger(__name__)

R_AIR_INSIDE = 0.13
R_AIR_OUTSIDE = 0.04
horizon = int(os.getenv('CONTROLLER_HORIZON', '4'))
MSO_ENABLE = os.getenv('MSO_ENABLE', 'false')


class ESSIMMQTTClient:
    def __init__(self,
                 server,
                 port=1883,
                 mqtt_username=None,
                 mqtt_password=None,
                 env_essim_id=None,
                 env_simulation_id=None,
                 env_model_id=None):
        # MQTT information
        self.server = server
        self.port = port
        self.mqtt_username = mqtt_username
        self.mqtt_password = mqtt_password
        self.topic = None
        self.node_id = None
        self.client = None

        # used to store the first timestamp we receive from ESSIM in the createBid message
        self.start_timestamp = None

        # InfluxDB information
        self.influxdb_client = None
        self.start_datetime = None
        self.end_datetime = None
        self.simulation_info = dict()

        # ESDL information
        self.esdl_processor = ESDLProcessor()
        self.energy_system_id = None
        self.carriers_info = None

        # Time Window information
        self.charge_time_windows = None
        self.discharge_time_windows = None

        # Scaling node information
        self.env_essim_id = '' if env_essim_id is None else env_essim_id
        self.env_simulation_id = '' if env_simulation_id is None else env_simulation_id
        self.env_model_id = '' if env_model_id is None else env_model_id

        self.scenario_id = None
        self.simulation_id = None
        self.battery_node = None

        self.model_state = ExternalModelState.UNINITIALIZED

    def connect(self, topic, node_id):
        self.topic = topic
        self.node_id = node_id

        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        if self.mqtt_username and self.mqtt_password:
            logger.info(f"Using MQTT username {self.mqtt_username} & password <hidden> for connecting.")
            self.client.username_pw_set(self.mqtt_username, self.mqtt_password)
        self.client.connect(host=self.server, port=self.port)

    def on_connect(self, client, userdata, flags, rc):
        logger.debug("Connected with result code " + str(rc))
        topic = "{}/node/{}/#".format(self.topic, self.node_id)
        logger.info("Subscribed to {}".format(topic))
        self.client.subscribe(topic, qos=2)

    def on_message(self, client, userdata, msg):
        logger.debug("==================================================")
        logger.debug(f"topic: {msg.topic}, model state: {self.model_state}")
        try:
            if str(msg.topic).endswith("/config"):
                if self.model_state == ExternalModelState.UNINITIALIZED:
                    logger.info("Received config message!")
                    self.model_state = ExternalModelState.RECEIVED_CONFIG
                    self.start_timestamp = None
                    logger.debug(msg.payload)
                    payload_bytes = msg.payload
                    payload_string = payload_bytes.decode("utf-8")
                    try:
                        payload_json = json.loads(payload_string)
                        self.process_json_payload(payload_json)
                        self.simulation_info = self.create_simulation_info()
                        self.carriers_info = self.esdl_processor.get_carriers_for_asset(self.node_id)
                        asset_info = self.esdl_processor.get_asset_info(self.node_id)
                        logger.info(f"Asset information: {asset_info}")
                        self.battery_node = BatteryNode(
                            asset_info=asset_info,
                            carriers_info=self.carriers_info,
                            simulation_info=self.simulation_info,
                            charge_time_windows=self.charge_time_windows,
                            discharge_time_windows=self.discharge_time_windows
                        )
                        self.model_state = ExternalModelState.WAITING_FOR_BID_REQUEST
                    except Exception as e:
                        logger.error(traceback.format_exc())
                        self.model_state = ExternalModelState.ERROR

            elif str(msg.topic).endswith("/createBid"):
                # {
                #     "timeStamp": 1546300800,
                #     "minPrice": 0,
                #     "timeStepInSeconds": 3600,
                #     "maxPrice": 1,
                #     "carrierId": "29903bc6-f798-4eb8-beb9-48862bec646b"
                # }

                payload_bytes = msg.payload
                payload_string = payload_bytes.decode("utf-8")
                try:
                    payload_json = json.loads(payload_string)
                    timestamp = payload_json["timeStamp"]
                    minprice = payload_json["minPrice"]
                    duration = payload_json["timeStepInSeconds"]
                    maxprice = payload_json["maxPrice"]
                    carrier_id = payload_json["carrierId"]

                    if not self.start_timestamp:
                        self.start_timestamp = timestamp

                    logger.debug(
                        f"received createBid ({self.carriers_info[carrier_id]['carrier_type']}): "
                        f"t={timestamp} ({int((timestamp - self.start_timestamp) / 3600)})"
                        f", d={duration}, pmin={minprice}, pmax={maxprice}")
                    logger.debug("--------------------------------------------------")

                    step_nr = int((timestamp - self.start_timestamp) / 3600)

                    logger.debug(f"create bidcurve for {self.carriers_info[carrier_id]['carrier_type']}")
                    # self.building_node.calculate_p_heat(step_nr, duration, carrier_id)
                    bid_curve = self.battery_node.create_bid_curve(step_nr, timestamp, duration, minprice, maxprice,
                                                                   carrier_id, )

                    response = struct.pack(">q", timestamp)
                    for b in bid_curve:
                        response = response + struct.pack(">dd", b[0], b[1])

                    logger.debug(
                        f"send ({self.carriers_info[carrier_id]['carrier_type']}): t={timestamp}, points={bid_curve}")
                    client.publish(
                        "{}/simulation/{}/{}/bid".format(self.topic, self.node_id, carrier_id),
                        response)

                    self.model_state = ExternalModelState.WAITING_FOR_ALLOCATION
                except Exception as e:
                    logger.error(traceback.format_exc())
            elif str(msg.topic).endswith("/allocate"):
                # {
                #     "timeStamp": 1546387200,
                #     "price": 1,
                #     "carrierId": "29903bc6-f798-4eb8-beb9-48862bec646b"
                # }
                self.model_state = ExternalModelState.WAITING_FOR_BID_REQUEST

                payload_bytes = msg.payload
                payload_string = payload_bytes.decode("utf-8")
                try:
                    payload_json = json.loads(payload_string)
                    timestamp = payload_json["timeStamp"]
                    price = payload_json["price"]
                    carrier_id = payload_json["carrierId"]
                    logger.debug(
                        f"Received allocation ({self.carriers_info[carrier_id]['carrier_type']}): "
                        f"price {price} for timestamp t={timestamp} "
                        f"({int((timestamp - self.start_timestamp) / 3600)})")
                    # logger.debug(f"carrier_info: {self.carriers_info[carrier_id]}")
                    logger.debug("--------------------------------------------------")
                    step_nr = int((timestamp - self.start_timestamp) / 3600)
                    self.battery_node.process_allocation(step_nr, price, carrier_id)

                except Exception as e:
                    logger.error(traceback.format_exc())
            elif str(msg.topic).endswith("/stop"):
                # {
                #     "carrierId": "29903bc6-f798-4eb8-beb9-48862bec646b"
                # }
                payload_bytes = msg.payload
                payload_string = payload_bytes.decode("utf-8")
                try:
                    payload_json = json.loads(payload_string)
                    carrier_id = payload_json["carrierId"]
                    logger.debug(f"Received stop message ({self.carriers_info[carrier_id]['carrier_name']})")

                    self.battery_node.write_results(self.influxdb_client, self.simulation_id, self.start_timestamp)
                    self.model_state = ExternalModelState.UNINITIALIZED
                    logger.info("Done")
                except Exception as e:
                    logger.error(traceback.format_exc())
            else:
                logger.error(f"Unknown command received: {msg.topic}")
        except Exception as e:
            logger.error(traceback.format_exc())

        logger.debug('^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^')

    def loop(self):
        try:
            self.client.loop_forever()
        except KeyboardInterrupt:
            self.client.disconnect()
            print("")

    def process_json_payload(self, json_payload):
        if "esdlContents" in json_payload:
            esdlstr_base64 = json_payload["esdlContents"]
            esdlstr_bytes = esdlstr_base64.encode("ascii")
            esdlstr_base64_bytes = base64.b64decode(esdlstr_bytes)
            esdlstr = esdlstr_base64_bytes.decode("ascii")
            self.esdl_processor.load_string(esdlstr)
            self.energy_system_id = self.esdl_processor.energy_system.id
        if "simulationId" in json_payload:
            self.simulation_id = json_payload["simulationId"]
        if "config" in json_payload:
            try:
                if "scenarioID" in json_payload["config"]:
                    self.scenario_id = json_payload["config"]["scenarioID"]
                else:
                    self.scenario_id = self.energy_system_id
                if "influxUrl" in json_payload["config"]:
                    influx_url = urlparse(json_payload["config"]["influxUrl"])
                    influx_host = influx_url.hostname
                    influx_port = influx_url.port

                    self.influxdb_client = InfluxDBConnector(influx_host, influx_port, self.scenario_id)
                if "startDate" in json_payload["config"]:
                    self.start_datetime = datetime.strptime(json_payload["config"]["startDate"], ESSIM_DATE_FORMAT)
                if "endDate" in json_payload["config"]:
                    self.end_datetime = datetime.strptime(json_payload["config"]["endDate"], ESSIM_DATE_FORMAT)
                if "chargeTimeWindows" in json_payload["config"]:
                    self.charge_time_windows = json_payload["config"]["chargeTimeWindows"]
                else:
                    self.charge_time_windows = None
                if "dischargeTimeWindows" in json_payload["config"]:
                    self.discharge_time_windows = json_payload["config"]["dischargeTimeWindows"]
                else:
                    self.discharge_time_windows = None
            except Exception as e:
                logger.error(e)

    def get_number_of_ESSIM_simulation_steps(self):
        if self.start_datetime and self.end_datetime:
            difference = self.end_datetime - self.start_datetime
            diff_in_s = difference.total_seconds()
            diff_in_h = int(divmod(diff_in_s, 3600)[0])
            return diff_in_h + 1  # Assume hourly simulations
        else:
            raise Exception("No start and enddate provided to external model")

    def create_simulation_info(self):
        return {
            "stepsize_in_seconds": 3600,  # Assume hourly simulations for now
            "start_datetime": f"{self.start_datetime.strftime(ESSIM_DATE_FORMAT)}",
            "end_datetime": f"{self.end_datetime.strftime(ESSIM_DATE_FORMAT)}",
            "number_of_steps": self.get_number_of_ESSIM_simulation_steps() + 1,
        }

    def get_profile(self, profile_info):
        profile = []
        num_steps = self.get_number_of_ESSIM_simulation_steps()
        if profile_info["type"] == "SingleValue":
            for s in range(num_steps):
                profile.append(profile_info["value"])
            return profile
        elif profile_info["type"] == "InfluxDBProfile":
            return ESDLProcessor.get_influxdb_profile(profile_info)
        elif profile_info["type"] == "TimeSeriesProfile":
            return profile_info["values"]
        else:
            raise Exception("Unsupported profile type")
