from easysnmp import Session
from enum import Enum, IntEnum
import sys
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


def convert_state_to_nagios(state):
    state = int(state)
    if state == 2:
        return NagiosState.OK
    elif state == 3 or state == 5:
        return NagiosState.WARNING
    elif state == 4 or state == 6:
        return NagiosState.CRITICAL


def print_status_message(states, perfData):
    warning_name_string = ""
    for name in states["WARNING"]:
        warning_name_string += ", " if not warning_name_string == "" else "" + name

    critical_name_string = ""
    for name in states["CRITICAL"]:
        critical_name_string += ", " if not critical_name_string == "" else "" + name

    result_message = ""
    if len(perfData) < 1:
        print "%s sensorProbe2plus: There is no sensor on the given port" % NagiosState.UNKNOWN.name
        exit(3)
    elif len(states["WARNING"]) > 0 and len(states["CRITICAL"]) > 0:
        result_message = "CRITICAL sensorProbe2plus: Sensor reports state CRITICAL for %d sensor%s (%s) " \
                "and state WARNING for %d sensor%s (%s)" % (
                    len(states["CRITICAL"]),
                    "s" if len(states["CRITICAL"]) > 1 else "",
                    critical_name_string,
                    len(states["WARNING"]),
                    "s" if len(states["WARNING"]) > 1 else "",
                    warning_name_string
                )
    elif len(states["WARNING"]) > 0:
        result_message = "WARNING sensorProbe2plus: Sensor reports state WARNING for %d sensor%s (%s)" % (
            len(states["WARNING"]), "s" if len(states["WARNING"]) > 1 else "", warning_name_string)
    elif len(states["CRITICAL"]) > 0:
        result_message = "CRITICAL sensorProbe2plus: Sensor reports state CRITICAL for %d sensor%s (%s)" % (
            len(states["CRITICAL"]), "s" if len(states["CRITICAL"]) > 1 else "", critical_name_string)
    else:
        result_message = "OK sensorProbe2plus: Sensor reports that everything is fine"

    result_message += "|"
    for data in perfData:
        result_message += data + " "

    print result_message


version = 1.0

verbose = 0
hostname = ""
community = ""
port = 0

parser = argparse.ArgumentParser(description='Check plugin for AKCP SensorProbe2+')
parser.add_argument("-V", "--version", action="store_true")
parser.add_argument("-v", "--verbose", action="count", default=0, help="increase output verbosity")
parser.add_argument("-p", "--port", help="port of the sensor to check", type=int, default=0)
required = parser.add_argument_group('required arguments')
required.add_argument("-H", "--hostname", help="host of the SensorProbe2+", required=True)
required.add_argument("-C", "--community", help="community of the SensorProbe2+", required=True)

args = parser.parse_args()
if args.version:
    print "AKCP SensorProbe2+ Version %s" % version
    sys.exit()
else:
    verbose = args.verbose if args.verbose <= 3 else 3
    hostname = args.hostname
    community = args.community
    port = args.port

session = Session(hostname=hostname, community=community, version=2)
result = session.walk("1.3.6.1.4.1.3854.3.5")

mostImportantState = NagiosState.OK
stateMessages = []
perfData = []
sensors = {}

for data in result:
    oid = data.oid.split(".")
    value = data.value

    index = int(oid[11])

    try:
        Types(index)
    except ValueError:
        continue

    category = int(oid[9])
    if category == 1 or category > 20:
        continue

    port = int(oid[15])
    if not args.port == 0 and not args.port - 1 == port:
        continue

    sensorIndex = int(oid[16])

    if not sensors.has_key(port):
        sensors[port] = {}

    if not sensors[port].has_key(sensorIndex):
        sensors[port][sensorIndex] = {}

    sensors[port][sensorIndex][index] = value

states = {"OK": [], "WARNING": [], "CRITICAL": []}
for port, sensorIndexes in sensors.iteritems():
    for sensorIndex, indexes in sensorIndexes.iteritems():
        state = convert_state_to_nagios(indexes[Types.STATE])
        if state.value > mostImportantState.value:
            mostImportantState = state

        states[state.name].append(indexes[Types.NAME])

        if not indexes.has_key(Types.VALUE):
            value = 0 if state == NagiosState.OK else 1
            stateMessages.append(
                "%s %s" % (state.name, indexes[Types.NAME]))
            perfData.append("'%s'=%s;" % (indexes[Types.NAME], value))
            continue

        if indexes[Types.UNIT] == "C":
            indexes[Types.VALUE] = float(indexes[Types.VALUE]) / 10
            indexes[Types.LOW_CRITICAL] = float(indexes[Types.LOW_CRITICAL]) / 10
            indexes[Types.LOW_WARNING] = float(indexes[Types.LOW_WARNING]) / 10
            indexes[Types.HIGH_WARNING] = float(indexes[Types.HIGH_WARNING]) / 10
            indexes[Types.HIGH_CRITICAL] = float(indexes[Types.HIGH_CRITICAL]) / 10

        stateMessage = "%s %s: %s%s" % (state.name, indexes[Types.NAME], indexes[Types.VALUE], indexes[Types.UNIT])
        if verbose > 1:
            stateMessage += "|" + "%s:%s;%s:%s" % (
                indexes[Types.LOW_WARNING], indexes[Types.HIGH_WARNING],
                indexes[Types.LOW_CRITICAL], indexes[Types.HIGH_CRITICAL])

        stateMessages.append(stateMessage)
        perfData.append("'%s'=%s%s;%s:%s;%s:%s" % (
            indexes[Types.NAME], indexes[Types.VALUE], indexes[Types.UNIT], indexes[Types.LOW_WARNING],
            indexes[Types.HIGH_WARNING], indexes[Types.LOW_CRITICAL], indexes[Types.HIGH_CRITICAL]))

print_status_message(states, perfData)

if verbose > 0:
    for message in stateMessages:
        print message

exit(mostImportantState.value)
