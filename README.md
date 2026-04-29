# check_sensorProbe2plus

This plugin serves the purpose of receiving data from the SensorProbe2+ and checking its state.

## Dependencies

+ [PySNMP](https://github.com/etingof/pysnmp)

## Usage

```
usage: check_sensorProbe2plus.py [-h] [-V] [-v] [-p PORT] -H HOSTNAME -C COMMUNITY

Check plugin for AKCP SensorProbe2+

options:
  -h, --help            show this help message and exit
  -V, --version
  -v, --verbose         increase output verbosity (-v or -vv)
  -p, --port PORT       port of the sensors to check (shows all if not set)

required arguments:
  -H, --hostname HOSTNAME
                        host of the sensor probe
  -C, --community COMMUNITY
                        read community of the sensor probe
```
