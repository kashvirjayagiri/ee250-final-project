from __future__ import annotations

import json
import os
import sqlite3
import threading
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

import paho.mqtt.client as mqtt
from flask import Flask, jsonify, render_template
from flask_socketio import SocketIO, emit


BASE_DIR = Path(__file__).parent.absolute()
DB_PATH = BASE_DIR / "occupancy.db"

MQTT_BROKER = os.getenv("MQTT_BROKER", "127.0.0.1") # flask mqtt broker
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPICS = ["brewview/+/status"]
MQTT_KEEPALIVE = 60

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "brewview-secret")
socketio = SocketIO(app, cors_allowed_origins="*")

db_lock = threading.Lock()


def utc_now() -> datetime:
    """Return the current timezone-aware UTC time."""
    return datetime.now(timezone.utc)


def parse_timestamp(raw_timestamp: Any) -> datetime:
    """Parse a timestamp from the RPi payload or fall back to the current time."""
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
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            return utc_now()

    return utc_now()


def parse_occupied(raw_occupied: Any) -> bool:
    """Normalize a truthy/falsy occupancy value from the payload."""
    if isinstance(raw_occupied, bool):
        return raw_occupied

    if isinstance(raw_occupied, (int, float)):
        return bool(raw_occupied)

    if isinstance(raw_occupied, str):
        return raw_occupied.strip().lower() in {"1", "true", "occupied", "yes", "on"}

    return False


def get_db_connection() -> sqlite3.Connection:
    """Create a SQLite connection with row access by column name."""
    connection = sqlite3.connect(DB_PATH, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    """Create the occupancy event table if it does not already exist."""
    with db_lock:
        connection = get_db_connection()
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS occupancy_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                table_id TEXT NOT NULL,
                occupied INTEGER NOT NULL,
                distance_cm REAL,
                sound REAL,
                timestamp TEXT NOT NULL
            )
            """
        )
        connection.commit()
        connection.close()


def normalize_event(payload: Dict[str, Any], topic: str) -> Dict[str, Any]:
    """Normalize an MQTT payload into the schema stored by the laptop server."""
    topic_parts = topic.split("/")
    topic_table_id = topic_parts[1] if len(topic_parts) >= 3 else "unknown"
    raw_occupied = payload.get("occupied", payload.get("status", False))

    timestamp = parse_timestamp(payload.get("timestamp"))

    event = {
        "table_id": str(payload.get("table_id", payload.get("table", topic_table_id))),
        "occupied": parse_occupied(raw_occupied),
        "distance_cm": payload.get("distance_cm"),
        "sound": payload.get("sound"),
        "timestamp": timestamp.isoformat(),
    }
    return event


def insert_event(event: Dict[str, Any]) -> None:
    """Insert a normalized occupancy event into SQLite."""
    with db_lock:
        connection = get_db_connection()
        connection.execute(
            """
            INSERT INTO occupancy_events (table_id, occupied, distance_cm, sound, timestamp)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                event["table_id"],
                int(event["occupied"]),
                event["distance_cm"],
                event["sound"],
                event["timestamp"],
            ),
        )
        connection.commit()
        connection.close()


def fetch_latest_state_by_table() -> List[Dict[str, Any]]:
    """Return the latest known state for each table."""
    with db_lock:
        connection = get_db_connection()
        rows = connection.execute(
            """
            SELECT table_id, occupied, distance_cm, sound, timestamp
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
            "sound": row["sound"],
            "timestamp": row["timestamp"],
        }
        for row in rows
    ]


def fetch_sound_history_last_30_minutes() -> List[Dict[str, Any]]:
    """Return sound readings recorded in the last 30 minutes."""
    cutoff = (utc_now() - timedelta(minutes=30)).isoformat()

    with db_lock:
        connection = get_db_connection()
        rows = connection.execute(
            """
            SELECT table_id, sound, occupied, distance_cm, timestamp
            FROM occupancy_events
            WHERE sound IS NOT NULL AND timestamp >= ?
            ORDER BY timestamp ASC
            """,
            (cutoff,),
        ).fetchall()
        connection.close()

    return [
        {
            "table_id": row["table_id"],
            "sound": row["sound"],
            "occupied": bool(row["occupied"]),
            "distance_cm": row["distance_cm"],
            "timestamp": row["timestamp"],
        }
        for row in rows
    ]


# ML pipeline removed for this project.
# def fetch_recent_events(hours: int = 24) -> List[sqlite3.Row]:
#     """Return recent events used by the lightweight prediction endpoint."""
#     cutoff = (utc_now() - timedelta(hours=hours)).isoformat()
#
#     with db_lock:
#         connection = get_db_connection()
#         rows = connection.execute(
#             """
#             SELECT table_id, occupied, sound, distance_cm, timestamp
#             FROM occupancy_events
#             WHERE timestamp >= ?
#             ORDER BY timestamp ASC
#             """,
#             (cutoff,),
#         ).fetchall()
#         connection.close()
#
#     return rows
#
#
# def build_next_6_hour_predictions() -> List[Dict[str, Any]]:
#     """
#     Build simple hour-by-hour predictions from recent data.
#
#     This acts as a lightweight baseline model until a separate trained model is
#     added to the project.
#     """
#     recent_rows = fetch_recent_events(hours=24)
#     latest_states = {row["table_id"]: row for row in fetch_latest_state_by_table()}
#     table_ids = sorted({row["table_id"] for row in recent_rows} | set(latest_states.keys()))
#
#     if not table_ids:
#         return []
#
#     occupancy_by_table_hour: Dict[str, Dict[int, List[int]]] = defaultdict(lambda: defaultdict(list))
#     sound_by_table_hour: Dict[str, Dict[int, List[float]]] = defaultdict(lambda: defaultdict(list))
#
#     for row in recent_rows:
#         timestamp = parse_timestamp(row["timestamp"])
#         occupancy_by_table_hour[row["table_id"]][timestamp.hour].append(int(row["occupied"]))
#         if row["sound"] is not None:
#             sound_by_table_hour[row["table_id"]][timestamp.hour].append(float(row["sound"]))
#
#     predictions: List[Dict[str, Any]] = []
#     current_time = utc_now().replace(minute=0, second=0, microsecond=0)
#
#     for hour_offset in range(1, 7):
#         prediction_time = current_time + timedelta(hours=hour_offset)
#         prediction_hour = prediction_time.hour
#
#         for table_id in table_ids:
#             latest_state = latest_states.get(table_id)
#             hour_occupancy = occupancy_by_table_hour[table_id].get(prediction_hour, [])
#             hour_sound = sound_by_table_hour[table_id].get(prediction_hour, [])
#
#             if hour_occupancy:
#                 occupancy_probability = sum(hour_occupancy) / len(hour_occupancy)
#             elif latest_state is not None:
#                 occupancy_probability = 1.0 if latest_state["occupied"] else 0.0
#             else:
#                 occupancy_probability = 0.0
#
#             if hour_sound:
#                 predicted_sound = sum(hour_sound) / len(hour_sound)
#             elif latest_state is not None and latest_state["sound"] is not None:
#                 predicted_sound = float(latest_state["sound"])
#             else:
#                 predicted_sound = 0.0
#
#             predictions.append(
#                 {
#                     "table_id": table_id,
#                     "timestamp": prediction_time.isoformat(),
#                     "occupied_probability": round(occupancy_probability, 3),
#                     "predicted_occupied": occupancy_probability >= 0.5,
#                     "predicted_sound": round(predicted_sound, 2),
#                 }
#             )
#
#     return predictions


def handle_incoming_event(payload: Dict[str, Any], topic: str) -> Dict[str, Any]:
    """Normalize, persist, and broadcast a new MQTT event."""
    event = normalize_event(payload, topic)
    insert_event(event)
    socketio.emit("occupancy_update", event)
    return event


def on_connect(client: mqtt.Client, userdata: Any, flags: Dict[str, Any], rc: int) -> None:
    """Subscribe to the RPi topic pattern after connecting to the broker."""
    if rc == 0:
        print(f"Connected to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")
        for topic in MQTT_TOPICS:
            client.subscribe(topic)
    else:
        print(f"MQTT connection failed with result code {rc}")


def on_message(client: mqtt.Client, userdata: Any, message: mqtt.MQTTMessage) -> None:
    """Process an incoming occupancy status event from the RPi."""
    try:
        payload = json.loads(message.payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"Skipping malformed MQTT payload on {message.topic}: {exc}")
        return

    event = handle_incoming_event(payload, message.topic)
    print(f"Stored update for {event['table_id']} at {event['timestamp']}")


def start_mqtt_subscriber() -> mqtt.Client:
    """Start the MQTT subscriber loop in the background."""
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
    """Serve the live cafe dashboard."""
    return render_template("index.html")


@app.route("/api/current", methods=["GET"])
def get_current() -> Any:
    """Return the most recent known state for each table."""
    return jsonify(fetch_latest_state_by_table())


@app.route("/api/sound_history", methods=["GET"])
def get_sound_history() -> Any:
    """Return sound sensor readings from the last 30 minutes."""
    return jsonify(fetch_sound_history_last_30_minutes())


# ML pipeline removed for this project.
# @app.route("/api/predict/next6", methods=["GET"])
# def get_next_6_predictions() -> Any:
#     """Return the next six hourly baseline occupancy predictions."""
#     return jsonify(build_next_6_hour_predictions())


@socketio.on("connect")
def handle_socket_connect() -> None:
    """Send the current state to newly connected dashboard clients."""
    emit("initial_state", fetch_latest_state_by_table())


if __name__ == "__main__":
    init_db()
    start_mqtt_subscriber()
    socketio.run(app, host="0.0.0.0", port=8080, debug=True)
