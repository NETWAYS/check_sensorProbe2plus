## check_sensorProbe2plus ##

### Description ###

This plugin serves the purpose of receiving data from the AKCP devices and checking the thresholds of the connected probes.

### Installation ###

# **ADD A HOW TO INSTALL** #

### Usage ###
```
check_sensorProbe2plus.py -H -C [-p][-V][-v][-h]
```
#### required arguments: ####
* **HOSTNAME:** host of the SensorProbe2+
  `` -H, --hostname  ``
* **COMMUNITY:** community of the SensorProbe2+
  `` -C, --community ``

### optional arguments: ###
* **HELP** show the help message and exit
  `` -h, --help ``
* **VERSION** shows the current version of the check plugin
  `` -V, --version ``
* **VERBOSE** increases output verbosity, has 2 stages:
  `` -v, --verbose ``
  `` -vv ``
* **PORT** port of the sensor to check
  `` -p, --port ``
