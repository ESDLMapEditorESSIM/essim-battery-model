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

from tno.essim_battery.essim_mqtt_client import ESSIMMQTTClient

essim_topic = "essim"

MQTT_HOST = os.getenv('MQTT_HOST', 'localhost')
MQTT_PORT = int(os.getenv('MQTT_PORT', '1883'))
MQTT_USERNAME = os.getenv('MQTT_USERNAME', None)
MQTT_PASSWORD = os.getenv('MQTT_PASSWORD', None)
ESSIM_ID = os.getenv('ESSIM_ID', None)
SIMULATION_ID = os.getenv('SIMULATION_ID', None)
MODEL_ID = os.getenv('MODEL_ID', 'BATT1')

print('MQTT_HOST:     ', MQTT_HOST)
print('MQTT_PORT:     ', MQTT_PORT)
print('MQTT_USERNAME: ', MQTT_USERNAME)
print('MQTT_PASSWORD: ', '<hidden>')
print('ESSIM_ID:      ', ESSIM_ID)
print('SIMULATION_ID: ', SIMULATION_ID)
print('MODEL_ID:      ', MODEL_ID)

essim_mqtt_client = ESSIMMQTTClient(
    MQTT_HOST,
    MQTT_PORT,
    mqtt_username=MQTT_USERNAME,
    mqtt_password=MQTT_PASSWORD,
    env_essim_id=ESSIM_ID,
    env_simulation_id=SIMULATION_ID,
    env_model_id=MODEL_ID
)
essim_mqtt_client.connect(topic=essim_topic, node_id=MODEL_ID)
essim_mqtt_client.loop()
