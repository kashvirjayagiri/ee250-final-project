**BrewView: Real-Time Cafe Occupancy Detection System**

Team Members:   
Irene Kim  
Kashvi Jayagiri

**PROJECT OVERVIEW**

BrewView is a two-node IoT system that detects cafe table occupancy in real time using a Grove Ultrasonic Ranger and a Potentiometer. The Raspberry Pi acts as the IoT edge node, running the sensor node and edge processing service. The laptop acts as the central analytics server, running the Flask backend and serving the live web dashboard.

**SYSTEM REQUIREMENTS**

Raspberry Pi

* Raspberry Pi (any model with WiFi, we used Model 4\)  
* GrovePi Shield seated on the 40-pin GPIO header  
* Grove Ultrasonic Ranger plugged into GrovePi digital port D4  
* Grove Potentiometer plugged into GrovePi analog port A0  
* Mosquitto MQTT broker  
* Python 3

Laptop

* Python 3  
* Libraries installed: paho-mqtt, Flask, Flask SocketIO

Must be on the same WiFi network as the Raspberry Pi

**HARDWARE WIRING**

*  Grove Ultrasonic Ranger → GrovePi shield port D4 (Grove cable)  
*  Grove Potentiometer → GrovePi shield port A0 (Grove cable)  
*  GrovePi shield → Seated on RPi 40-pin GPIO header

**INSTALLATION**

On the Raspberry Pi (from MQTT lab)  
1\. Install Mosquitto broker:  
       sudo apt install \-y mosquitto mosquitto-clients

2\. Configure Mosquitto to accept external connections:  
       sudo nano /etc/mosquitto/mosquitto.conf

     Add these two lines at the end of the file:  
       listener 1883  
       allow\_anonymous true

3\. Restart Mosquitto:  
       sudo systemctl restart mosquitto

4\. Enable Mosquitto to start on boot:  
       sudo systemctl enable mosquitto.service

5\. Install Python dependencies:  
       pip3 install paho-mqtt grovepi typing\_extensions

6\. Note your RPi IP address (needed for laptop setup):  
       hostname \-I

On the Laptop  
1\. Go into the directory containing your project and create and activate a virtual environment:  
       cd \<location\>  
       python3 \-m venv .venv  
       *MacOS/Linux:* source .venv/bin/activate             
       *Windows:* venv\\Scripts\\activate        

2\. Install Python dependencies:  
       pip install flask flask-socketio paho-mqtt

3\. Open server.py and set MQTT\_BROKER to your RPi IP address:  
       MQTT\_BROKER \= "RPI\_IP"    \# replace with RPi IP from step 6 above

**HOW TO RUN**

Step 1: On your laptop open four separate terminals:

Terminal 1: verify broker is running  
sudo systemctl status mosquitto

If its not running, start the broker  
sudo systemctl start mosquitto

Terminal 2: start the edge processing service in a virtual environment  
python3 edge\_processor.py

Terminal 3: SSH into your RPI and start the sensor node  
python3 sensor\_node.py \--table\_id table\_1 –broker \<LAPTOP\_IP\>

Terminal 4: start the server in a virtual environment  
python3 server.py

You should see distance and threshold readings printing every 2 seconds  
In Terminal 3, and occupancy state updates printing in Terminal 2\.

Step 2: Open a browser and navigate to:  
    [http://localhost:8080](http://localhost:8080) 

**EXTERNAL LIBRARIES**

**Raspberry Pi**

| paho-mqtt | MQTT client for publishing and subscribing |
| :---- | :---- |
|   grovepi | GrovePi sensor library for reading Grove sensors |
| typing\_extensions | Just an updated version of a standard python library that we used to solve an error |

**Laptop**

| flask |  Web framework for the analytics server |
| :---: | :---- |
| flask-socketio |  WebSocket support for live dashboard updates |
| paho-mqtt |  MQTT client for subscribing to RPi broker |

**FILES**

| sensor\_node.py | Sensor node service (reads ultrasonic ranger and potentiometer, publishes raw readings to RPi broker every 2 seconds via MQTT) |
| :---: | ----- |
| edge\_processor.py |  Edge processing service (subscribes to raw readings, applies hysteresis threshold and holdover timer logic, publishes processed occupancy events to RPi broker) |
| server.py | Central analytics server (subscribes to processed events from RPi broker, stores events in SQLite database, serves REST API and live web dashboard) |
| templates/index.html | Web dashboard (displays live floor map, occupancy metrics, and threshold readings via WebSocket updates) |

