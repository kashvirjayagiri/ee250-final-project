import time
import json
import argparse
import grovepi
import paho.mqtt.client as mqtt

# Argument parsing
    # argparse command line arguments better when you want to run multiple instances of the same script for multiple tables
parser = argparse.ArgumentParser(description="BrewView physical sensor node")
parser.add_argument("--table_id", required=True,    help="Table identifier (ex. table_1)")
parser.add_argument("--broker", default="localhost", help="MQTT broker host")
parser.add_argument("--port", type=int, default=1883)
parser.add_argument("--interval", type=float, default=2.0, help="Publish interval in seconds")
args = parser.parse_args()

TOPIC = f"brewview/{args.table_id}/raw"

POT_PORT = 0
ULTRASONIC_PORT = 4

# MQTT setup
client = mqtt.Client(client_id = f"sensor_{args.table_id}")
client.connect(args.broker, args.port)
client.loop_start()
print(f"[{args.table_id}] Sensor node started - broker: {args.broker}:{args.port}, topic: {TOPIC}")


def get_distance():
    """Trigger ultrasonic sensor and return distance in cm. Returns None on timeout."""
    try:
        distance = grovepi.ultrasonicRead(ULTRASONIC_PORT)
        return round(distance, 1)
    except IOError:
        print(f"[{args.table_id}] Ultrasonic read error")
        return None

def get_threshold():
    try: 
        raw = grovepi.analogRead(POT_PORT)
        # map 0-1023 to a useful threshold range for occupancy, e.g. 30-100 cm 
        threshold = int(30 + (raw / 1023) * 70)
        return round(threshold / 5) * 5
    except IOError:
        print(f"[{args.table_id}] Potentiometer read error")
        return 60  # fallback to default

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
            "threshold": threshold,
            "timestamp": time.time()
        })

        client.publish(TOPIC, payload)
        print(f"[{args.table_id}] dist={distance:6.1f} cm | threshold={threshold} cm")

        time.sleep(args.interval)

except KeyboardInterrupt:
    print(f"[{args.table_id}] Shutting down sensor node.")

finally:
    client.loop_stop()
    client.disconnect()
