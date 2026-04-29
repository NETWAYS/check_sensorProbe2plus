#!/usr/bin/env python
# ------------------------------------------------------------------------------
# check_sensorProbe2plus.py - A check plugin for AKCP SensorProbe2+.
# Copyright (C) 2017  NETWAYS GmbH, www.netways.de
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
# ------------------------------------------------------------------------------

"""
check_sensorProbe2plus.py is a Check Plugin for Nagios similar monitoring systems
like Icinga or Nameon.
It retrieves data from a AKCP SensorProbe2+ devices and alerts on problematic
conditions
"""

import argparse
import asyncio as other_asyncio_name
import sys
import typing
from enum import Enum, IntEnum

import pysnmp
from pysnmp.hlapi.v3arch.asyncio import SnmpEngine as pySnmp_engine
from pysnmp.hlapi.v3arch.asyncio import next_cmd as pySnmp_next_cmd

# Version number
VERSION = 1.1

# Root for sensor OIDs
SENSORS_OID = (1, 3, 6, 1, 4, 1, 3854, 3, 5)

# pylint: disable=consider-using-f-string


class Types(IntEnum):
    """Translate the OID indexes to keywords"""

    CATEGORY = 0
    NAME = 2
    UNIT = 5
    STATE = 6
    LOW_CRITICAL = 9
    LOW_WARNING = 10
    HIGH_WARNING = 11
    HIGH_CRITICAL = 12
    VALUE = 20


class NagiosState(Enum):
    """Translate the Nagios state IDs to keywords"""

    OK = 0
    WARNING = 1
    CRITICAL = 2
    UNKNOWN = 3


categories = {
    2: "Temperature",
    3: "Humidity",
    4: "Dry Contact",
    5: "Current 4 to 20mA",
    6: "DC voltage",
    7: "Airflow",
    8: "Motion",
    9: "Water",
    10: "Security",
    11: "Siren",
    12: "Relay",
    13: "AC voltage",
    14: "Smoke",
    21: "Water rope",
    22: "Power",
    24: "Fuel",
    26: "Tank sender",
    27: "Door",
}


def convert_state_to_nagios(state_to_convert):
    """
    Convert a state from AKCP format to Nagios
    """
    state_to_convert = int(state_to_convert)
    if state_to_convert == 1:
        return NagiosState.UNKNOWN
    if state_to_convert == 2:
        return NagiosState.OK
    if state_to_convert in (3, 5):
        return NagiosState.WARNING
    if state_to_convert in (4, 6):
        return NagiosState.CRITICAL

    print("State %s is out of range. That should not happen." % state_to_convert)
    return NagiosState.UNKNOWN


def print_status_message(sensor_states, perf_data):
    """
    Display a one line status message with:
        - most important Nagios state and short message
        - number and name of the sensors in any state but OK
        - thresholds of the sensors
    """
    warning_name_string = ""
    for name in sensor_states["WARNING"]:
        if warning_name_string:
            warning_name_string += ", "
        warning_name_string += name

    critical_name_string = ""
    for name in sensor_states["CRITICAL"]:
        if critical_name_string:
            critical_name_string += ", "
        critical_name_string += name

    result_message = ""
    if len(sensor_states["WARNING"]) > 0 and len(sensor_states["CRITICAL"]) > 0:
        result_message = (
            "CRITICAL sensorProbe2plus: Sensor reports state CRITICAL for {} sensor{} ({}) "
            "and state WARNING for {} sensor{} ({})".format(
                len(sensor_states["CRITICAL"]),
                "s" if len(sensor_states["CRITICAL"]) > 1 else "",
                critical_name_string,
                len(sensor_states["WARNING"]),
                "s" if len(sensor_states["WARNING"]) > 1 else "",
                warning_name_string,
            )
        )
    elif len(sensor_states["WARNING"]) > 0:
        result_message = (
            "WARNING sensorProbe2plus: Sensor reports state WARNING for %d sensor%s (%s)"
            % (
                len(sensor_states["WARNING"]),
                "s" if len(sensor_states["WARNING"]) > 1 else "",
                warning_name_string,
            )
        )
    elif len(sensor_states["CRITICAL"]) > 0:
        result_message = (
            "CRITICAL sensorProbe2plus: Sensor reports state CRITICAL for %d sensor%s (%s)"
            % (
                len(sensor_states["CRITICAL"]),
                "s" if len(sensor_states["CRITICAL"]) > 1 else "",
                critical_name_string,
            )
        )
    else:
        result_message = "OK sensorProbe2plus: Sensor reports that everything is fine"

    # Add the performance data to the end of the first output line
    result_message += "|"
    for single_perfdata in perf_data:
        result_message += single_perfdata + " "

    # Print summary and performance data
    print(result_message)


def parse_args() -> tuple[int, str, str, int]:
    """
    Parse CLI arguments
    """
    parser = argparse.ArgumentParser(description="Check plugin for AKCP SensorProbe2+")
    parser.add_argument("-V", "--version", action="store_true")
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="increase output verbosity (-v or -vv)",
    )
    parser.add_argument(
        "-p",
        "--port",
        help="port of the sensors to check (shows all if not set)",
        type=int,
        default=0,
    )
    required = parser.add_argument_group("required arguments")
    required.add_argument(
        "-H", "--hostname", help="host of the sensor probe", required=True
    )
    required.add_argument(
        "-C", "--community", help="read community of the sensor probe", required=True
    )

    args = parser.parse_args()

    # Print version if version argument is given
    if args.version:
        print("check_sensorProbe2plus version %s" % VERSION)
        sys.exit()
    else:
        # Assert arguments to their variables
        verbose = args.verbose if args.verbose <= 2 else 2
        hostname = args.hostname
        community = args.community
        port = args.port
        return (verbose, hostname, community, port)


def execute(hostname, sensor_port_input, community, verbose) -> None:
    """
    Execute the actual test
    """
    # Array of messages to print after first line if verbose
    state_messages = []

    # Performance data for each sensor as string
    perfdata = []

    # Root for sensor dictionary tree
    sensor_ports: dict[int, typing.Any] = {}

    error_indication, error_status, error_index, result = other_asyncio_name.run(
        snmp_query(hostname, 161, SENSORS_OID, community)
    )

    # The state with the highest importance (CRITICAL -> WARNING -> OK)
    most_important_state = NagiosState.OK

    if error_indication:
        print("%s sensorProbe2plus: %s" % (NagiosState.UNKNOWN.name, error_indication))
        most_important_state = NagiosState.UNKNOWN
    elif error_status:
        print(
            (
                "%s sensorProbe2plus: %s at %s"
                % (
                    NagiosState.CRITICAL.name,
                    error_status.prettyPrint(),
                    error_index and result[int(error_index) - 1] or "?",
                )
            )
        )
        most_important_state = NagiosState.CRITICAL
    else:
        # Sort results
        for data in result:
            oid = data[0][0]
            value = data[0][1]

            # Filter relevant OIDs
            value_index = int(oid[11])
            try:
                Types(value_index)
            except ValueError:
                continue

            # Get sensor category
            category = int(oid[9])
            if category == 1 or category > 27:
                continue

            # Filter ports if port is given in arguments
            sensor_port = int(oid[15])
            if sensor_port_input != 0 and sensor_port_input - 1 != sensor_port:
                continue

            # Numeric index of sensor
            sensor_index = int(oid[16])

            # Add needed dictionaries if not yet existing
            if sensor_port not in sensor_ports:
                sensor_ports[sensor_port] = {}
            if sensor_index not in sensor_ports[sensor_port]:
                sensor_ports[sensor_port][sensor_index] = {}

            # Store data in dictionary tree
            sensor_ports[sensor_port][sensor_index][value_index] = value
            sensor_ports[sensor_port][sensor_index][Types.CATEGORY] = categories[
                category
            ]

        # Check if there is no sensor on the given port
        if len(sensor_ports) < 1:
            print(
                "%s sensorProbe2plus: There is no sensor on the given port"
                % NagiosState.UNKNOWN.name
            )
            sys.exit(NagiosState.UNKNOWN.value)

        # Sensor names sorted by state
        names_by_state: dict[str, list] = {
            "OK": [],
            "WARNING": [],
            "CRITICAL": [],
            "UNKNOWN": [],
        }

        # Iterate through sensors
        for sensor_port, sensor_indexes in sensor_ports.items():
            for sensor_index, value_indexes in sensor_indexes.items():
                # Convert state to Nagios states
                state = convert_state_to_nagios(value_indexes[Types.STATE])

                # Redetermines most important state
                if hasattr(state, "value") and state.value > most_important_state.value:
                    most_important_state = state
                else:
                    most_important_state = NagiosState.UNKNOWN

                # Sort sensor name by state
                names_by_state[state.name].append(value_indexes[Types.NAME])

                # Check if sensor has no value
                if Types.VALUE not in value_indexes:
                    # Value replacement for sensors without value
                    value = 0 if state == NagiosState.OK else 1

                    # Status message for sensor
                    state_messages.append(
                        "%s %s" % (state.name, value_indexes[Types.NAME])
                    )

                    # Add performance data to performance data array
                    perfdata.append("'%s'=%s;" % (value_indexes[Types.NAME], value))
                else:
                    # Convert temperatures into right format
                    if value_indexes[Types.UNIT] == "C":
                        value_indexes[Types.VALUE] = (
                            float(value_indexes[Types.VALUE]) / 10
                        )
                        value_indexes[Types.LOW_CRITICAL] = (
                            float(value_indexes[Types.LOW_CRITICAL]) / 10
                        )
                        value_indexes[Types.LOW_WARNING] = (
                            float(value_indexes[Types.LOW_WARNING]) / 10
                        )
                        value_indexes[Types.HIGH_WARNING] = (
                            float(value_indexes[Types.HIGH_WARNING]) / 10
                        )
                        value_indexes[Types.HIGH_CRITICAL] = (
                            float(value_indexes[Types.HIGH_CRITICAL]) / 10
                        )

                    # Status message for sensor
                    state_message = '%s %s sensor "%s": %s%s' % (
                        state.name,
                        value_indexes[Types.CATEGORY],
                        value_indexes[Types.NAME],
                        value_indexes[Types.VALUE],
                        value_indexes[Types.UNIT],
                    )

                    # Add thresholds to verbose sensor messages
                    if verbose > 1:
                        state_message += " (%s:%s/%s:%s)" % (
                            value_indexes[Types.LOW_WARNING],
                            value_indexes[Types.HIGH_WARNING],
                            value_indexes[Types.LOW_CRITICAL],
                            value_indexes[Types.HIGH_CRITICAL],
                        )

                    state_messages.append(state_message)

                    # Add performance data to performance data array
                    perfdata.append(
                        "'%s'=%s%s;%s:%s;%s:%s"
                        % (
                            value_indexes[Types.NAME],
                            value_indexes[Types.VALUE],
                            value_indexes[Types.UNIT],
                            value_indexes[Types.LOW_WARNING],
                            value_indexes[Types.HIGH_WARNING],
                            value_indexes[Types.LOW_CRITICAL],
                            value_indexes[Types.HIGH_CRITICAL],
                        )
                    )

        # Print first line of output
        print_status_message(names_by_state, perfdata)

        # Add additional information for each sensor to the output if verbose
        if verbose > 0:
            for message in state_messages:
                print(message)

        # Exit with most important state
        sys.exit(most_important_state.value)


async def snmp_query(hostname, port, oid, community):
    """
    snmp_query executes the actual query
    """
    snmp_engine = pySnmp_engine()

    snmp_object = pysnmp.smi.rfc1902.ObjectType(pysnmp.smi.rfc1902.ObjectIdentity(oid))
    error_indication, error_status, error_index, result = await pySnmp_next_cmd(
        snmp_engine,
        pysnmp.hlapi.v3arch.asyncio.auth.CommunityData(community),
        await pysnmp.hlapi.v3arch.asyncio.UdpTransportTarget.create((hostname, port)),
        pysnmp.hlapi.v3arch.asyncio.ContextData(),
        snmp_object,
    )

    return (error_indication, error_status, error_index, result)


if __name__ == "__main__":
    verbose, hostname, community, sensor_port = parse_args()
    execute(hostname, sensor_port, community, verbose)
