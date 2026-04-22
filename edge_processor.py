import json
import time
import paho.mqtt.client as mqtt
from collections import defaultdict

BROKER_HOST      = "localhost"
BROKER_PORT      = 1883
RAW_TOPIC        = "brewview/+/raw"
STATUS_TOPIC_FMT = "brewview/{}/status"

ALPHA            = 0.4
# usually would be longer in real life but use 5 seconds for demo
HOLDOVER_SECONDS = 5
HYSTERESIS_GAP   = 20


def fresh_state():
    return {
        "smoothed_distance": 100.0,
        "occupied":          False,
        "vacant_since":      None,
        "last_update":       None,
    }

state = defaultdict(fresh_state)


def process(table_id, distance_cm, timestamp, threshold):
    s   = state[table_id]
    now = time.time()

    # EMA filter
    s["smoothed_distance"] = ALPHA * distance_cm + (1 - ALPHA) * s["smoothed_distance"]
    s["last_update"]       = now
    dist = s["smoothed_distance"]

    # dynamic thresholds from potentiometer
    occupied_threshold = threshold
    vacant_threshold   = threshold + HYSTERESIS_GAP

    # hysteresis + holdover
    if dist < occupied_threshold:
        s["occupied"]     = True
        s["vacant_since"] = None

    elif dist > vacant_threshold:
        if s["vacant_since"] is None:
            s["vacant_since"] = now
            print(f"  [{table_id}] Holdover timer started")
        elif now - s["vacant_since"] >= HOLDOVER_SECONDS:
            if s["occupied"]:
                print(f"  [{table_id}] Holdover elapsed - switching to VACANT")
            s["occupied"] = False

    else:
        s["vacant_since"] = None

    vacant_since_str = (
        f"+{round(now - s['vacant_since'])}s"
        if s["vacant_since"] else "None"
    )
    print(
        f"[{table_id}] {'OCCUPIED' if s['occupied'] else 'VACANT  '} | "
        f"raw={distance_cm:6.1f} cm | "
        f"smoothed={dist:6.1f} cm | "
        f"threshold={threshold} cm | "
        f"vacant_since={vacant_since_str:>8}"
    )

    return {
        "table":             table_id,
        "occupied":          s["occupied"],
        "distance_cm":       round(distance_cm, 1),
        "smoothed_distance": round(dist, 1),
        "threshold":         threshold,
        "timestamp":         timestamp
    }


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"[edge processor] Connected to broker. Subscribing to {RAW_TOPIC}")
        client.subscribe(RAW_TOPIC)
    else:
        print(f"[edge processor] Connection failed, rc={rc}")


def on_message(client, userdata, msg):
    try:
        data      = json.loads(msg.payload.decode())
        table_id  = data["table"]
        distance  = float(data["distance_cm"])
        timestamp = float(data["timestamp"])
        threshold = int(data.get("threshold", 60))
    except (KeyError, ValueError, json.JSONDecodeError) as e:
        print(f"[edge processor] Bad payload on {msg.topic}: {e}")
        return

    result       = process(table_id, distance, timestamp, threshold)
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