# run this separately to callibrate the sound threshold for grovepi sound sensor
import grovepi
import time

while True:
    print(grovepi.analogRead(0))
    time.sleep(0.5)