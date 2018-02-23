#!/usr/bin/Python

from Foundation import *
import AppKit
import sys
import random

from phue import Bridge

red    = 65535
green  = 21845
yellow = 10000
blue   = 43690
colors = [ red, green, yellow, blue ]

################################################################

class SRDelegate(NSObject):
    def speechRecognizer_didRecognizeCommand_(self,sender,cmd):
        print("I heard and understood: {}".format(cmd))

        if cmd == 'Turn on all lights':
            set_light(1,  "on")
            set_light(2, "on")
            set_light(3, "on")
            set_light(4, "on")
        elif cmd == 'Turn off all lights' or 'quit' in cmd.lower():
            set_light(1, "off")
            set_light(2, "off")
            set_light(3, "off")
            set_light(4, "off")

            if 'quit' in cmd.lower():
                sys.exit()

        elif cmd == 'Turn on light 1':
            set_light(1,  "on")
        elif cmd == 'Turn on light 2':
            set_light(2,  "on")
        elif cmd == 'Turn on light 3':
            set_light(3,  "on")
        elif cmd == 'Turn on light 4':
            set_light(4,  "on")

        elif cmd == 'Turn off light 1':
            set_light(1,  "off")
        elif cmd == 'Turn off light 2':
            set_light(2,  "off")
        elif cmd == 'Turn off light 3':
            set_light(3,  "off")
        elif cmd == 'Turn off light 4':
            set_light(4,  "off")

################################################################

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
        light.transitiontime = 3
        light.brighness = 255
        light.on = False

    return lights

def set_light(which, state):
    print("Turning {state} {which} light"
          .format(state = state, which = which))

    if state == 'on':
        lights[which].on = True
        lights.hue        = random.randomselection(colors)
        lights.brightness = 255

    elif state == 'off':
        lights[which].on = False

bridge = get_bridge()
lights = load_lights(bridge)

################################################################

recog = AppKit.NSSpeechRecognizer.alloc().init()
recog.setCommands_( [
    "Turn on lights",
    "Turn off lights",

    "Turn on light 1",
    "Turn on light 2",
    "Turn on light 3",
    "Turn on light 4",

    "Turn off light 1",
    "Turn off light 2",
    "Turn off light 3",
    "Turn off light 4",

    "Quit"])

recog.setListensInForegroundOnly_(False)
d = SRDelegate.alloc().init()
recog.setDelegate_(d)

print("\nI am listening!\n")
recog.startListening()

runLoop = NSRunLoop.currentRunLoop()
runLoop.run()
