from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import paho.mqtt.client as mqtt
from flask import Flask, jsonify, render_template
from flask_socketio import SocketIO, emit


BASE_DIR = Path(__file__).parent.absolute()
DB_PATH = BASE_DIR / "occupancy.db"

MQTT_BROKER = os.getenv("MQTT_BROKER", "127.0.0.1")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPICS = ["brewview/+/status"]
MQTT_KEEPALIVE = 60

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "brewview-secret")
socketio = SocketIO(app, cors_allowed_origins="*")

db_lock = threading.Lock()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_timestamp(raw_timestamp: Any) -> datetime:
    if raw_timestamp is None:
        return utc_now()

    if isinstance(raw_timestamp, (int, float)):
        return datetime.fromtimestamp(raw_timestamp, tz=timezone.utc)

    if isinstance(raw_timestamp, str):
        normalized = raw_timestamp.strip()
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"

        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return utc_now()

        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    return utc_now()


def parse_occupied(raw_occupied: Any) -> bool:
    if isinstance(raw_occupied, bool):
        return raw_occupied

    if isinstance(raw_occupied, (int, float)):
        return bool(raw_occupied)

    if isinstance(raw_occupied, str):
        return raw_occupied.strip().lower() in {"1", "true", "occupied", "yes", "on"}

    return False


def parse_optional_float(raw_value: Any) -> float | None:
    if raw_value is None:
        return None

    try:
        return float(raw_value)
    except (TypeError, ValueError):
        return None


def get_db_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    return connection


def ensure_db_schema(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS occupancy_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_id TEXT NOT NULL,
            occupied INTEGER NOT NULL,
            distance_cm REAL,
            threshold_cm REAL,
            smoothed_distance_cm REAL,
            timestamp TEXT NOT NULL
        )
        """
    )

    column_names = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(occupancy_events)").fetchall()
    }

    if "threshold_cm" not in column_names:
        connection.execute("ALTER TABLE occupancy_events ADD COLUMN threshold_cm REAL")

    if "smoothed_distance_cm" not in column_names:
        connection.execute("ALTER TABLE occupancy_events ADD COLUMN smoothed_distance_cm REAL")


def init_db() -> None:
    with db_lock:
        connection = get_db_connection()
        ensure_db_schema(connection)
        connection.commit()
        connection.close()


def normalize_event(payload: Dict[str, Any], topic: str) -> Dict[str, Any]:
    topic_parts = topic.split("/")
    topic_table_id = topic_parts[1] if len(topic_parts) >= 3 else "unknown"
    timestamp = parse_timestamp(payload.get("timestamp"))

    return {
        "table_id": str(payload.get("table_id", payload.get("table", topic_table_id))),
        "occupied": parse_occupied(payload.get("occupied", payload.get("status", False))),
        "distance_cm": parse_optional_float(payload.get("distance_cm")),
        "threshold": parse_optional_float(payload.get("threshold")),
        "smoothed_distance": parse_optional_float(payload.get("smoothed_distance")),
        "timestamp": timestamp.isoformat(),
    }


def insert_event(event: Dict[str, Any]) -> None:
    with db_lock:
        connection = get_db_connection()
        ensure_db_schema(connection)
        connection.execute(
            """
            INSERT INTO occupancy_events (
                table_id,
                occupied,
                distance_cm,
                threshold_cm,
                smoothed_distance_cm,
                timestamp
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                event["table_id"],
                int(event["occupied"]),
                event["distance_cm"],
                event["threshold"],
                event["smoothed_distance"],
                event["timestamp"],
            ),
        )
        connection.commit()
        connection.close()


def fetch_latest_state_by_table() -> List[Dict[str, Any]]:
    with db_lock:
        connection = get_db_connection()
        ensure_db_schema(connection)
        rows = connection.execute(
            """
            SELECT
                table_id,
                occupied,
                distance_cm,
                threshold_cm,
                smoothed_distance_cm,
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

    return [
        {
            "table_id": row["table_id"],
            "occupied": bool(row["occupied"]),
            "distance_cm": row["distance_cm"],
            "threshold": row["threshold_cm"],
            "smoothed_distance": row["smoothed_distance_cm"],
            "timestamp": row["timestamp"],
        }
        for row in rows
    ]


def handle_incoming_event(payload: Dict[str, Any], topic: str) -> Dict[str, Any]:
    event = normalize_event(payload, topic)
    insert_event(event)
    socketio.emit("occupancy_update", event)
    return event


def on_connect(client: mqtt.Client, userdata: Any, flags: Dict[str, Any], rc: int) -> None:
    if rc == 0:
        print(f"Connected to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")
        for topic in MQTT_TOPICS:
            client.subscribe(topic)
    else:
        print(f"MQTT connection failed with result code {rc}")


def on_message(client: mqtt.Client, userdata: Any, message: mqtt.MQTTMessage) -> None:
    try:
        payload = json.loads(message.payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"Skipping malformed MQTT payload on {message.topic}: {exc}")
        return

    event = handle_incoming_event(payload, message.topic)
    print(f"Stored update for {event['table_id']} at {event['timestamp']}")


def start_mqtt_subscriber() -> mqtt.Client:
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(MQTT_BROKER, MQTT_PORT, MQTT_KEEPALIVE)
        client.loop_start()
    except OSError as exc:
        print(f"Could not connect to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}: {exc}")

    return client


@app.route("/", methods=["GET"])
def index() -> Any:
    return render_template("index.html")


@app.route("/api/current", methods=["GET"])
def get_current() -> Any:
    return jsonify(fetch_latest_state_by_table())


@socketio.on("connect")
def handle_socket_connect() -> None:
    emit("initial_state", fetch_latest_state_by_table())


if __name__ == "__main__":
    init_db()
    start_mqtt_subscriber()
    socketio.run(app, host="0.0.0.0", port=8080, debug=True)
