#!/usr/local/bin/python3

import json
import time
import logging
import sys
import select

debuggging = False

#######################################################################

import pyaudio
import wave
import struct
import math
import numpy

CHUNK           = 4096
FORMAT          = pyaudio.paInt16
CHANNELS        = 2
RATE            = 44100
SHORT_NORMALIZE = (1.0/32768.0)
RECORD_SECONDS  = 20

#######################################################################

from phue import Bridge

red_lo = 0
red_hi = 65535
green  = 21845
yellow = 10000
blue   = 43690

#######################################################################

def get_bridge():
    # Disable annoying output from phue library
    logger = logging.getLogger('phue')
    logger.setLevel(logging.CRITICAL)

    # Get the Bridge IP address from the Hue cloud (cool!)
    first = Bridge()
    ip = first.get_ip_address()

    # Connect to the bridge
    bridge = Bridge(ip)

    return bridge

def load_lights(bridge):
    lights = bridge.lights
    for light in lights:
        light.transitiontime = 1
        light.brighness = 255
        light.on = False

    return lights

def hue_add(hue, val):
    h = (int(hue) + val) % 65535
    return str(h)

def back_n_forth(bridge, lights, num_times):
    for l in lights:
        l.transitiontime = 5

    rev_lights = lights[::-1]

    hue = 0
    for i in range(num_times):
        for l in lights:
            l.on = True
            l.hue = hue
            l.sat = 255
            l.brightness = 255
            time.sleep(0.3)
            l.on = False

            hue = hue_add(hue, 1500)

        for l in rev_lights:
            l.on = True
            l.hue = hue
            l.sat = 255
            l.brightness = 255
            time.sleep(0.3)
            l.on = False

            hue = hue_add(hue, 1500)

        # If the user hits a key, we're done
        if select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], []):
            _ = sys.stdin.read(1)
            return

def all_blink(bridge, lights, hue, num_times,
              light_time=0.3, dark_time=0.4):
    for l in lights:
        l.transitiontime = 1

    first = True
    for i in range(num_times):
        for l in lights:
            l.on = True
            if first:
                l.brightness = 255
                l.hue = hue
        time.sleep(light_time)

        for l in lights:
            l.on = False
        time.sleep(dark_time)

        first = False

def blink_one(bridge, light, hue, num_times,
              light_time=0.3, dark_time=0.4):
    light.transitiontime = 1

    for i in range(num_times):
        light.on = True
        light.brightness = 255
        light.hue = hue
        time.sleep(light_time)

        light.on = False
        time.sleep(dark_time)

def fast_blink_one(bridge, light, hue, num_times):
    blink_one(bridge=bridge, light=light, hue=hue, num_times=num_times,
              light_time=0.1, dark_time=0.2)

def slow_blink_one(bridge, light, hue, num_times):
    blink_one(bridge=bridge, light=light, hue=hue, num_times=num_times,
              light_time=0.5, dark_time=0.4)

#######################################################################

def root_mean_square(block):
    d = numpy.frombuffer(block, numpy.int16).astype(numpy.float)
    rms = numpy.sqrt((d*d).sum()/len(d))
    return rms

# Open the microphone audio stream
def open_stream(pya):
    stream = pya.open(format=FORMAT,
                      channels=CHANNELS,
                      rate=RATE,
                      input=True,
                      frames_per_buffer=CHUNK)
    return stream

#---------------------------------------------------------------------

# At Career Day, I saw a max of about 22K RMS
max_rms_value = 22000
hue_range = red_hi - green
bright_range = 253

def color_me(rms):
    # Range from green to red_hi
    # Brightness from 1 to 254

    fraction_of_max = min(1, rms / max_rms_value)

    hue = green + int(hue_range * fraction_of_max)
    brightness = 1 + int(bright_range * fraction_of_max)

    return hue, brightness

#######################################################################

def player(bridge, light, num):
    print('')
    print('--------------------------------------------------------------')
    input("Player {num}: hit ENTER when ready: ".format(num=num))
    print('')

    seconds = 5
    print("Ready...")
    slow_blink_one(bridge, light, hue=green, num_times=1)
    print("Set...")
    slow_blink_one(bridge, light, hue=green, num_times=1)
    print("Wait for it...")
    time.sleep(2)
    print('')
    print("GO")

    light.transitiontime = 1
    light.on = True
    light.hue = red_lo
    light.brightness = 1

    pya = pyaudio.PyAudio()
    stream = open_stream(pya)

    max_rms = -9999999
    for i in range(int(RATE / CHUNK * seconds)):
        try:
            audio_data = stream.read(CHUNK)
            rms = root_mean_square(audio_data)

            if rms > max_rms:
                max_rms = rms
                if debugging:
                    print("New max: {}".format(max_rms))

            hue, bright = color_me(rms)
            light.hue = hue
            light.brightness = bright
            if debugging:
                print("RMS={r}, Hue={h}, bright={b}"
                      .format(r=rms, h=hue, b=bright))
        except:
            stream = open_stream(pya)

    m = int(max_rms)
    print("STOP!\n")
    print("Maximum sound volume: {max}".format(max=m))

    return m

def player_off(light):
    light.hue = red_lo
    light.brigtness = 1
    light.on = False

def main():
    bridge = get_bridge()
    lights = load_lights(bridge)

    # Time delay
    print('')
    print("Hit ENTER to start")
    back_n_forth(bridge, lights, num_times=999999)
    all_blink(bridge, lights, red_lo, num_times=3,
              light_time=0.1, dark_time=0.2)

    player1_light = lights[0]
    player2_light = lights[3]

    max1 = player(bridge, player1_light, 1)
    player_off(player1_light)

    max2 = player(bridge, player2_light, 2)
    player_off(player2_light)

    if max1 > max2:
        print('Player 1 is the winner!')
        fast_blink_one(bridge, player1_light, yellow, num_times=20)
    elif max2 > max1:
        print('Player 2 is the winner!')
        fast_blink_one(bridge, player2_light, yellow, num_times=20)
    else:
        print('Player 1 and player 2 tied!')
        all_blink(bridge, lights, yellow, num_times=20,
                  light_time=0.1, dark_time=0.2)

    print('')
    print("Thanks for playing!")
    print('')

# Run the game!
main()
