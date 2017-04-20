## check_sensorProbe2plus ##

### Description ###

This plugin serves the purpose of receiving data from the SensorProbe2+ and checking its state.


### Dependencies ###

+ [PySNMP](https://github.com/etingof/pysnmp)

### Usage ###

```
check_sensorProbe2plus.py -H -C [-p] [-V] [-v] [-h]
```

#### required arguments: ####

+ **HOSTNAME:** host of the SensorProbe2+  
  `` -H, --hostname  ``
+ **COMMUNITY:** read community of the SensorProbe2+  
  `` -C, --community ``

#### optional arguments: ####

+ **HELP** show the help message and exit  
  `` -h, --help ``
+ **VERSION** shows the current version of the check plugin  
  `` -V, --version ``
+ **VERBOSE** increases output verbosity (-v or -vv)  
  `` -v, --verbose ``
+ **PORT** port of the sensor to check (shows all if not set)  
  `` -p, --port ``
