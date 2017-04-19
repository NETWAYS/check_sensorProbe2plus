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


def print_status_message(state, perfData, stateCount):
    message = ""

    if len(perfData) < 1:
        print "%s sensorProbe2plus: There is no sensor on the given port" % NagiosState.UNKNOWN.name
        exit(3)
    elif state.value == 0:
        message = "%s sensorProbe2plus: Sensor reports that everything is fine" % state.name
    elif state.value == 1:
        message = "%s sensorProbe2plus: Sensor reports that %d %s in state WARNING" % (state.name, stateCount[1], "sensors are" if stateCount[1] > 1 else "sensor is")
    elif state.value == 2:
        message = "%s sensorProbe2plus: Sensor reports that %d %s in state CRITICAL" % (state.name, stateCount[2], "sensors are" if stateCount[2] > 1 else "sensor is")

    if verbose > 0:
        message += "|"
        for data in perfData:
            message += data + " "

    print message


version = 1.0

indexesNeeded = [2, 5, 6, 9, 10, 11, 12, 20]

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
stateCounts = [0, 0, 0]
sensors = {}

for data in result:
    oid = data.oid.split(".")
    value = data.value

    index = int(oid[11])
    if index not in indexesNeeded:
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

for port, sensorIndexes in sensors.iteritems():
    for sensorIndex, indexes in sensorIndexes.iteritems():
        state = convert_state_to_nagios(indexes[Types.STATE])
        if state.value > mostImportantState.value:
            mostImportantState = state
        stateCounts[state.value] += 1

        if not indexes.has_key(Types.VALUE):
            stateMessages.append(
                "%s %s" % (state.name, indexes[Types.NAME]))
            continue

        if indexes[Types.UNIT] == "C":
            indexes[Types.VALUE] = float(indexes[Types.VALUE]) / 10
            indexes[Types.LOW_CRITICAL] = float(indexes[Types.LOW_CRITICAL]) / 10
            indexes[Types.LOW_WARNING] = float(indexes[Types.LOW_WARNING]) / 10
            indexes[Types.HIGH_WARNING] = float(indexes[Types.HIGH_WARNING]) / 10
            indexes[Types.HIGH_CRITICAL] = float(indexes[Types.HIGH_CRITICAL]) / 10

        stateMessages.append(
            "%s %s: %s%s" % (state.name, indexes[Types.NAME], indexes[Types.VALUE], indexes[Types.UNIT]))
        perfData.append("'%s'=%s%s;%s:%s;%s:%s" % (
        indexes[Types.NAME], indexes[Types.VALUE], indexes[Types.UNIT], indexes[Types.LOW_WARNING],
        indexes[Types.HIGH_WARNING], indexes[Types.LOW_CRITICAL], indexes[Types.HIGH_CRITICAL]))

print_status_message(mostImportantState, perfData, stateCounts)

if verbose > 1:
    for message in stateMessages:
        print message

exit(mostImportantState.value)