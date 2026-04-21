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