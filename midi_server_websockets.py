#!../bin/python3
####################################################################################################
############################ MIDI Websockets server for remote mixers ##############################
#### - Usage:
####   > Run main program: run websockets listener + send to midi output
####       midi_server_websockets.py [verbose]
####
#### - Description:
####   This code allows a front hall user to mix their own in-ear monitors using a usb midi keyboard
####   with CC (control change) knobs/faders. The usb midi device connects via USB to a raspberry pi
####   (or similar SFF SBC), and the pi connects to Wi-Fi. the pi will create a websockets
####   connection to this code and send over any 3-byte CC commands as a csv formatted string
####   to the websockets port.
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

from websockets.asyncio.server import serve


async def handler(websocket):
    while True:
        message = await websocket.recv()
        print(message.split(','))


async def main():
    async with serve(handler, "", 8001):
        await asyncio.get_running_loop().create_future()  # run forever


if __name__ == "__main__":
    asyncio.run(main())