import RPi.GPIO as GPIO
import time

TRIG = 23
ECHO = 24

GPIO.setmode(GPIO.BCM)
GPIO.setup(TRIG, GPIO.OUT)
GPIO.setup(ECHO, GPIO.IN)
GPIO.output(TRIG, False)
time.sleep(2)

def get_distance():
    GPIO.output(TRIG, True)
    time.sleep(0.00001)
    GPIO.output(TRIG, False)

    while GPIO.input(ECHO) == 0:
        pass
    start = time.time()
    while GPIO.input(ECHO) == 1:
        pass
    end = time.time()

    return round((end - start) * 34300 / 2, 1)

try:
    while True:
        print(get_distance())
        time.sleep(0.5)

except KeyboardInterrupt:
    GPIO.cleanup()