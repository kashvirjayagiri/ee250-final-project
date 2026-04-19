import json
import time
import paho.mqtt.client as mqtt
from collections import defaultdict

BROKER_HOST = "localhost"
BROKER_PORT = 1883
RAW_TOPIC = "brewview/+/raw"
STATUS_TOPIC_FMT = "brewview/{}/status"

# below this means definitely occupied
THRESHOLD_OCCUPIED = 60
# above this means possibly vacant
THRESHOLD_VACANT = 80
# EMA smoothing factor (20% of the new value comes from the fresh raw reading)
ALPHA = 0.2
# seconds of empty evidence in order to switch to vacant
HOLDOVER_SECONDS = 30

# state per table
def fresh_state():
    return{
        "smoothed_distance": 100.0,
        "occupied": False,
        "vacant_since": None,
        "last_sound": 0,
        "last_update": None,
    }

state = defaultdict(fresh_state)

def process(table_id, distance_cm, sound, timestamp):
    s = state[table_id]
    now = time.time()

    # EMA filter - smooths out sensor noise
    s["smoothed_distance"] = ALPHA * distance_cm + (1-ALPHA) * s["smoothed_distance"]
    s["last_sound"] = sound
    s["last_update"] = now
    dist = s["smoothed_distance"]
    
    # state + sensor fusion + holdover logic
    if dist < THRESHOLD_OCCUPIED:
        s["occupied"] = True
        s["vacant_since"] = None
    
    elif dist > THRESHOLD_VACANT and sound == 0: #both sensors agree vacant
        # start holdover timer if not started already
        if s["vacant_since"] is None:
            s["vacant_since"] = now
            print(f" [{table_id}] Holdover timer started")
        # when it's been vacant for longer than holdover_seconds, switch to vacant
        elif now - s["vacant_since"] >= HOLDOVER_SECONDS:
            if s["occupied"]:
                print(f" [{table_id}] Holdover elapsed - switching to VACANT")
            s["occupied"] = False

    elif dist > THRESHOLD_VACANT and sound == 1:
        # distance says vacant but sound says presence: hold state -> reset timer
        print(f" [{table_id}] Sound detected near threshold - holding state")
        s["vacant_since"] = None

    else:
        # hold previous state -> reset timer
        s["vacant_since"] = None

    # build status payload
    vacant_since_str = (
        f"+{round(now - s['vacant_since'])}s"
        if s["vacant_since"] else "None"
    )
    print(
        f"[{table_id}] {'OCCUPIED' if s['occupied'] else 'VACANT    '} | "
        f"raw={distance_cm:6.1f} cm | "
        f"smoothed={dist:6.1f} cm | "
        f"sound={sound} | "
        f"vacant_since={vacant_since_str:>8}"
    )

    return{
        "table": table_id,
        "occupied": s["occupied"],
        "distance_cm": round(distance_cm, 1),
        "smoothed_distance": round(dist, 1),
        "sound": sound,
        "timestamp": timestamp
    }

# MQTT callbacks
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"[edge processor] Connected to broker. Subscribing to {RAW_TOPIC}")
        client.subscribe(RAW_TOPIC)

    else:
        print(f"[edge processor] Connection failed, rc={rc}")

def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode())
        table_id = data["table"]
        distance = float(data["distance_cm"])
        sound = int(data["sound"])
        timestamp = float(data["timestamp"])
    except(KeyError, ValueError, json.JSONDecodeError) as e:
        print(f"[edge process] Bad payload on {msg.topic}: {e}")
        return
    
    result = process(table_id, distance, sound, timestamp)
    status_topic = STATUS_TOPIC_FMT.format(table_id)
    client.publish(status_topic, json.dumps(result))

def main():
    client = mqtt.Client(client_id="edge_processor")
    client.on_connect = on_connect
    client.on_message = on_message

    print("[edge processor] Edge processing service starting.")
    client.connect(BROKER_HOST, BROKER_PORT)
    client.loop_forever()

if __name__ == "__main__":
    main()