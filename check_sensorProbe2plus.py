#!/usr/bin/env python
# ------------------------------------------------------------------------------
# check_sensorProbe2plus.py - A check plugin for AKCP SensorProbe2+.
# Copyright (C) 2017  NETWAYS GmbH, www.netways.de
# Authors: Noah Hilverling <noah.hilverling@netways.de>
#          Jennifer Mourek <jennifer.mourek@netways.de>
#
# Version: 1.0
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

import argparse
import sys
from pysnmp.entity.rfc3413.oneliner import cmdgen
from enum import Enum, IntEnum


# Translate the OID indexes to keywords
class Types(IntEnum):
    CATEGORY = 0
    NAME = 2
    UNIT = 5
    STATE = 6
    LOW_CRITICAL = 9
    LOW_WARNING = 10
    HIGH_WARNING = 11
    HIGH_CRITICAL = 12
    VALUE = 20


# Translate the Nagios state IDs to keywords
class NagiosState(Enum):
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
    27: "Door"
}


# Convert a state from AKCP format to Nagios
def convert_state_to_nagios(state_to_convert):
    state_to_convert = int(state_to_convert)
    if state_to_convert == 1:
        return NagiosState.UNKNOWN
    elif state_to_convert == 2:
        return NagiosState.OK
    elif state_to_convert == 3 or state_to_convert == 5:
        return NagiosState.WARNING
    elif state_to_convert == 4 or state_to_convert == 6:
        return NagiosState.CRITICAL
    else:
        print("State %s is out of range. That should not happen." % state_to_convert)
        return NagiosState.UNKNOWN


# Display a one line status message with:
#   - most important Nagios state and short message
#   - number and name of the sensors in any state but OK
#   - thresholds of the sensors
def print_status_message(sensor_states, perf_data):
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
        result_message = "CRITICAL sensorProbe2plus: Sensor reports state CRITICAL for %d sensor%s (%s) " \
                "and state WARNING for %d sensor%s (%s)" % (
                    len(sensor_states["CRITICAL"]),
                    "s" if len(sensor_states["CRITICAL"]) > 1 else "",
                    critical_name_string,
                    len(sensor_states["WARNING"]),
                    "s" if len(sensor_states["WARNING"]) > 1 else "",
                    warning_name_string
                )
    elif len(sensor_states["WARNING"]) > 0:
        result_message = "WARNING sensorProbe2plus: Sensor reports state WARNING for %d sensor%s (%s)" % (
            len(sensor_states["WARNING"]), "s" if len(sensor_states["WARNING"]) > 1 else "", warning_name_string)
    elif len(sensor_states["CRITICAL"]) > 0:
        result_message = "CRITICAL sensorProbe2plus: Sensor reports state CRITICAL for %d sensor%s (%s)" % (
            len(sensor_states["CRITICAL"]), "s" if len(sensor_states["CRITICAL"]) > 1 else "", critical_name_string)
    else:
        result_message = "OK sensorProbe2plus: Sensor reports that everything is fine"

    # Add the performance data to the end of the first output line
    result_message += "|"
    for singlePerfData in perf_data:
        result_message += singlePerfData + " "

    # Print summary and performance data
    print(result_message)


# Version number
version = 1.0

# Initialise variables
verbose = 0
hostname = ""
community = ""
port = 0

# Arguments for the CLI command
parser = argparse.ArgumentParser(description='Check plugin for AKCP SensorProbe2+')
parser.add_argument("-V", "--version", action="store_true")
parser.add_argument("-v", "--verbose", action="count", default=0, help="increase output verbosity (-v or -vv)")
parser.add_argument("-p", "--port", help="port of the sensors to check (shows all if not set)", type=int, default=0)
required = parser.add_argument_group('required arguments')
required.add_argument("-H", "--hostname", help="host of the sensor probe", required=True)
required.add_argument("-C", "--community", help="read community of the sensor probe", required=True)

args = parser.parse_args()

# Print version if version argument is given
if args.version:
    print("AKCP SensorProbe2+ Version %s" % version)
    sys.exit()
else:
    # Assert arguments to their variables
    verbose = args.verbose if args.verbose <= 2 else 2
    hostname = args.hostname
    community = args.community
    port = args.port

# The state with the highest importance (CRITICAL -> WARNING -> OK)
mostImportantState = NagiosState.OK

# Array of messages to print after first line if verbose
stateMessages = []

# Performance data for each sensor as string
perfData = []

# Root for sensor dictionary tree
sensorPorts = {}

# Root for sensor OIDs
sensorsOID = (1, 3, 6, 1, 4, 1, 3854, 3, 5)

generator = cmdgen.CommandGenerator()
communityData = cmdgen.CommunityData(community)
transport = cmdgen.UdpTransportTarget((hostname, 161))
command = getattr(generator, 'nextCmd')

errorIndication, errorStatus, errorIndex, result = command(communityData, transport, sensorsOID)

# Check if an exception occurred
if errorIndication:
    print("%s sensorProbe2plus: %s" % (NagiosState.UNKNOWN.name, errorIndication))
    mostImportantState = NagiosState.UNKNOWN
elif errorStatus:
    print(('%s sensorProbe2plus: %s at %s' % (NagiosState.CRITICAL.name,
                                             errorStatus.prettyPrint(),
                                             errorIndex and result[int(errorIndex)-1] or '?')))
    mostImportantState = NagiosState.CRITICAL
else:
    # Sort results
    for data in result:
        oid = data[0][0]
        value = data[0][1]

        # Filter relevant OIDs
        valueIndex = int(oid[11])
        try:
            Types(valueIndex)
        except ValueError as err:
            continue

        # Get sensor category
        category = int(oid[9])
        if category == 1 or category > 27:
            continue

        # Filter ports if port is given in arguments
        sensorPort = int(oid[15])
        if args.port != 0 and args.port - 1 != sensorPort:
            continue

        # Numeric index of sensor
        sensorIndex = int(oid[16])

        # Add needed dictionaries if not yet existing
        if sensorPort not in sensorPorts:
            sensorPorts[sensorPort] = {}
        if sensorIndex not in sensorPorts[sensorPort]:
            sensorPorts[sensorPort][sensorIndex] = {}

        # Store data in dictionary tree
        sensorPorts[sensorPort][sensorIndex][valueIndex] = value
        sensorPorts[sensorPort][sensorIndex][Types.CATEGORY] = categories[category]

    # Check if there is no sensor on the given port
    if len(sensorPorts) < 1:
        print("%s sensorProbe2plus: There is no sensor on the given port" % NagiosState.UNKNOWN.name)
        sys.exit(NagiosState.UNKNOWN.value)

    # Sensor names sorted by state
    namesByState = {"OK": [], "WARNING": [], "CRITICAL": [], "UNKNOWN": []}

    # Iterate through sensors
    for sensorPort, sensorIndexes in sensorPorts.items():
        for sensorIndex, valueIndexes in sensorIndexes.items():
            # Convert state to Nagios states
            state = convert_state_to_nagios(valueIndexes[Types.STATE])

            # Redetermines most important state
            if hasattr(state, 'value') and state.value > mostImportantState.value:
                mostImportantState = state
            else:
                mostImportantState = NagiosState.UNKNOWN

            # Sort sensor name by state
            namesByState[state.name].append(valueIndexes[Types.NAME])

            # Check if sensor has no value
            if Types.VALUE not in valueIndexes:
                # Value replacement for sensors without value
                value = 0 if state == NagiosState.OK else 1

                # Status message for sensor
                stateMessages.append(
                    "%s %s" % (state.name, valueIndexes[Types.NAME]))

                # Add performance data to performance data array
                perfData.append("'%s'=%s;" % (valueIndexes[Types.NAME], value))
            else:
                # Convert temperatures into right format
                if valueIndexes[Types.UNIT] == "C":
                    valueIndexes[Types.VALUE] = float(valueIndexes[Types.VALUE]) / 10
                    valueIndexes[Types.LOW_CRITICAL] = float(valueIndexes[Types.LOW_CRITICAL]) / 10
                    valueIndexes[Types.LOW_WARNING] = float(valueIndexes[Types.LOW_WARNING]) / 10
                    valueIndexes[Types.HIGH_WARNING] = float(valueIndexes[Types.HIGH_WARNING]) / 10
                    valueIndexes[Types.HIGH_CRITICAL] = float(valueIndexes[Types.HIGH_CRITICAL]) / 10

                # Status message for sensor
                stateMessage = '%s %s sensor "%s": %s%s' % (state.name,
                                                            valueIndexes[Types.CATEGORY],
                                                            valueIndexes[Types.NAME],
                                                            valueIndexes[Types.VALUE],
                                                            valueIndexes[Types.UNIT])

                # Add thresholds to verbose sensor messages
                if verbose > 1:
                    stateMessage += " (%s:%s/%s:%s)" % (valueIndexes[Types.LOW_WARNING],
                                                        valueIndexes[Types.HIGH_WARNING],
                                                        valueIndexes[Types.LOW_CRITICAL],
                                                        valueIndexes[Types.HIGH_CRITICAL])

                stateMessages.append(stateMessage)

                # Add performance data to performance data array
                perfData.append("'%s'=%s%s;%s:%s;%s:%s" % (valueIndexes[Types.NAME],
                                                           valueIndexes[Types.VALUE],
                                                           valueIndexes[Types.UNIT],
                                                           valueIndexes[Types.LOW_WARNING],
                                                           valueIndexes[Types.HIGH_WARNING],
                                                           valueIndexes[Types.LOW_CRITICAL],
                                                           valueIndexes[Types.HIGH_CRITICAL]))

    # Print first line of output
    print_status_message(namesByState, perfData)

    # Add additional information for each sensor to the output if verbose
    if verbose > 0:
        for message in stateMessages:
            print(message)

    # Exit with most important state
    sys.exit(mostImportantState.value)
