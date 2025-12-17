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

from datetime import datetime

from tno.shared.log import get_logger

logger = get_logger(__name__)


class BatteryNode:
    def __init__(self, asset_info, carriers_info, simulation_info, charge_time_windows, discharge_time_windows):
        self.asset_info = asset_info
        self.carriers_info = carriers_info
        self.simulation_info = simulation_info

        self.delta = 1e-12

        self.state_of_charge_in_joules = list()
        self.bid_curves = dict()
        self.allocations_energy = dict()
        self.min_price = None
        self.max_price = None
        self.duration = None

        self.charge_time_windows = charge_time_windows
        self.discharge_time_windows = discharge_time_windows

        attrs_used = ["capacity", "fillLevel", "marginalChargeCosts", "marginalDischargeCosts"]
        for attr in attrs_used:
            if attr not in self.asset_info:
                raise Exception(f"{attr} not defined on battery asset")

        self.state_of_charge_in_joules.append(self.asset_info["capacity"] * self.asset_info["fillLevel"])

    def store_bid_curve(self, carried_id, bid_curve):
        if carried_id not in self.bid_curves:
            self.bid_curves[carried_id] = list()

        self.bid_curves[carried_id].append(bid_curve)

    def store_allocation_energy(self, carried_id, allocation):
        if carried_id not in self.allocations_energy:
            self.allocations_energy[carried_id] = list()

        self.allocations_energy[carried_id].append(allocation)

    def get_allocation_energy(self, carried_id, step_nr):
        if carried_id in self.allocations_energy:
            if step_nr >= len(self.allocations_energy[carried_id]):
                print(
                    f"Serious error: step_nr {step_nr}, len(self.allocations_energy[carried_id]) {len(self.allocations_energy[carried_id])}")
            return self.allocations_energy[carried_id][step_nr]
        return None

    def get_marginal_charge_costs(self, step_nr):
        if self.asset_info['marginalChargeCosts']['type'] == 'SingleValue':
            return self.asset_info['marginalChargeCosts']['value']
        else:
            raise Exception('Other marginal cost types than SingleValue have not been implemented yet!')

    def get_marginal_discharge_costs(self, step_nr):
        if self.asset_info['marginalDischargeCosts']['type'] == 'SingleValue':
            return self.asset_info['marginalDischargeCosts']['value']
        else:
            raise Exception('Other marginal cost types than SingleValue have not been implemented yet!')

    def create_bid_curve(self, step_nr, timestamp, duration, minprice, maxprice, carrier_id):
        self.min_price = minprice
        self.max_price = maxprice
        self.duration = duration

        current_soc = self.state_of_charge_in_joules[step_nr]
        charge_fill_fraction = current_soc / self.asset_info['capacity']

        hour_of_day = datetime.fromtimestamp(timestamp).hour

        allow_charge = True
        if self.charge_time_windows and charge_fill_fraction > float(self.charge_time_windows[
                                                                         'always_charge_below_fill_fraction']):
            allow_charge = False
            for window in self.charge_time_windows['windows']:
                if not allow_charge:
                    allow_charge = int(window["start_hour"]) <= hour_of_day < int(window["end_hour"])

        allow_discharge = True
        if self.discharge_time_windows and charge_fill_fraction < float(self.discharge_time_windows[
                                                                            'always_discharge_above_fill_fraction']):
            allow_discharge = False
            for window in self.discharge_time_windows['windows']:
                if not allow_discharge:
                    allow_discharge = int(window["start_hour"]) <= hour_of_day < int(window["end_hour"])

        logger.debug(f"hour_of_day '{hour_of_day}': allow_charge {allow_charge} allow_discharge {allow_discharge}")

        if allow_charge:
            max_charge_this_timestep = min(
                self.asset_info['maxChargeRate'] * duration,  # max joules that can be added in this timestep
                self.asset_info['capacity'] - current_soc  # "Space" left in Joules
            )
        else:
            max_charge_this_timestep = 0

        if allow_discharge:
            max_discharge_this_timestep = min(
                self.asset_info['maxDischargeRate'] * duration,  # max Joules that can be used in this timestep
                current_soc  # Charge available in Joules
            )
        else:
            max_discharge_this_timestep = 0

        mcc = self.get_marginal_charge_costs(step_nr)
        mdc = self.get_marginal_discharge_costs(step_nr)
        if mcc > mdc:
            raise Exception(f"step_nr {step_nr}: Marginal charge costs ({mcc}) > Marginal discharge costs ({mdc})")

        # e is the amount of energy in Joules that can be consumed in one timestep
        # e = power * duration
        # logger.debug(f"energy={e}, power={power}")

        # Bidcurves must be strictly decreasing
        mdc_energy = -self.delta / 2 if self.delta / 2 < max_discharge_this_timestep else -max_discharge_this_timestep / 2
        mcc_energy = self.delta / 2 if self.delta / 2 < max_charge_this_timestep else max_charge_this_timestep / 2
        bid_curve = [[minprice, max_charge_this_timestep], [mcc, mcc_energy], [mdc, mdc_energy], [maxprice, -max_discharge_this_timestep]]
        if max_discharge_this_timestep == 0:
            bid_curve.pop(2)    # remove the [mdc, ...] element if there is no discharging allowed at this timestep
        if max_charge_this_timestep == 0:
            bid_curve.pop(1)    # remove the [mcc, ...] element if there is no charging allowed at this timestep
        if len(bid_curve) == 2:
            bid_curve[1][1] = -self.delta   # is both are 0, change the latter to -delta to keep strictly decreasing

        # Bidcurve is needed when allocation is received. For now, save all created bidcurves
        self.store_bid_curve(carrier_id, bid_curve)
        return bid_curve

    def get_carrier_cost(self, carrier_type, step_nr):
        for carr in self.carriers_info:
            if carr['carrier_type'] == carrier_type + 'Commodity':
                if isinstance(carr['carrier_cost'], list):
                    return carr['carrier_cost'][step_nr]
                else:
                    return carr['carrier_cost']
        return 0

    def process_allocation(self, step_nr, price, carrier_id):
        logger.debug(f"process_allocation - step_nr: {step_nr}, price: {price} for carrier: "
                     f"{self.carriers_info[carrier_id]['carrier_type']}")
        current_bid_curve = self.bid_curves[carrier_id][step_nr]
        logger.debug(current_bid_curve)
        allocation = None
        if price < self.min_price + 1e-12:
            allocation = current_bid_curve[0][1]
        else:
            for i in range(len(current_bid_curve) - 1):
                if current_bid_curve[i + 1][0] >= price:
                    allocation = current_bid_curve[i][1] \
                                 + (price - current_bid_curve[i][0]) \
                                 * (current_bid_curve[i + 1][1] - current_bid_curve[i][1]) \
                                 / (current_bid_curve[i + 1][0] - current_bid_curve[i][0])
                    break
        if allocation is None:
            raise Exception("No allocation found - serious error!")

        # Allocation > 0: charge, so SoC increases
        # Allocation < 0: discharge, so SoC decreases
        new_soc = self.state_of_charge_in_joules[step_nr] + allocation
        if new_soc < 0:
            new_soc = 0
        self.state_of_charge_in_joules.append(new_soc)

        logger.debug(
            f"Allocation/duration ({self.carriers_info[carrier_id]['carrier_type']}): {allocation / self.duration}")

        self.store_allocation_energy(carrier_id, allocation)
        return allocation

    def write_results(self, influxdb_client, simulation_run_id, start_timestamp):
        points = list()
        first_timestamp = None

        t_rms = 0.0
        for i in range(self.simulation_info['number_of_steps'] - 1):
            try:
                time = datetime.utcfromtimestamp(start_timestamp + i * self.duration).strftime("%Y-%m-%dT%H:%M:%SZ")
                if first_timestamp is None:
                    first_timestamp = time

                fields = {
                    "State_of_charge_in_joules": float(self.state_of_charge_in_joules[i]),
                    "State_of_charge_in_fraction": float(
                        self.state_of_charge_in_joules[i] / self.asset_info["capacity"]),
                }

                for carr in self.carriers_info:
                    carr_type = self.carriers_info[carr]["carrier_type"].replace("Commodity", "")
                    fields[carr_type + "_allocation_energy"] = float(self.get_allocation_energy(carr, i))
                    fields[carr_type + "_bid_curve_energy_start"] = float(self.bid_curves[carr][i][0][1])
                    fields[carr_type + "_bid_curve_energy_end"] = float(self.bid_curves[carr][i][-1][1])
                    if "carrier_cost" in self.carriers_info[carr]:
                        fields[carr_type + "_cost"] = float(self.carriers_info[carr]["carrier_cost"][i])

                item = {
                    "measurement": f"battery-{self.asset_info['name']}",
                    "tags": {"simulationRun": simulation_run_id},
                    "time": time,
                    "fields": fields,
                }
            except Exception as e:
                logger.debug(f"Exception: {e.message} {e.args}")
                continue
            points.append(item)

        logger.info(
            f"InfluxDB writing {len(points)} points to measurement 'battery-{self.asset_info['name']}' with tag simulationRun {simulation_run_id}")
        influxdb_client.write(points)
