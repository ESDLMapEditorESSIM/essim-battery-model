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
import re

from esdl import esdl, EnergyAsset, CostInformation, SingleValue
from esdl.esdl_handler import EnergySystemHandler
from influxdb import InfluxDBClient

from tno.shared.log import get_logger

logger = get_logger(__name__)
influx_cred = os.getenv('INFLUXDB_CREDENTIALS')
influx_cred_map = {}
if influx_cred is not None:
    for host_cred_combo in influx_cred.split(','):
        match = re.search(r'(.*:\/\/)*(\w+):(\w+)@([A-Za-z0-9\-\.]+)(:(\d+))*', host_cred_combo.strip())
        if len(match.groups()) != 6:
            logger.warning('Invalid credential combination specified: {}. Ignoring', host_cred_combo)
            continue
        else:
            scheme = match.group(1)
            username = match.group(2)
            password = match.group(3)
            url = match.group(4)
            port = match.group(6)
            influx_host = ''
            if scheme is not None and scheme not in url:
                influx_host = scheme + url
            else:
                influx_host = url
            if port is not None:
                influx_host = influx_host + ':' + port
            influx_cred_map[influx_host] = (username, password)
    logger.debug('Processed {} InfluxDB credentials'.format(len(influx_cred_map)))


class ESDLProcessor:

    def __init__(self):
        self.esh = EnergySystemHandler()
        self.energy_system: esdl.EnergySystem = None

    def load_string(self, esdl_string):
        self.energy_system = self.esh.load_from_string(esdl_string)

    def find_control_strategy(self, asset):
        services = self.energy_system.services
        if services:
            for s in services.service:
                if isinstance(s, esdl.ControlStrategy):
                    if s.energyAsset == asset:
                        return s
        return None

    def process_storage_strategy_info(self, asset_info, ss: esdl.StorageStrategy):
        if ss.marginalChargeCosts:
            asset_info['marginalChargeCosts'] = self.get_profile_info(ss.marginalChargeCosts)
        if ss.marginalDischargeCosts:
            asset_info['marginalDischargeCosts'] = self.get_profile_info(ss.marginalDischargeCosts)

    def get_asset_info(self, asset_id):
        asset: EnergyAsset = self.esh.get_by_id(asset_id)
        asset_info = dict()

        asset_info["name"] = asset.name
        if isinstance(asset, esdl.Battery):
            asset_info["capacity"] = asset.capacity
            asset_info["fillLevel"] = asset.fillLevel
            asset_info["maxChargeRate"] = asset.maxChargeRate
            asset_info["maxDischargeRate"] = asset.maxDischargeRate
            asset_info["selfDischargeRate"] = asset.selfDischargeRate
            asset_info["chargeEfficiency"] = asset.chargeEfficiency
            asset_info["dischargeEfficiency"] = asset.dischargeEfficiency

        # asset_info["marginal_cost"] = 0.5
        # if asset.costInformation:
        #     cost_info: CostInformation = asset.costInformation
        #     if cost_info.marginalCosts:
        #         if isinstance(cost_info.marginalCosts, SingleValue):
        #             asset_info["marginal_cost"] = cost_info.marginalCosts.value

        cs = self.find_control_strategy(asset)
        if cs:
            if isinstance(cs, esdl.StorageStrategy):
                self.process_storage_strategy_info(asset_info, cs)

        return asset_info

    def get_carriers_for_asset(self, asset_id):
        asset = self.esh.get_by_id(asset_id)
        carrier_dict = dict()
        carrier_cost = {}
        if asset:
            for port in asset.port:
                carrier = port.carrier
                carrier_cost = {}
                if carrier.cost:
                    if isinstance(carrier.cost, esdl.InfluxDBProfile):
                        carrier_cost = {'carrier_cost': self.get_influxdb_profile(self.get_profile_info(carrier.cost))}
                    elif isinstance(carrier.cost, esdl.SingleValue):
                        carrier_cost = {'carrier_cost': carrier.cost.value}
                    else:
                        raise ValueError('Only InfluxDB carrier cost profiles are currently supported.')

                profile_info = None
                if port.profile:
                    profile = port.profile[0]
                    if isinstance(profile, esdl.InfluxDBProfile):
                        profile_info = {
                            'values': self.get_influxdb_profile(self.get_profile_info(profile)),
                            'unit': 'JOULE'
                        }
                        if profile.profileQuantityAndUnit:
                            profile_info['unit'] = profile.profileQuantityAndUnit.unit

                carrier_dict[carrier.id] = {
                    'port_id': port.id,
                    'port_type': port.eClass.name,
                    'port_profile': profile_info,
                    'carrier_type': carrier.eClass.name,
                    'carrier_name': carrier.name,
                    **carrier_cost
                }
        return carrier_dict

    @staticmethod
    def get_influxdb_profile(profile_info):
        profile_host = profile_info['host']
        influx_host = '{}:{}'.format(profile_host, profile_info['port'])
        if influx_host in influx_cred_map:
            (username, password) = influx_cred_map[influx_host]
        else:
            username = None
            password = None
        ssl_setting = False
        if 'https' in profile_host:
            profile_host = profile_host[8:]
            ssl_setting = True
        elif 'http' in profile_host:
            profile_host = profile_host[7:]
        if profile_info['port'] == 443:
            ssl_setting = True
        if profile_info['startDate'] is not None:
            profile_start_date = str(profile_info['startDate'].isoformat()).replace('T', ' ')
        else:
            raise ValueError(f'Start date missing in profile {profile_info}')
        if profile_info['endDate'] is not None:
            end_date_suffix = " AND time <= '{}'".format(str(profile_info['endDate'].isoformat()).replace('T', ' '))
        else:
            raise ValueError(f'End date missing in profile {profile_info}')
        query = 'SELECT ("{}") FROM "{}" WHERE time >= \'{}\'{}'.format(
            profile_info['field'],
            profile_info['measurement'],
            profile_start_date,
            end_date_suffix)

        client = InfluxDBClient(host=profile_host, port=profile_info['port'], username=username,
                                password=password, ssl=ssl_setting, verify_ssl=ssl_setting)
        client.switch_database(profile_info['database'])
        data = client.query(query=query)
        data_points = [t[1] for t in data.raw["series"][0]["values"]]

        logger.info(f"First 10/{len(data_points)} influxdb data_points for {profile_info['field']}: {', '.join([str(p) for p in data_points[:10]])}")
        return data_points

        #
        # influxdb_client = InfluxDBConnector(profile_info["host"], profile_info["port"], profile_info["database"])
        #
        # query = f"SELECT {profile_info['field']} FROM {profile_info['measurement']} WHERE " \
        #         + f"time >= '{profile_info['startDate']}' AND time < '{profile_info['endDate']}'"
        # logger.debug(query)
        #
        # rs = influxdb_client.query(query)
        # results = list(rs.get_points(measurement=profile_info["measurement"]))
        # profile = list(map(lambda x: x[profile_info["field"]], results))
        # return profile

    def get_profile_info(self, profile):
        profile_info = dict()
        if isinstance(profile, esdl.SingleValue):
            profile_info["type"] = "SingleValue"
            profile_info["value"] = profile.value
        if isinstance(profile, esdl.InfluxDBProfile):
            profile_info["type"] = "InfluxDBProfile"
            profile_info["multiplier"] = profile.multiplier
            profile_info["host"] = profile.host
            profile_info["port"] = profile.port
            profile_info["database"] = profile.database
            profile_info["measurement"] = profile.measurement
            profile_info["field"] = profile.field
            profile_info["startDate"] = profile.startDate
            profile_info["endDate"] = profile.endDate
        if isinstance(profile, esdl.TimeSeriesProfile):
            profile_info["type"] = "TimeSeriesProfile"
            profile_info["startDateTime"] = profile.startDateTime
            profile_info["timestep"] = profile.timestep
            profile_info["values"] = list(profile.values)       # Cast EList to list

        return profile_info
