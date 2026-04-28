# used CODEX to help with fail-proof integration to improve code after typing the main parts out on our own
import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

import paho.mqtt.client as mqtt
from flask import Flask, jsonify, render_template
from flask_socketio import SocketIO, emit


BASE_DIR = Path(__file__).parent.absolute()
DB_PATH = BASE_DIR / "occupancy.db"

MQTT_BROKER = os.getenv("MQTT_BROKER", "127.0.0.1")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC = "brewview/+/status"

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

db_lock = threading.Lock() # AI also helped implement locks


def get_db_connection(): # connect with the database
    connection = sqlite3.connect(DB_PATH, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    return connection


def init_db(): # initialize a connection to the database and create a table for our brew view project
    with db_lock:
        connection = get_db_connection()
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS occupancy_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                table_id TEXT NOT NULL,
                occupied INTEGER NOT NULL,
                distance_cm REAL,
                threshold_cm REAL,
                timestamp TEXT NOT NULL
            )
            """
        )
        connection.commit()
        connection.close()


def format_timestamp(raw_timestamp): # formatting the timestamp to be used in the table
    try:
        return datetime.fromtimestamp(float(raw_timestamp), tz=timezone.utc).isoformat()
    except (TypeError, ValueError):
        return datetime.now(timezone.utc).isoformat()


def normalize_event(payload, topic): # helps get the reqwuired table data entries
    # used AI especially for this to make integration easier
    topic_parts = topic.split("/")
    topic_table_id = topic_parts[1] if len(topic_parts) >= 3 else "unknown"

    return {
        "table_id": str(payload.get("table_id", payload.get("table", topic_table_id))),
        "occupied": bool(payload.get("occupied", False)),
        "distance_cm": payload.get("distance_cm"),
        "threshold": payload.get("threshold"),
        "timestamp": format_timestamp(payload.get("timestamp")),
    }


def insert_event(event): # helps insert new data into the database
    with db_lock: 
        connection = get_db_connection()
        connection.execute(
            """
            INSERT INTO occupancy_events (
                table_id,
                occupied,
                distance_cm,
                threshold_cm,
                timestamp
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                event["table_id"],
                int(event["occupied"]),
                event["distance_cm"],
                event["threshold"],
                event["timestamp"],
            ),
        )
        connection.commit()
        connection.close()


def fetch_latest_state_by_table(): # most recent occupancy status table is returned
    with db_lock:
        connection = get_db_connection()
        rows = connection.execute(
            """
            SELECT
                table_id,
                occupied,
                distance_cm,
                threshold_cm,
                timestamp
            FROM occupancy_events
            WHERE id IN (
                SELECT MAX(id)
                FROM occupancy_events
                GROUP BY table_id
            )
            ORDER BY table_id
            """
        ).fetchall()
        connection.close()

    current = []
    for row in rows:
        current.append(
            {
                "table_id": row["table_id"],
                "occupied": bool(row["occupied"]),
                "distance_cm": row["distance_cm"],
                "threshold": row["threshold_cm"],
                "timestamp": row["timestamp"],
            }
        )
    return current


def on_connect(client, userdata, flags, rc): # subscribing to the MQTT topic for smooth communication
    if rc == 0:
        print(f"Connected to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")
        client.subscribe(MQTT_TOPIC)
    else:
        print(f"MQTT connection failed with result code {rc}")


def on_message(client, userdata, message): # processing an update received through MQTT in json
    try:
        payload = json.loads(message.payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"Skipping malformed MQTT payload on {message.topic}: {exc}")
        return

    event = normalize_event(payload, message.topic)
    insert_event(event)
    socketio.emit("occupancy_update", event)
    print(f"Stored update for {event['table_id']} at {event['timestamp']}")


def start_mqtt_subscriber(): # 
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    try: # also used AI to protect our program from certain function failures
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_start()
    except OSError as exc:
        print(f"Could not connect to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}: {exc}")

    return client


@app.route("/", methods=["GET"]) # HTTP GET method to run the website
def index():
    return render_template("index.html")


@app.route("/api/current", methods=["GET"]) # HTTP GET method to fetch the current state of the table
def get_current():
    return jsonify(fetch_latest_state_by_table())


@socketio.on("connect") # as soon as we connect
def handle_socket_connect():
    emit("initial_state", fetch_latest_state_by_table())


if __name__ == "__main__":
    init_db()
    start_mqtt_subscriber()
    socketio.run(app, host="0.0.0.0", port=8080, debug=True)
