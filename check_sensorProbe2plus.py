# ------------------------------------------------------------------------------
# check_sensorProbe2plus.py - A check plugin for AKCP SensorProbe2+.
# Copyright (C) 2017  NETWAYS GmbH, www.netways.de
# Authors: Noah Hilverling <noah.hilverling@netways.de>, Jennifer Mourek <jennifer.mourek@netways.de>
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

from pysnmp.entity.rfc3413.oneliner import cmdgen
from enum import Enum, IntEnum
import argparse


class Types(IntEnum):
    NAME = 2
    UNIT = 5
    STATE = 6
    LOW_CRITICAL = 9
    LOW_WARNING = 10
    HIGH_WARNING = 11
    HIGH_CRITICAL = 12
    VALUE = 20


class NagiosState(Enum):
    OK = 0
    WARNING = 1
    CRITICAL = 2
    UNKNOWN = 3


def convert_state_to_nagios(state_to_convert):
    state_to_convert = int(state_to_convert)
    if state_to_convert == 2:
        return NagiosState.OK
    elif state_to_convert == 3 or state_to_convert == 5:
        return NagiosState.WARNING
    elif state_to_convert == 4 or state_to_convert == 6:
        return NagiosState.CRITICAL


def print_status_message(sensor_states, perf_data):
    warning_name_string = ""
    for name in sensor_states["WARNING"]:
        warning_name_string += ", " if not warning_name_string == "" else "" + name

    critical_name_string = ""
    for name in sensor_states["CRITICAL"]:
        critical_name_string += ", " if not critical_name_string == "" else "" + name

    result_message = ""
    if len(perf_data) < 1:
        print "%s sensorProbe2plus: There is no sensor on the given port" % NagiosState.UNKNOWN.name
        exit(NagiosState.UNKNOWN.value)
    elif len(sensor_states["WARNING"]) > 0 and len(sensor_states["CRITICAL"]) > 0:
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

    result_message += "|"
    for singlePerfData in perf_data:
        result_message += singlePerfData + " "

    print result_message


version = 1.0

verbose = 0
hostname = ""
community = ""
port = 0

parser = argparse.ArgumentParser(description='Check plugin for AKCP SensorProbe2+')
parser.add_argument("-V", "--version", action="store_true")
parser.add_argument("-v", "--verbose", action="count", default=0, help="increase output verbosity (-v or -vv)")
parser.add_argument("-p", "--port", help="port of the sensors to check (shows all if not set)", type=int, default=0)
required = parser.add_argument_group('required arguments')
required.add_argument("-H", "--hostname", help="host of the sensor probe", required=True)
required.add_argument("-C", "--community", help="read community of the sensor probe", required=True)

args = parser.parse_args()
if args.version:
    print "AKCP SensorProbe2+ Version %s" % version
    exit()
else:
    verbose = args.verbose if args.verbose <= 2 else 2
    hostname = args.hostname
    community = args.community
    port = args.port

sensorsOID = (1, 3, 6, 1, 4, 1, 3854, 3, 5)

generator = cmdgen.CommandGenerator()
communityData = cmdgen.CommunityData(community)
transport = cmdgen.UdpTransportTarget((hostname, 161))
command = getattr(generator, 'nextCmd')

errorIndication, errorStatus, errorIndex, result = command(communityData, transport, sensorsOID)

mostImportantState = NagiosState.OK
stateMessages = []
perfData = []
sensorPorts = {}

if errorIndication:
    print "%s sensorProbe2plus: %s" % (NagiosState.UNKNOWN.name, errorIndication)
    mostImportantState = NagiosState.UNKNOWN
elif errorStatus:
    print('%s sensorProbe2plus: %s at %s' % (
        NagiosState.CRITICAL.name,
        errorStatus.prettyPrint(), errorIndex and result[int(errorIndex)-1] or '?')
    )
    mostImportantState = NagiosState.CRITICAL
else:
    for data in result:
        oid = data[0][0]
        value = data[0][1]

        valueIndex = int(oid[11])

        try:
            Types(valueIndex)
        except ValueError as err:
            continue

        category = int(oid[9])
        if category == 1 or category > 20:
            continue

        sensorPort = int(oid[15])
        if not args.port == 0 and not args.port - 1 == sensorPort:
            continue

        sensorIndex = int(oid[16])

        if sensorPort not in sensorPorts:
            sensorPorts[sensorPort] = {}

        if sensorIndex not in sensorPorts[sensorPort]:
            sensorPorts[sensorPort][sensorIndex] = {}

        sensorPorts[sensorPort][sensorIndex][valueIndex] = value

    states = {"OK": [], "WARNING": [], "CRITICAL": []}
    for sensorPort, sensorIndexes in sensorPorts.iteritems():
        for sensorIndex, valueIndexes in sensorIndexes.iteritems():
            state = convert_state_to_nagios(valueIndexes[Types.STATE])
            if state.value > mostImportantState.value:
                mostImportantState = state

            states[state.name].append(valueIndexes[Types.NAME])

            if Types.VALUE not in valueIndexes:
                value = 0 if state == NagiosState.OK else 1
                stateMessages.append(
                    "%s %s" % (state.name, valueIndexes[Types.NAME]))
                perfData.append("'%s'=%s;" % (valueIndexes[Types.NAME], value))
                continue

            if valueIndexes[Types.UNIT] == "C":
                valueIndexes[Types.VALUE] = float(valueIndexes[Types.VALUE]) / 10
                valueIndexes[Types.LOW_CRITICAL] = float(valueIndexes[Types.LOW_CRITICAL]) / 10
                valueIndexes[Types.LOW_WARNING] = float(valueIndexes[Types.LOW_WARNING]) / 10
                valueIndexes[Types.HIGH_WARNING] = float(valueIndexes[Types.HIGH_WARNING]) / 10
                valueIndexes[Types.HIGH_CRITICAL] = float(valueIndexes[Types.HIGH_CRITICAL]) / 10

            stateMessage = "%s %s: %s%s" % (
                state.name, valueIndexes[Types.NAME], valueIndexes[Types.VALUE], valueIndexes[Types.UNIT]
            )
            if verbose > 1:
                stateMessage += "|" + "%s:%s;%s:%s" % (
                    valueIndexes[Types.LOW_WARNING], valueIndexes[Types.HIGH_WARNING],
                    valueIndexes[Types.LOW_CRITICAL], valueIndexes[Types.HIGH_CRITICAL])

            stateMessages.append(stateMessage)
            perfData.append("'%s'=%s%s;%s:%s;%s:%s" % (
                valueIndexes[Types.NAME], valueIndexes[Types.VALUE], valueIndexes[Types.UNIT],
                valueIndexes[Types.LOW_WARNING], valueIndexes[Types.HIGH_WARNING], valueIndexes[Types.LOW_CRITICAL],
                valueIndexes[Types.HIGH_CRITICAL])
            )

    print_status_message(states, perfData)

    if verbose > 0:
        for message in stateMessages:
            print message

    exit(mostImportantState.value)
