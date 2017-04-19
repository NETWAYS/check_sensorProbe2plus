from pysnmp.entity.rfc3413.oneliner import cmdgen
from enum import Enum
import sys
import argparse


class NagiosState(Enum):
    OK = 0
    WARNING = 1
    CRITICAL = 2
    UNKNOWN = 3


sensorNameOID   = (1, 3, 6, 1, 4, 1, 3854, 3, 5, 1, 1, 2, 0, 0, 0)
valueOID        = (1, 3, 6, 1, 4, 1, 3854, 3, 5, 1, 1, 4, 0, 0, 0)
unitOID         = (1, 3, 6, 1, 4, 1, 3854, 3, 5, 1, 1, 5, 0, 0, 0)
stateOID        = (1, 3, 6, 1, 4, 1, 3854, 3, 5, 1, 1, 6, 0, 0, 0)

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

if port > 0:
    port -= 1
    sensorNameOID += (port,)
    valueOID += (port,)
    unitOID += (port,)
    stateOID += (port,)

def convert_state_to_nagios(state):
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

generator = cmdgen.CommandGenerator()
communityData = cmdgen.CommunityData(community)
transport = cmdgen.UdpTransportTarget((hostname, 161))

command = getattr(generator, 'nextCmd')

errorIndication, errorStatus, errorIndex, sensorNames = command(communityData, transport, sensorNameOID)
sensorValues = command(communityData, transport, valueOID)[3]
sensorUnits = command(communityData, transport, unitOID)[3]
sensorStates = command(communityData, transport, stateOID)[3]

mostImportantState = NagiosState.OK
if errorIndication:
    print "%s %s" % (NagiosState.UNKNOWN.name, errorIndication)
    mostImportantState = NagiosState.UNKNOWN
elif errorStatus:
    print('%s %s at %s' % (
        NagiosState.CRITICAL.name,
        errorStatus.prettyPrint(),
            errorIndex and sensorNames[int(errorIndex)-1] or '?'
        )
    )
    mostImportantState = NagiosState.CRITICAL
else:
    stateMessages = []
    perfData = []
    stateCounts = [0, 0, 0]
    for sensorName in sensorNames:
        key = sensorNames.index(sensorName)
        state = convert_state_to_nagios(sensorStates[key][0][1])
        if state.value > mostImportantState.value:
            mostImportantState = state
        stateCounts[state.value] += 1
        stateMessages.append("%s %s: %s%s" % (state.name, sensorName[0][1], sensorValues[key][0][1], sensorUnits[key][0][1]))
        perfData.append("'%s'=%s%s" % (sensorName[0][1], sensorValues[key][0][1], sensorUnits[key][0][1]))

    print_status_message(mostImportantState, perfData, stateCounts)

    if verbose > 1:
        for message in stateMessages:
            print message

    exit(mostImportantState.value)