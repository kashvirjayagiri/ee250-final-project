import time
import json
import argparse
from datetime import datetime
import RPi.GPIO as GPIO
import paho.mqtt.client as mqtt

# Argument parsing
    # argparse command line arguments better when you want to run multiple instances of the same script for multiple tables
parser = argparse.ArgumentParser(description="BrewView physical sensor node")
parser.add_argument("--table_id", required=True,    help="Table identifier (ex. table_1)")
parser.add_argument("--trig", type=int, default=23, help="GPIO pin for HC-SR04 TRIG")
parser.add_argument("--echo", type=int, default=24, help="GPIO pin for HC-SR04 ECHO")
parser.add_argument("--sound", type=int, default=17, help="GPIO pin for KY-037 digital out")
parser.add_argument("--broker", default="localhost", help="MQTT broker host")
parser.add_argument("--port", type=int, default=1883)
parser.add_argument("--interval", type=float, default=2.0, help="Publish interval in seconds")
args = parser.parse_args()

TOPIC = f"brewview/{args.table_id}/raw"

# GPIO setup
GPIO.setmode(GPIO.BCM)
GPIO.setup(args.trig, GPIO.OUT)
GPIO.setup(args.echo, GPIO.IN)
GPIO.setup(args.sound, GPIO.IN)
GPIO.output(args.trig, False)
print(f"[{args.table_id}] Waiting for sensor to settle...")
time.sleep(2) # lets HC-SR04 stabilize on startup

# MQTT setup
client = mqtt.Client(client_id = f"sensor_{args.table_id}")
client.connect(args.broker, args.port)
client.loop_start()
print(f"[{args.table_id}] Sensor node started - broker: {args.broker}:{args.port}, topic: {TOPIC}")


def get_distance():
    """Trigger HC-SR04 and return distance in cm. Returns None on timeout."""
    
    # send 10 microsecond trigger pulse
    GPIO.output(args.trig, True)
    time.sleep(0.00001)
    GPIO.output(args.trig, False)

    # wait for echo to go high
    timeout_start = time.time()
    while GPIO.input(args.echo) == 0:
        if time.time() - timeout_start > 0.04:
            return None

    pulse_start = time.time()

    # wait for echo to go low
    while GPIO.input(args.echo) == 1:
        if time.time() - pulse_start > 0.04:
            return None
    
    pulse_end = time.time()

    # convert pulse duration to cm
    duration = pulse_end - pulse_start
    distance = (duration * 34300)/2
    return round(distance, 1)

def get_sound():
    """Read KY-037 digital ouput. Returns 1 is sound is detected, 0 if quiet."""
    return GPIO.input(args.sound)

try:
    while True:
        distance = get_distance()
        sound = get_sound()

        if distance is None:
            print(f"[{args.table_id}] Distance read timed out - skipping")
            time.sleep(args.interval)
            continue

        # create range and eliminate sensor noise (anything beyond 3m isn't important)
        if distance > 300:
            print(f"[{args.table_id}] Distance out of range ({distance} cm) - skipping")
            time.sleep(args.interval)
            continue

        payload = json.dumps({
            "table": args.table_id,
            "distance_cm": distance,
            "sound": sound,
            "timestamp": time.time()
        })

        client.publish(TOPIC, payload)
        print(f"[{args.table_id}] dist={distance:6.1f} cm | sound={sound}")

        time.sleep(args.interval)

except KeyboardInterrupt:
    print(f"[{args.table_id}] Shutting down sensor node.")

finally:
    GPIO.cleanup()
    client.loop_stop()
    client.disconnect()