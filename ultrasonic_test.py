# import RPi.GPIO as GPIO
# import time

# TRIG = 23
# ECHO = 24

# GPIO.setmode(GPIO.BCM)
# GPIO.setup(TRIG, GPIO.OUT)
# GPIO.setup(ECHO, GPIO.IN)
# GPIO.output(TRIG, False)
# time.sleep(2)

# def get_distance():
#     GPIO.output(TRIG, True)
#     time.sleep(0.00001)
#     GPIO.output(TRIG, False)

#     while GPIO.input(ECHO) == 0:
#         pass
#     start = time.time()
#     while GPIO.input(ECHO) == 1:
#         pass
#     end = time.time()

#     return round((end - start) * 34300 / 2, 1)

# try:
#     while True:
#         print(get_distance())
#         time.sleep(0.5)

# except KeyboardInterrupt:
#     GPIO.cleanup()
    
# ultrasonic test old
import sys
sys.path.append('~/Dexter/GrovePi/Software/Python')
import time
import grovepi

# Grove Ultrasonic Ranger connectd to digital port 2
ultrasonic_ranger = 2

while True:
  try:
    # TODO:read distance value from Ultrasonic Ranger and print distance on LCD
    dist = int(grovepi.ultrasonicRead(ultrasonic_ranger))
    print (dist)
    # setText_norefresh(f'\n{dist}cm')

  except IOError:
    print("Error")
