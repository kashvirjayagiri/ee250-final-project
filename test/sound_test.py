import grovepi
import time
import RPi.GPIO as GPIO

# CONFIG (CHANGE IF NEEDED)
TRIG = 23
ECHO = 24
SOUND_PORT = 0   # Grove analog port

# GPIO SETUP
GPIO.setmode(GPIO.BCM)
GPIO.setup(TRIG, GPIO.OUT)
GPIO.setup(ECHO, GPIO.IN)
GPIO.output(TRIG, False)

time.sleep(1)

# DISTANCE FUNCTION
def get_distance():
    # ensure clean LOW pulse
    GPIO.output(TRIG, False)
    time.sleep(0.0002)

    # trigger pulse
    GPIO.output(TRIG, True)
    time.sleep(0.00001)
    GPIO.output(TRIG, False)

    # wait for echo HIGH
    timeout_start = time.time()
    while GPIO.input(ECHO) == 0:
        if time.time() - timeout_start > 0.04:
            return None
    pulse_start = time.time()

    # wait for echo LOW
    while GPIO.input(ECHO) == 1:
        if time.time() - pulse_start > 0.04:
            return None
    pulse_end = time.time()

    # calculate distance
    duration = pulse_end - pulse_start
    distance = (duration * 34300) / 2
    return round(distance, 1)


# MAIN LOOP
readings = []

try:
    print("Sensor calibration")
    print("Move your hand / sit / leave empty to observe values\n")

    while True:
        dist = get_distance()
        sound = grovepi.analogRead(SOUND_PORT)

        # rolling average for distance
        if dist is not None:
            readings.append(dist)
            if len(readings) > 5:
                readings.pop(0)
            avg_dist = sum(readings) / len(readings)
        else:
            avg_dist = None

        # print nicely
        print("----------------------------")
        print(f"Distance (raw): {dist} cm")
        print(f"Distance (avg): {round(avg_dist,2) if avg_dist else 'N/A'} cm")
        print(f"Sound level   : {sound}")

        time.sleep(0.2)

except KeyboardInterrupt:
    print("\nStopping...")
    GPIO.cleanup()