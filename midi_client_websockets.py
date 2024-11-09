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
import time
import logging
import traceback
import asyncio
import sys
from functools import partial

from bidict import bidict
import rtmidi
import click
from websockets.sync.client import connect

#my constants
import yamaha_ls9_constants as MIDI_LS9

WEBSOCKET_IP = 'localhost'
WEBSOCKET_PORT = '8001'

def websockets_send(controller, data):
    with connect(f'ws://{WEBSOCKET_IP}:{WEBSOCKET_PORT}') as websocket:
        websocket.send(f'{int(controller)},{int(data)}')

# Click wrapper for the async main function
@click.command()
@click.option('-v', '--verbose', is_flag=True, default=False, help='Set logging level to DEBUG')
@click.option('-p', '--port', default=0, metavar='PORT', show_default=True, type=int, help='Specify MIDI port number')
def main(port, verbose):
    asyncio.run(async_main(port, verbose))

async def async_main(midi_port, verbose):
    def midi_cc_callback(event, unused):
        message, timestamp = event
        if message[0] == MIDI_LS9.CC_CMD_BYTE:
            logging.debug(f'CC Message    {message[0]}\t{message[1]}\t{message[2]}')
            logging.debug(f'Websocket Send "{message[1]},{message[2]}" to {WEBSOCKET_IP}:{WEBSOCKET_PORT}')
            websockets_send(message[1], message[2])

    if verbose:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO
    logging.basicConfig(format='%(asctime)s %(message)s', level=log_level)
    logging.info('MIDI USB Keyboard to websockets Client')
    logging.info('Press CTRL+C to exit')

    midi_in = rtmidi.MidiIn()
    midi_in.open_port(midi_port)
    midi_in.set_callback(midi_cc_callback)

    try:
        while True:
            await asyncio.sleep(0.05)
    except KeyboardInterrupt:
        print('Exiting...')
    finally:
        midi_in.close_port()
        sys.exit()

if __name__ == '__main__':
    main()
