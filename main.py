import json

from micropython import const
import ubinascii
import network
from secrets import wifi_SSID, wifi_password
from umqtt.robust2 import MQTTClient
from machine import Pin, UART, Timer
import time
import re

DEBUG = const(False)
# Create a unique name for the Pico
pico_id = "pico-" + ubinascii.hexlify(machine.unique_id()).decode()


def toggle_led(timer):
    print("toggling")
    led.toggle()
    
def turn_off_led(timer):
    led.off()


timer_for_led_off = Timer()
def read_uart():
    if DEBUG:
        file = open("rawmessage.txt", "b")
        return file.read()
    else:
        print("Starting to read")
        data_request_pin.init(mode=Pin.OUT)
        # Read until exactly 635 bytes are processed
        rxdata = bytes()
        while len(rxdata) != 635:
            print("Checking for 635 bytes")
            # Reset rxdata every time it does not match 635
            rxdata = bytes()
            # Wait for data to come
            while uart.any() == 0:
                pass
            while uart.any() > 0:
                led.on()
                rxdata += uart.read()
        timer_for_led_off.init(mode=Timer.ONE_SHOT, period=250, callback=turn_off_led)
        data_request_pin.init(mode=Pin.IN)
        return rxdata


def parse_message(data):
    # Convert binary data to string
    data = data.decode()

    def extract(expression, group):
        return re.search(expression, data).group(group)

#    def decode_timestamp(timestamp, dst):
    def decode_timestamp(timestamp):
        year = "20" + timestamp[0:2]
        month = timestamp[2:4]
        day = timestamp[4:6]
        hour = timestamp[6:8]
        minute = timestamp[8:10]
        second = timestamp[10:12]
#        if dst == "S":
#            tzinfo = "+02:00"
#        elif dst == "X":
#            tzinfo = "+01:00"
#        return "%s-%s-%sT%s:%s:%s%s" % (year, month, day, hour, minute, second, tzinfo)
        return "%s-%s-%sT%s:%s:%s" % (year, month, day, hour, minute, second)

    extracted_data = {"date_time": decode_timestamp(extract("\d-\d:1\.0\.0\((\d+)(.)", 1)),  # DateTime
#                                                    extract("\d-\d:1\.0\.0\((\d+)(.)", 2)),  # DST
                      "meter_active_energy_out": extract("\d-\d:1\.8\.0\((\d+.\d+)", 1),
                      "meter_active_energy_in": extract("\d-\d:2\.8\.0\((\d+.\d+)", 1),
                      "meter_reactive_energy_out": extract("\d-\d:3\.8\.0\((\d+.\d+)", 1),
                      "meter_reactive_energy_in": extract("\d-\d:4\.8\.0\((\d+.\d+)", 1),
                      "active_power_out": extract("\d-\d:1\.7\.0\((\d+.\d+)", 1),
                      "active_power_in": extract("\d-\d:2\.7\.0\((\d+.\d+)", 1),
                      "reactive_power_out": extract("\d-\d:3\.7\.0\((\d+.\d+)", 1),
                      "reactive_power_in": extract("\d-\d:4\.7\.0\((\d+.\d+)", 1),
                      "active_power_L1_out": extract("\d-\d:21\.7\.0\((\d+.\d+)", 1),
                      "active_power_L1_in": extract("\d-\d:41\.7\.0\((\d+.\d+)", 1),
                      "active_power_L2_out": extract("\d-\d:61\.7\.0\((\d+.\d+)", 1),
                      "active_power_L2_in": extract("\d-\d:22\.7\.0\((\d+.\d+)", 1),
                      "active_power_L3_out": extract("\d-\d:42\.7\.0\((\d+.\d+)", 1),
                      "active_power_L3_in": extract("\d-\d:62\.7\.0\((\d+.\d+)", 1),
                      "reactive_power_L1_out": extract("\d-\d:23\.7\.0\((\d+.\d+)", 1),
                      "reactive_power_L1_in": extract("\d-\d:43\.7\.0\((\d+.\d+)", 1),
                      "reactive_power_L2_out": extract("\d-\d:63\.7\.0\((\d+.\d+)", 1),
                      "reactive_power_L2_in": extract("\d-\d:24\.7\.0\((\d+.\d+)", 1),
                      "reactive_power_L3_out": extract("\d-\d:44\.7\.0\((\d+.\d+)", 1),
                      "reactive_power_L3_in": extract("\d-\d:64\.7\.0\((\d+.\d+)", 1),
                      "voltage_L1": extract("\d-\d:32\.7\.0\((\d+.\d+)", 1),
                      "voltage_L2": extract("\d-\d:52\.7\.0\((\d+.\d+)", 1),
                      "voltage_L3": extract("\d-\d:72\.7\.0\((\d+.\d+)", 1),
                      "current_L1": extract("\d-\d:31\.7\.0\((\d+.\d+)", 1),
                      "current_L2": extract("\d-\d:51\.7\.0\((\d+.\d+)", 1),
                      "current_L3": extract("\d-\d:71\.7\.0\((\d+.\d+)", 1)}  

    return extracted_data


def read_and_publish(timer):
    message = read_uart()
    extracted_data = parse_message(message)
    stringified_data = json.dumps(extracted_data)
    c.publish(pico_id + "/meter", stringified_data)
    c.publish(pico_id + "/system/status", "online")


print(pico_id)

# Check if LED works
print("Checking LED for 5 seconds")
led = Pin("LED", Pin.OUT)
led.on()
time.sleep(5)

# Initialise Wifi
print("Initializing WiFi")
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(wifi_SSID, wifi_password)

# Initialize UART for P1 port
data_request_pin = Pin(28, Pin.IN, pull=None, value=1)  # Data request pin cannot be low as per specification.It has
# to be high impedance state. We store value 1 so when we change it to Pin.OUT it is immediately set to high.
uart = UART(0, 115200, invert=UART.INV_RX)

# Checking Wi-Fi before continuing
tim = Timer()
tim.init(freq=3, mode=Timer.PERIODIC, callback=toggle_led)
while wlan.status() != 3:
    print("Waiting, wlan status " + str(wlan.status()))
    time.sleep(1)
print("Connected, wlan status " + str(wlan.status()))
tim.deinit()
led.off()

c = MQTTClient(pico_id, "192.168.1.100", keepalive=30)
c.set_last_will(pico_id + "/system/status", "offline", retain=True)
c.connect()


# Discovery packet for Homeassistant
def publish_config(discovery_topic, name, device_class=None, unit_of_measurement=None, state_class=None):
    config_payload = {
        "name": name,
        "state_topic": pico_id + "/meter",
        "availability_topic": pico_id + "/system/status",
        "device": {
            "identifiers": pico_id,
            "name": "Raspberry Pi Pico W"
        },
        "unique_id": pico_id + "-" + discovery_topic,
        "device_class": device_class,
        "value_template": "{{ value_json." + discovery_topic + " }}",
        "unit_of_measurement": unit_of_measurement,
        "state_class": state_class
    }

    if device_class is None:
        del config_payload["device_class"]
    if unit_of_measurement is None:
        del config_payload["unit_of_measurement"]
    if state_class is None:
        del config_payload["state_class"]

    c.publish("homeassistant/sensor/" + pico_id + "/" + discovery_topic + "/config", json.dumps(config_payload), retain=True)


publish_config("date_time", "Timestamp electricity", "timestamp")
publish_config("meter_active_energy_out", "Meter active energy out", "energy", "kWh", "total_increasing")
publish_config("meter_active_energy_in", "Meter active energy in", "energy", "kWh", "total_increasing")
publish_config("meter_reactive_energy_out", "Meter reactive energy out", "energy", "kWh", "total_increasing")
publish_config("meter_reactive_energy_in", "Meter reactive energy in", "energy", "kWh", "total_increasing")
publish_config("active_power_out", "Active power out", "power", "kW", "measurement")
publish_config("active_power_in", "Active power in", "power", "kW", "measurement")
publish_config("reactive_power_out", "Reactive power out", "power", "kW", "measurement")
publish_config("reactive_power_in", "Reactive power in", "power", "kW", "measurement")


publish_config("tariff", "Tariff")
publish_config("power", "Actual power", "power", "kW", "measurement")
publish_config("n_power_failures", "N. of power failures", state_class="total_increasing")
publish_config("n_long_power_failures", "N. of long power failures", state_class="total_increasing")
publish_config("n_voltage_drops", "N. of voltage drops", state_class="total_increasing")
publish_config("n_voltage_surges", "N. of voltage surges", state_class="total_increasing")
publish_config("instant_voltage", "Voltage", "voltage", "V", "measurement")
publish_config("instant_current", "Current", "current", "A", "measurement")
publish_config("instant_active_power", "Active power", "power", "kW", "measurement")
publish_config("gas_date_time", "Timestamp gas", "timestamp")
publish_config("gas_volume", "Gas volume", "gas", "m3", "total_increasing")

# Send data to broker every 10 seconds
send_tim = Timer()
send_tim.init(period=10000, mode=Timer.PERIODIC, callback=read_and_publish)
