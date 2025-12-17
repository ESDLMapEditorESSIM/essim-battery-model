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

import hashlib
import os
import re
from typing import Union

import log4p
import numpy as np
import pandas as pd
from esdl import esdl, Port, ProfileReference
from influxdb import InfluxDBClient

logger = log4p.GetLogger(__name__, config='log4p.json')
log = logger.logger
influx_cred = os.getenv('INFLUXDB_CREDENTIALS')


class ESDLProfileProcessor:
    """
    ESDL Data Store to extract and pre-process profile data into data frames

    """

    def __init__(self, start_date, end_date, time_step):
        self.start_date = start_date
        self.end_date = end_date
        self.time_step = time_step
        ts = self.time_step.total_seconds()
        self.time_step_notation = '{}s'.format(int(ts))
        self.time_range = pd.date_range(self.start_date, self.end_date, freq=self.time_step_notation)
        self.data_frames = None
        self.asset_data = {}
        self.data_cache = {}
        self.data_type = {}
        self.factor = {
            "ENERGY_IN_WH": 3.6 * 1e3,
            "ENERGY_IN_KWH": 3.6 * 1e6,
            "ENERGY_IN_MWH": 3.6 * 1e9,
            "ENERGY_IN_GWH": 3.6 * 1e12,
            "ENERGY_IN_TWH": 3.6 * 1e15,
            "ENERGY_IN_PWH": 3.6 * 1e18,
            "ENERGY_IN_J": 1,
            "ENERGY_IN_KJ": 1e3,
            "ENERGY_IN_MJ": 1e6,
            "ENERGY_IN_GJ": 1e9,
            "ENERGY_IN_TJ": 1e12,
            "ENERGY_IN_PJ": 1e15,
            "POWER_IN_W": 1 * ts,
            "POWER_IN_KW": 1e3 * ts,
            "POWER_IN_MW": 1e6 * ts,
            "POWER_IN_GW": 1e9 * ts,
            "POWER_IN_TW": 1e12 * ts,
            "POWER_IN_PW": 1e15 * ts
        }
        self.mult_suffix = {
            "NONE": "",
            "KILO": "K",
            "MEGA": "M",
            "GIGA": "G",
            "TERRA": "T",
            "TERA": "T",
            "PETA": "P",
            "MILLI": "-",
            "MICRO": "-",
            "NANO": "-",
            "PICO": "-"
        }

        # Process credential info supplied in environment variable INFLUXDB_CREDENTIALS
        self.influx_cred_map = {}
        if influx_cred is not None:
            for host_cred_combo in influx_cred.split(','):
                match = re.search('(.*:\/\/)*(\w+):(\w+)@([A-Za-z0-9\-\.]+)(:(\d+))*', host_cred_combo.strip())
                if len(match.groups()) != 6:
                    log.warning('Invalid credential combination specified: {}. Ignoring', host_cred_combo)
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
                    self.influx_cred_map[influx_host] = (username, password)
            log.debug('Processed {} InfluxDB credentials'.format(len(self.influx_cred_map)))

    def process_profile(self, profile: esdl.GenericProfile) -> Union[pd.DataFrame, None]:
        # Process each profile
        log.debug(f'Processing profile {profile.name}')
        if isinstance(profile.eContainer(), Port):
            containing_asset = profile.eContainer().energyasset
            containing_asset_id = containing_asset.id
        else:
            containing_asset_id = profile.id
        to_si_multiplier = self.to_joules(profile)

        if isinstance(profile, ProfileReference):
            profile = profile.reference

        if isinstance(profile, esdl.InfluxDBProfile):
            log.debug("Processing InfluxDB profile {} of asset {}".format(profile.id, containing_asset_id))
            is_energy_profile = False
            is_power_profile = False
            if ESDLProfileProcessor.is_energy(profile):
                self.data_type[containing_asset_id] = "energy"
                is_energy_profile = True
                agg_op = 'MEAN'
            elif ESDLProfileProcessor.is_power(profile):
                self.data_type[containing_asset_id] = "power"
                is_power_profile = True
                agg_op = 'SUM'
            else:
                log.warning(f'{profile.id} is a non-energy and non-power profile. Ignoring...')
                # TODO - To handle non-power/energy profile
                return None

            if is_energy_profile or is_power_profile:
                profile_host = profile.host
                influx_host = '{}:{}'.format(profile_host, profile.port)
                if influx_host in self.influx_cred_map:
                    (username, password) = self.influx_cred_map[influx_host]
                else:
                    username = None
                    password = None
                ssl_setting = False
                if 'https' in profile_host:
                    profile_host = profile_host[8:]
                    ssl_setting = True
                elif 'http' in profile_host:
                    profile_host = profile_host[7:]
                if profile.port == 443:
                    ssl_setting = True
                if profile.startDate is not None:
                    profile_start_date = profile.startDate.isoformat()
                else:
                    profile_start_date = self.start_date.isoformat()
                if profile.endDate is not None:
                    end_date_suffix = " AND time <= '{}'".format(profile.endDate.isoformat())
                else:
                    end_date_suffix = " AND time <= '{}'".format(self.end_date.isoformat())
                if profile.filters is not None and profile.filters != '':
                    filter_suffix = " AND {}".format(profile.filters)
                else:
                    filter_suffix = ""
                query = 'SELECT {}("{}") FROM "{}" WHERE time >= \'{}\'{}{} GROUP BY time({})'.format(
                    agg_op,
                    profile.field,
                    profile.measurement,
                    profile_start_date,
                    end_date_suffix,
                    filter_suffix,
                    self.time_step_notation)
                query_hash = hashlib.sha256(query.encode("utf-8")).hexdigest()
                log.debug('InfluxDB query: {} on {}'.format(query, influx_host))
                if query_hash not in self.data_cache:
                    log.debug("Profile not cached. Going to query InfluxDB.")
                    client = InfluxDBClient(host=profile_host, port=profile.port, username=username,
                                            password=password, ssl=ssl_setting, verify_ssl=ssl_setting)
                    client.switch_database(profile.database)
                    data = client.query(query=query)
                    data_points = {t[0]: t[1] for t in data.raw["series"][0]["values"]}
                    df = pd.DataFrame.from_dict(data_points, orient="index")
                    df.index = pd.to_datetime(df.index)
                    self.asset_data[containing_asset_id] = df * profile.multiplier * to_si_multiplier
                    self.data_cache[query_hash] = df
                    client.close()
                else:
                    log.debug("Profile cached. Retrieving profile from cache.")
                    return self.data_cache[query_hash] * profile.multiplier * to_si_multiplier

        elif isinstance(profile, esdl.SingleValue):
            return pd.DataFrame({containing_asset_id: profile.value * to_si_multiplier}, index=self.time_range)

        elif isinstance(profile, esdl.DateTimeProfile):
            df = pd.DataFrame({containing_asset_id: np.NaN}, index=self.time_range)
            for element in profile.element:
                df[containing_asset_id][
                pd.to_datetime(element.from_):pd.to_datetime(element.to)] = element.value * to_si_multiplier
            return df

        elif isinstance(profile, esdl.TimeSeriesProfile):
            df = pd.DataFrame({containing_asset_id: profile.values},
                              index=pd.date_range(start=pd.to_datetime(profile.startDateTime),
                                                  periods=len(profile.values),
                                                  freq='{}s'.format(profile.timestep)))
            return df * to_si_multiplier

        else:
            log.warning('Unsupported profile type {} for asset {}'.format(profile.__class__, containing_asset_id))
            return None

    @staticmethod
    def is_energy(profile: esdl.GenericProfile):
        if profile.profileType is not None and profile.profileType != esdl.ProfileTypeEnum.UNDEFINED:
            if 4 <= profile.profileType.value <= 13:
                return True
            else:
                return False
        if profile.profileQuantityAndUnit is not None:
            if isinstance(profile.profileQuantityAndUnit, esdl.QuantityAndUnitReference):
                p = profile.profileQuantityAndUnit.reference
            elif isinstance(profile.profileQuantityAndUnit, esdl.QuantityAndUnitType):
                p = profile.profileQuantityAndUnit
            else:
                return False

            if p is not None:
                if p.physicalQuantity == esdl.PhysicalQuantityEnum.ENERGY:
                    return True
                else:
                    return False
        return False

    @staticmethod
    def is_power(profile: esdl.GenericProfile):
        if profile.profileType is not None and profile.profileType != esdl.ProfileTypeEnum.UNDEFINED:
            if 16 <= profile.profileType.value <= 20:
                return True
            else:
                return False
        if profile.profileQuantityAndUnit is not None:
            if isinstance(profile.profileQuantityAndUnit, esdl.QuantityAndUnitReference):
                p = profile.profileQuantityAndUnit.reference
            elif isinstance(profile.profileQuantityAndUnit, esdl.QuantityAndUnitType):
                p = profile.profileQuantityAndUnit
            else:
                return False

            if p is not None:
                if p.physicalQuantity == esdl.PhysicalQuantityEnum.POWER:
                    return True
                else:
                    return False

        return False

    def to_joules(self, profile: esdl.GenericProfile):
        if profile.profileType is not None and profile.profileType != esdl.ProfileTypeEnum.UNDEFINED:
            if profile.profileType.name not in self.factor:
                log.error("Unsupported profile type : {}".format(profile.profileType))
                return 0
            return self.factor[profile.profileType.name]

        p = None
        if isinstance(profile.profileQuantityAndUnit, esdl.QuantityAndUnitReference):
            p = profile.profileQuantityAndUnit.reference
        elif isinstance(profile.profileQuantityAndUnit, esdl.QuantityAndUnitType):
            p = profile.profileQuantityAndUnit

        if p is None:
            raise ValueError("No Quantity and Unit defined for profile {}".format(profile))
        else:
            if p.unit == esdl.UnitEnum.JOULE:
                phy_quantity = "ENERGY_IN_"
                suffix = "J"
            elif p.unit == esdl.UnitEnum.WATTHOUR:
                phy_quantity = "ENERGY_IN_"
                suffix = "WH"
            elif p.unit == esdl.UnitEnum.WATT:
                phy_quantity = "POWER_IN_"
                suffix = "W"
            else:
                log.warning("Unsupported unit : {}".format(p.unit))
                return 0

            prefix = self.mult_suffix[p.multiplier.name]
            if prefix == "-":
                log.warning("Unsupported multiplier : {}".format(p.multiplier))
                return 0

            return self.factor["{}{}{}".format(phy_quantity, prefix, suffix)]
