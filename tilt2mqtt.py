#!/usr/bin/env python3
"""
Wrapper for reading messages from Tilt wireless hydrometer and forwarding them to MQTT topics. 

The device acts as a simple Bluetooth IBeacon sending the following two values,

 * major: Temperature in Fahrenheit
 * minor: Specific gravity

The raw values read from the Tilt are uncalibrated and should be calibrated before use. The script works a follows,

 1. Listen for local IBeacon devices
 2. If found the callback is triggered
  * Translate the UUID to a Tilt color
  * Extract and convert measurements from the device
  * Construct a JSON payload
  * Send payload to the MQTT server
 3. Stop listening and sleep for X minutes before getting a new measurement

This script has been tested on Linux.

# How to run

First install Python dependencies

 pip install beacontools paho-mqtt requests pybluez

Run the script,

 python tilt2mqtt.py

Note: A MQTT server is required.
"""

import time
import logging as lg
import os
import json
from beacontools import BeaconScanner, IBeaconFilter, parse_packet, const
import paho.mqtt.publish as publish
import requests
from ast import literal_eval

#
# Constants
#
sleep_interval = 60.0*10  # How often to listen for new messages in seconds

lg.basicConfig(level=lg.INFO)
LOG = lg.getLogger()

# Create handlers
c_handler = lg.StreamHandler()
f_handler = lg.FileHandler('/tmp/tilt.log')
c_handler.setLevel(lg.DEBUG)
f_handler.setLevel(lg.INFO)

# Create formatters and add it to handlers
c_format = lg.Formatter('%(name)s - %(levelname)s - %(message)s')
f_format = lg.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
c_handler.setFormatter(c_format)
f_handler.setFormatter(f_format)

# Add handlers to the logger
LOG.addHandler(c_handler)
LOG.addHandler(f_handler)

# Unique bluetooth IDs for Tilt sensors
TILTS = {
        'a495bb10-c5b1-4b44-b512-1370f02d74de': 'Red',
        'a495bb20-c5b1-4b44-b512-1370f02d74de': 'Green',
        'a495bb30-c5b1-4b44-b512-1370f02d74de': 'Black',
        'a495bb40-c5b1-4b44-b512-1370f02d74de': 'Purple',
        'a495bb50-c5b1-4b44-b512-1370f02d74de': 'Orange',
        'a495bb60-c5b1-4b44-b512-1370f02d74de': 'Blue',
        'a495bb70-c5b1-4b44-b512-1370f02d74de': 'Yellow',
        'a495bb80-c5b1-4b44-b512-1370f02d74de': 'Pink',
}

calibration = {
        'Red'    : literal_eval(os.getenv('TILT_CAL_RED', "None")),
        'Green'  : literal_eval(os.getenv('TILT_CAL_GREEN', "None")),
        'Black'  : literal_eval(os.getenv('TILT_CAL_BLACK', "None")),
        'Purple' : literal_eval(os.getenv('TILT_CAL_PURPLE', "None")),
        'Orange' : literal_eval(os.getenv('TILT_CAL_ORANGE', "None")),
        'Blue'   : literal_eval(os.getenv('TILT_CAL_BLUE', "None")),
        'Yellow' : literal_eval(os.getenv('TILT_CAL_YELLOW', "None")),
        'Pink'   : literal_eval(os.getenv('TILT_CAL_PINK', "None")),
}
#@@@#LOG.info("TILT Blue Calibration: {}".format(calibration['Blue']))


# MQTT Settings
config = {
        'host': os.getenv('MQTT_IP', '127.0.0.1'),
        'port':int(os.getenv('MQTT_PORT', 1883)),
        'auth': literal_eval(os.getenv('MQTT_AUTH', "None")),
        'debug': os.getenv('MQTT_DEBUG', True),
}
#@@@#LOG.info("MQTT Broker: {}:{}  AUTH:{}".format(config['host'], config['port'], config['auth']))
#@@@#LOG.info("AUTH['username']:{}  AUTH['password']:{}".format(config['auth']['username'],config['auth']['password']))

def callback(bt_addr, rssi, packet, additional_info):
    """Message recieved from tilt
    """
    LOG.info(additional_info)
    msgs = []
    color = "unknown"

    print("<%s, %d> %s %s" % (bt_addr, rssi, packet, additional_info))

    try:
        uuid = additional_info["uuid"]
        #@@@#color = TILTS[uuid.replace('-','')]
        color = TILTS[uuid]
    except KeyError:
        LOG.error("Unable to decode tilt color. Additional info was {}".format(additional_info))

    try:
        # Get uncalibrated values
        temperature_fahrenheit = float(additional_info["major"])
        specific_gravity = float(additional_info["minor"])/1000

        # See if have calibration values. If so, use them.
        if (calibration[color]):
            suffix = "cali"
            temperature_fahrenheit += calibration[color]['temp']
            specific_gravity += calibration[color]['sg']
        else:
            suffix = "uncali"
        
        # convert temperature
        temperature_celsius = (temperature_fahrenheit - 32) * 5/9

        # convert gravity
        degree_plato = 135.997*pow(specific_gravity, 3) - 630.272*pow(specific_gravity, 2) + 1111.14*specific_gravity - 616.868

        data = {
            "specific_gravity_"+suffix: "{:.3f}".format(specific_gravity),
            "plato_"+suffix: "{:.2f}".format(degree_plato),
            "temperature_celsius_"+suffix: "{:.2f}".format(temperature_celsius),
            "temperature_fahrenheit_"+suffix: "{:.1f}".format(temperature_fahrenheit),
            "rssi": "{:d}".format(rssi)
        }

        # Create message                                        QoS   Retain message
        msgs.append(("tilt/{}".format(color), json.dumps(data), 2,    1))

        # Send message via MQTT server
        publish.multiple(msgs, hostname=config['host'], port=config['port'], auth=config['auth'], protocol=4)
    except KeyError:
        LOG.error("Device does not look like a Tilt Hydrometer.")



def scan(scantime=25.0):        
        LOG.info("Create BeaconScanner()")
        ## Only look for known Tilts        
        scanner = BeaconScanner(callback, device_filter=[IBeaconFilter(uuid=x) for x in list(TILTS.keys())])

        LOG.info("Started scanning")
        # Start scanning in active mode
        scanner.start()

        # Time to wait for tilt to respond
        time.sleep(scantime)

        # Stop again
        scanner.stop()
        LOG.info("Stopped scanning")

        
OLD=None
if (OLD):
    ## Only look for known Tilts        
    scanner = BeaconScanner(callback, device_filter=[IBeaconFilter(uuid=x) for x in list(TILTS.keys())])

    scanner.start()
    monitor = scanner._mon
    while(1):
        LOG.info("Started scanning")
        # Start scanning in active mode
        monitor.toggle_scan(True)

        # Time to wait for tilt to respond
        time.sleep(25)

        LOG.info("Stopped scanning")
        # Stop again
        monitor.toggle_scan(False)

        # Wait until next scan periode
        time.sleep(sleep_interval)

else:
    while(1):

        # Scan for iBeacons of Tilt for 25 seconds
        scan(25.0)

        #@@@## Test mqtt publish with sample data
        #@@@#callback("ea:ca:eb:f0:0f:b5", -95, "", {'uuid': 'a495bb60-c5b1-4b44-b512-1370f02d74de', 'major': 73, 'minor': 989})
        #@@@#time.sleep(2.0)

        # Wait until next scan periode
        time.sleep(sleep_interval)
