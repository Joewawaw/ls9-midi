#!../bin/python3
####################################################################################################
############################ MIDI Websockets client for remote mixers ##############################
#### - Usage:
####   > Run main program: run midi input listener + send to websockets server
####       midi_client_websockets.py [verbose]
####
#### - Description:
####   This code allows a front hall user to mix their own in-ear monitors using a usb midi keyboard
####   with CC (control change) knobs/faders. The usb midi device connects via USB to a raspberry pi
####   (or similar SFF SBC), and the pi connects to Wi-Fi. The pi via this code will create 
####   a websockets connection to this code and send over any 3-byte CC commands as 
####   a csv formatted string to the websockets port.
####
#### - pip Package Reference:
####     https://pypi.org/project/python-rtmidi/
####     https://pypi.org/project/websockets/
####     https://pypi.org/project/bidict/
####     https://pypi.org/project/click/
####
#### - Requirements:
####   This code requires a python venv with packages python-rtmidi & bidict installed.
####   Here are the steps
####       apt update
####       apt install python-venv -y
####       python3 -m venv ls9-midi
####       cd ls9-midi
####       git clone https://github.com/joewawaw/ls9-midi src
####       source bin/activate
####       pip install python-rtmidi bidict websockets click
####       cd src
####       ./midi_server_websockets.py
import asyncio
from websockets.sync.client import connect

def websockets_send():
    with connect("ws://localhost:8765") as websocket:
        websocket.send("Hello world!")

websockets_send()