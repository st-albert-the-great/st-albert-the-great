#!/usr/bin/Python

from Foundation import *
import AppKit
import sys

class SRDelegate(NSObject):
    def speechRecognizer_didRecognizeCommand_(self,sender,cmd):
        print("I heard and understood: {}".format(cmd))
        if 'quit' in cmd.lower():
            sys.exit()

################################################################

recog = AppKit.NSSpeechRecognizer.alloc().init()
recog.setCommands_( [
        "Saint Albert the Great",
        "Today is career day",
        "Quit"])

recog.setListensInForegroundOnly_(False)
d = SRDelegate.alloc().init()
recog.setDelegate_(d)

print("\nI am listening!\n")
recog.startListening()

runLoop = NSRunLoop.currentRunLoop()
runLoop.run()
