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
####   connection to this code and send over any 2-byte CC commands as a csv formatted string
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

## TODO:
## make class for midi incoming, and make into a file. common to all .py files.
## move timeout to a separate thread into the class, should not be visible on the main loop
## move async part of main loop to a specific nested? function that is declared as async, not the entire main block
## move is_, getters and send_nrpn into midi in out class
## make --ip flag in server code too
## make systemd service with proper description for all 3 codes (automations, foh mixer server, foh mixer client)
## in this websockets server code's pure form, process midi message should not exist here. in a
## class based setup, we can configure process_cc_messages to trigger based on a click flag
## make process_midi_messages a importable function from midi_yamaha_ls9.py. flip the values for process midi messages.
## move midi console into tools/test? folder
## unit tests!

import time
import logging
import traceback
import asyncio
import sys
from functools import partial

from bidict import bidict
import rtmidi
import click
from websockets.asyncio.server import serve

#my constants
import yamaha_ls9_constants as MIDI_LS9


def is_valid_nrpn_message(msg):
    if int(msg[0][1]) != MIDI_LS9.NRPN_BYTE_1 or int(msg[1][1]) != MIDI_LS9.NRPN_BYTE_2 or \
       int(msg[2][1]) != MIDI_LS9.NRPN_BYTE_3 or int(msg[3][1]) != MIDI_LS9.NRPN_BYTE_4:
        raise ValueError(f'Invalid NRPN MIDI data sequence! MIDI Message Dump: {msg}')
    return True

def is_on_off_operation(msg):
    # Since the bidict below contains all of the on/off channels, we can take message and check
    #   if it matches a value in the ON_OFF_CONTROLLERS mapping to find out if this
    #   message is an on/off operation.
    # We use inverse() as the mapping is <ch_name> -> <controller_number> (we want to find ch_name)
    if get_nrpn_ctlr(msg) in MIDI_LS9.ON_OFF_CTLRS.inverse:
        return True
    return False

def is_fade_operation(msg):
    if get_nrpn_ctlr(msg) in MIDI_LS9.FADER_CTLRS.inverse:
        return True
    return False

#returns a string corresponding to the channel (or mix/mt) of the message
def get_channel(msg):
    if is_fade_operation(msg):
        return MIDI_LS9.FADER_CTLRS.inv[get_nrpn_ctlr(msg)]

    if is_on_off_operation(msg):
        return MIDI_LS9.ON_OFF_CTLRS.inv[get_nrpn_ctlr(msg)]
    return None

#we need these in the midi message interpretation
def combine_bytes(msb, lsb):
    msb = int(msb); lsb = int(lsb)
    # & 0b1111111 to mask out the 8th bit (MIDI data is 7 bits)
    return ((msb & 0b1111111) << 7) | (lsb & 0b1111111)

#returns multiple values!
def split_bytes(combined):
    combined = int(combined)
    msb = (combined >> 7) & 0b1111111
    lsb = combined & 0b1111111
    return msb, lsb

#this returns the nrpn controller. this is passed through one of the bidicts to return a string
def get_nrpn_ctlr(msg):
    return combine_bytes(msg[0][2], msg[1][2])

#return midi NRPN data
def get_nrpn_data(msg):
    return combine_bytes(msg[2][2], msg[3][2])

#returns the state on the on/off button press, True = OFF->ON, False = ON->OFF
def get_on_off_data(msg):
    if not is_on_off_operation(msg):
        raise ValueError('Message is not an ON/OFF operation!')

    data = get_nrpn_data(msg)
    if data == MIDI_LS9.CH_OFF_VALUE:
        return False
    if data == MIDI_LS9.CH_ON_VALUE:
        return True

def send_nrpn(midi_output, controller, data):
    controller1, controller2 = split_bytes(controller)
    data1, data2 = split_bytes(data)

    midi_output.send_message([MIDI_LS9.CC_CMD_BYTE, MIDI_LS9.NRPN_BYTE_1,  controller1])
    midi_output.send_message([MIDI_LS9.CC_CMD_BYTE, MIDI_LS9.NRPN_BYTE_2,  controller2])
    midi_output.send_message([MIDI_LS9.CC_CMD_BYTE, MIDI_LS9.NRPN_BYTE_3,  data1])
    midi_output.send_message([MIDI_LS9.CC_CMD_BYTE, MIDI_LS9.NRPN_BYTE_4,  data2])

#these global vars holds the first 14 channel's on/off state (based on fader level)
#it is needed for fader muting/unmuting
channel_states = {
    'CH01': 'OFF',  'CH02': 'OFF',  'CH03': 'OFF',  'CH04': 'OFF',  'CH05': 'OFF',
    'CH06': 'OFF',  'CH07': 'OFF',  'CH08': 'OFF',  'CH09': 'OFF',  'CH10': 'OFF',
    'CH11': 'OFF',  'CH12': 'OFF',  'CH13': 'OFF',  'CH14': 'OFF'
}
wltbk_state = 'OFF'

# Process the 4 collected CC messages
def process_midi_messages(messages, midi_out):
    global channel_states
    global wltbk_state
    channel = get_channel(messages) #i.e. the NRPN controller
    # Processing for Fade operations
    if is_fade_operation(messages):
        data = get_nrpn_data(messages)
        # Mute the send of a vocal mic to MIX1,2 (for lead and chorus) if fader drops below -60dB
        # we also use the channel_states dict to keep track of which channels have already been
        # lowered (else we would have multiple triggers when the fader moves in b/w -inf to -60dB)
        if channel in MIDI_LS9.CHORUS_TO_LEAD_MAPPING:
            lead_ch = MIDI_LS9.CHORUS_TO_LEAD_MAPPING[channel]
            if data < MIDI_LS9.FADE_60DB_VALUE and channel_states[channel] == 'ON':
                channel_states[channel] = 'OFF'
                out_data = MIDI_LS9.FADE_0DB_VALUE
                logging.debug(f'MIXER IN: {channel} fade above -50dB')
                logging.info(f'MIDI OUT: {channel}, {lead_ch} Send to MIX1,2 @ 0 dB')
                send_nrpn(midi_out, MIDI_LS9.MIX1_SOF_CTLRS[channel], out_data)
                send_nrpn(midi_out, MIDI_LS9.MIX1_SOF_CTLRS[lead_ch], out_data)
            #fade back up to 0dB only if above -50dB, hence it is a software schmitt trigger
            elif data > MIDI_LS9.FADE_50DB_VALUE and channel_states[channel] == 'OFF':
                channel_states[channel] = 'ON'
                out_data = MIDI_LS9.FADE_NEGINF_VALUE
                logging.debug(f'MIXER IN: {channel} fade below -60dB')
                logging.info(f'MIDI OUT: {channel}, {lead_ch} Send to MIX1,2 @ -inf dB')
                send_nrpn(midi_out, MIDI_LS9.MIX1_SOF_CTLRS[channel], out_data)
                send_nrpn(midi_out, MIDI_LS9.MIX1_SOF_CTLRS[lead_ch], out_data)

#! this section is actually not needed
        elif channel in MIDI_LS9.WIRELESS_MC_TO_CHR_MAPPING and channel_states[channel] == 'ON':
            channel_states[channel] = 'OFF'
            wl_chr_ch =  MIDI_LS9.WIRELESS_MC_TO_CHR_MAPPING[channel]
            wl_lead_ch = MIDI_LS9.WIRELESS_MC_TO_LEAD_MAPPING[channel]
            if data < MIDI_LS9.FADE_60DB_VALUE:
                out_data = MIDI_LS9.FADE_NEGINF_VALUE
                logging.debug(f'MIXER IN: {channel} fade below -60dB')
                logging.info(f'MIDI OUT: {channel}, {wl_chr_ch}, {wl_lead_ch} Send to MIX1,2 @ -inf dB')
            elif data > MIDI_LS9.FADE_50DB_VALUE:
                out_data = MIDI_LS9.FADE_0DB_VALUE
                logging.debug(f'MIXER IN: {channel} fade above -50dB')
                logging.info(f'MIDI OUT: {channel}, {wl_chr_ch}, {wl_lead_ch} Send to MIX1,2 @ 0dB')
            send_nrpn(midi_out, MIDI_LS9.MIX1_SOF_CTLRS[channel],    out_data)
            send_nrpn(midi_out, MIDI_LS9.MIX1_SOF_CTLRS[wl_chr_ch],  out_data)
            send_nrpn(midi_out, MIDI_LS9.MIX1_SOF_CTLRS[wl_lead_ch], out_data)

    # Processing for ON/OFF message operations
    if is_on_off_operation(messages):
        data = get_on_off_data(messages)
        if data is True:
        #### Automation for CH01-CH10 switched ON/OFF (switch OFF/ON alt_channel)
            # if the channel is in the forward values of this mapping, it's one of the original channels
            if channel in MIDI_LS9.CHORUS_TO_LEAD_MAPPING:
                alt_channel = MIDI_LS9.CHORUS_TO_LEAD_MAPPING[channel]
                if data is True:
                    out_data = MIDI_LS9.CH_OFF_VALUE
                    logging.debug(f'MIXER IN: {channel} switched ON')
                    logging.info(f'MIDI OUT: {alt_channel} OFF')
                else:
                    out_data = MIDI_LS9.CH_ON_VALUE
                    logging.debug(f'MIXER IN: {channel} switched OFF')
                    logging.info(f'MIDI OUT: {alt_channel} ON')
                send_nrpn(midi_out, MIDI_LS9.ON_OFF_CTLRS[alt_channel], out_data)

            #if the channel is part of the inverse bidict, it is a duplicate channel (i.e. CH33-CH42)
            elif channel in MIDI_LS9.CHORUS_TO_LEAD_MAPPING.inv:
                alt_channel = MIDI_LS9.CHORUS_TO_LEAD_MAPPING.inv[channel]
                if data is True:
                    out_data = MIDI_LS9.CH_OFF_VALUE
                    logging.debug(f'MIXER IN: {channel} switched ON')
                    logging.info(f'MIDI OUT: {alt_channel} OFF')
                else:
                    out_data - MIDI_LS9.CH_ON_VALUE
                    logging.debug(f'MIXER IN: {channel} switched OFF')
                    logging.info(f'MIDI OUT: {alt_channel} ON')
                send_nrpn(midi_out, MIDI_LS9.ON_OFF_CTLRS[alt_channel], out_data)

        #### Automation for Wireless Mics switched ON/OFF
            elif channel in MIDI_LS9.WIRELESS_MC_TO_CHR_MAPPING:
                # If Wireless MC CH N switched ON, then turn off WLCHR N & LEADWL N
                if data is True:
                    #we disable toggling if wltbk_state is ON and the current channel is 13 or 14
                    if wltbk_state == 'OFF' or (wltbk_state=='ON' and channel!='CH13' and channel!='CH14'):
                        chr_channel =  MIDI_LS9.WIRELESS_MC_TO_CHR_MAPPING[channel]
                        lead_channel = MIDI_LS9.WIRELESS_MC_TO_LEAD_MAPPING[channel]
                        logging.info(f'MIDI OUT: {lead_channel} OFF & CH {chr_channel} OFF')
                        send_nrpn(midi_out, MIDI_LS9.ON_OFF_CTLRS[chr_channel],  MIDI_LS9.CH_OFF_VALUE)
                        send_nrpn(midi_out, MIDI_LS9.ON_OFF_CTLRS[lead_channel], MIDI_LS9.CH_OFF_VALUE)
                    #if a channel that is WLTBK is switched ON while in WLTBK mode,
                    # we need to turn it back off.
                    else:
                        send_nrpn(midi_out, MIDI_LS9.ON_OFF_CTLRS[channel],  MIDI_LS9.CH_OFF_VALUE)
                else:
                    chr_channel =  MIDI_LS9.WIRELESS_MC_TO_CHR_MAPPING[channel]
                    lead_channel = MIDI_LS9.WIRELESS_MC_TO_LEAD_MAPPING[channel]
                    logging.info(f'MIDI OUT: {chr_channel} ON & CH {lead_channel} OFF')
                    send_nrpn(midi_out, MIDI_LS9.ON_OFF_CTLRS[chr_channel],  MIDI_LS9.CH_ON_VALUE)
                    send_nrpn(midi_out, MIDI_LS9.ON_OFF_CTLRS[lead_channel], MIDI_LS9.CH_OFF_VALUE)

            elif channel in MIDI_LS9.WIRELESS_MC_TO_LEAD_MAPPING.inv:
                # If LEADWL CH N switched ON, then turn off WLCHR N & WLMC N
                if data is True:
                    if wltbk_state == 'OFF' or (wltbk_state=='ON' and channel!='CH45' and channel!='CH46'):
                        mc_channel =  MIDI_LS9.WIRELESS_MC_TO_LEAD_MAPPING.inv[channel]
                        chr_channel = MIDI_LS9.WIRELESS_CHR_TO_LEAD_MAPPING.inv[channel]
                        logging.info(f'MIDI OUT: {chr_channel} OFF & CH {mc_channel} OFF')
                        send_nrpn(midi_out, MIDI_LS9.ON_OFF_CTLRS[chr_channel], MIDI_LS9.CH_OFF_VALUE)
                        send_nrpn(midi_out, MIDI_LS9.ON_OFF_CTLRS[mc_channel],  MIDI_LS9.CH_OFF_VALUE)
                    else:
                        send_nrpn(midi_out, MIDI_LS9.ON_OFF_CTLRS[channel],  MIDI_LS9.CH_OFF_VALUE)
                else:
                    mc_channel =  MIDI_LS9.WIRELESS_MC_TO_LEAD_MAPPING.inv[channel]
                    chr_channel = MIDI_LS9.WIRELESS_CHR_TO_LEAD_MAPPING.inv[channel]
                    logging.info(f'MIDI OUT: {chr_channel} ON & CH {mc_channel} OFF')
                    send_nrpn(midi_out, MIDI_LS9.ON_OFF_CTLRS[chr_channel], MIDI_LS9.CH_ON_VALUE)
                    send_nrpn(midi_out, MIDI_LS9.ON_OFF_CTLRS[mc_channel],  MIDI_LS9.CH_OFF_VALUE)

            elif channel in MIDI_LS9.WIRELESS_CHR_TO_LEAD_MAPPING:
                # If WLCHR CH N switched ON, then turn off LEADWL N & WLMC N
                if data is True:
                    if wltbk_state == 'OFF' or (wltbk_state=='ON' and channel!='CH49' and channel!='CH50'):
                        mc_channel =   MIDI_LS9.WIRELESS_MC_TO_CHR_MAPPING.inv[channel]
                        lead_channel = MIDI_LS9.WIRELESS_CHR_TO_LEAD_MAPPING[channel]
                        logging.info(f'MIDI OUT: {mc_channel} OFF & CH {lead_channel} OFF')
                        send_nrpn(midi_out, MIDI_LS9.ON_OFF_CTLRS[mc_channel],   MIDI_LS9.CH_OFF_VALUE)
                        send_nrpn(midi_out, MIDI_LS9.ON_OFF_CTLRS[lead_channel], MIDI_LS9.CH_OFF_VALUE)
                    else:
                        send_nrpn(midi_out, MIDI_LS9.ON_OFF_CTLRS[channel],  MIDI_LS9.CH_OFF_VALUE)
                else:
                    mc_channel =   MIDI_LS9.WIRELESS_MC_TO_CHR_MAPPING.inv[channel]
                    lead_channel = MIDI_LS9.WIRELESS_CHR_TO_LEAD_MAPPING[channel]
                    logging.info(f'MIDI OUT: {lead_channel} ON & CH {mc_channel} OFF')
                    send_nrpn(midi_out, MIDI_LS9.ON_OFF_CTLRS[lead_channel], MIDI_LS9.CH_ON_VALUE)
                    send_nrpn(midi_out, MIDI_LS9.ON_OFF_CTLRS[mc_channel],   MIDI_LS9.CH_OFF_VALUE)

        #### Automation for MIX1 or MIX2 switched ON (switch ON ST LR)
            elif channel == 'MIX1' or channel == 'MIX2' and data is True:
                send_nrpn(midi_out, MIDI_LS9.ON_OFF_CTLRS['ST LR'], MIDI_LS9.CH_ON_VALUE)
        #### Automation for ST L/R switched OFF (switch OFF MIX1 as well)
            elif channel == 'ST LR' and data is False:
                send_nrpn(midi_out, MIDI_LS9.ON_OFF_CTLRS['MIX1'], MIDI_LS9.CH_OFF_VALUE)

        #### Automation for PC IN2 routing to BASMNT
            elif channel == 'ST-IN1':
                if data is True:
                    logging.info('MIDI OUT: PC IN2 -> BASMNT')
                    out_data_mix16 = MIDI_LS9.FADE_0DB_VALUE
                    out_data_mono =  MIDI_LS9.FADE_NEGINF_VALUE
                else:
                    logging.info('MIDI OUT: STREAM -> BASMNT')
                    out_data_mix16 = MIDI_LS9.FADE_NEGINF_VALUE
                    out_data_mono =  MIDI_LS9.FADE_0DB_VALUE
                send_nrpn(midi_out, MIDI_LS9.MIX16_SEND_TO_MT1, out_data_mix16)
                send_nrpn(midi_out, MIDI_LS9.MONO_SEND_TO_MT1,  out_data_mono)

        #### Automation for PC IN2 routing to LOBBY
            elif channel == 'ST-IN2':
                if data is True:
                    logging.info('MIDI OUT: PC IN2 -> LOBBY')
                    out_data_mix16 = MIDI_LS9.FADE_0DB_VALUE
                    out_data_stlr =  MIDI_LS9.FADE_NEGINF_VALUE
                else:
                    logging.info('MIDI OUT: ST L/R -> LOBBY')
                    out_data_mix16 = MIDI_LS9.FADE_NEGINF_VALUE
                    out_data_stlr =  MIDI_LS9.FADE_0DB_VALUE
                send_nrpn(midi_out, MIDI_LS9.MIX16_SEND_TO_MT2, MIDI_LS9.FADE_NEGINF_VALUE)
                send_nrpn(midi_out, MIDI_LS9.STLR_SEND_TO_MT2,  MIDI_LS9.FADE_0DB_VALUE)

        #### Automation for LOUNGE toggle between MONO and ST LR (ST-IN3 switched ON)
            elif channel == 'ST-IN3':
                # if ON, route MONO to LOUNGE
                if data is True:
                    logging.info('MIDI OUT: MONO -> LOUNGE')
                    out_data_mono = MIDI_LS9.FADE_0DB_VALUE
                    out_data_stlr = MIDI_LS9.FADE_NEGINF_VALUE
                # if OFF, route ST LR to LOUNGE
                else:
                    logging.info('MIDI OUT: ST L/R -> LOUNGE')
                    out_data_mono = MIDI_LS9.FADE_NEGINF_VALUE
                    out_data_stlr = MIDI_LS9.FADE_0DB_VALUE
                send_nrpn(midi_out, MIDI_LS9.MONO_SEND_TO_MT3,  out_data_mono)
                send_nrpn(midi_out, MIDI_LS9.ST_LR_SEND_TO_MT3, out_data_stlr)

        #### Automation for toggling WLTBK 3 & 4 ON/OFF
            elif channel == 'ST-IN4':
                if data is True:
                    logging.info('MIDI OUT: WLTBK3 & WLTBK4 ON')
                    wltbk_state = 'ON' # we need this global var to disable WL MC/CHR/LEAD toggling
                    out_data_ch13 = MIDI_LS9.CH_OFF_VALUE
                    out_data_ch14 = MIDI_LS9.CH_OFF_VALUE
                else:
                    logging.info('MIDI OUT: WLTBK3 & WLTBK4 OFF')
                    wltbk_state = 'OFF'
                    #turn on only MC channels (and turn off all alt channels below)
                    out_data_ch13 = MIDI_LS9.CH_ON_VALUE
                    out_data_ch14 = MIDI_LS9.CH_ON_VALUE

                send_nrpn(midi_out, MIDI_LS9.ON_OFF_CTLRS['CH13'], out_data_ch13)
                send_nrpn(midi_out, MIDI_LS9.ON_OFF_CTLRS['CH14'], out_data_ch14)
                #turn off all alt channels for wireless mics 3 & 4; as they all route to ST L/R
                send_nrpn(midi_out, MIDI_LS9.ON_OFF_CTLRS['CH46'], MIDI_LS9.CH_OFF_VALUE)
                send_nrpn(midi_out, MIDI_LS9.ON_OFF_CTLRS['CH47'], MIDI_LS9.CH_OFF_VALUE)
                send_nrpn(midi_out, MIDI_LS9.ON_OFF_CTLRS['CH49'], MIDI_LS9.CH_OFF_VALUE)
                send_nrpn(midi_out, MIDI_LS9.ON_OFF_CTLRS['CH50'], MIDI_LS9.CH_OFF_VALUE)


# this is a small tool to echo any NRPN-formatted CC commands
async def midi_console(midi_port, console):
    midi_nrpn_console_messages = []
    # using a list because lists are mutable, and so their values will change in the parent function
    # if changed in a child function.
    timeout_counter = [0]
    def midi_nrpn_callback(event, unused):
        message, timestamp = event

        if message[0] == MIDI_LS9.CC_CMD_BYTE:
            midi_nrpn_console_messages.append(message)
        if len(midi_nrpn_console_messages) == 4:
            controller = get_nrpn_ctlr(midi_nrpn_console_messages)
            data =       get_nrpn_data(midi_nrpn_console_messages)
            logging.info(f'NRPN Message    Controller  {hex(controller)}\tData  {hex(data)}')
            midi_nrpn_console_messages.clear()
            timeout_counter[0] = 0

    def midi_cc_callback(event, unused):
        message, timestamp = event
        if message[0] == MIDI_LS9.CC_CMD_BYTE:
            logging.info(f'CC Message    {message[0]}\t{message[1]}\t{message[2]}')
            timeout_counter[0] = 0

    logging.basicConfig(format='%(asctime)s %(message)s', level=logging.INFO)
    midi_in = rtmidi.MidiIn()
    midi_in.open_port(midi_port)

    if console == 'CC':
        logging.info('MIDI CC Console. Echoing all incoming MIDI CC messages (3 byte packets)')
        logging.info('Press CTRL+C to exit')
        midi_in.set_callback(midi_cc_callback)
    elif console == 'NRPN':
        logging.info('MIDI NRPN Console. Echoing all incoming MIDI NRPN messages (controller+data)')
        logging.info('Press CTRL+C to exit')
        midi_in.set_callback(midi_nrpn_callback)

    try:
        while True:
            await asyncio.sleep(0.05)
            timeout_counter[0] += 1
            # every 1s print a blank line
            if timeout_counter[0] == 20:
                print()
                timeout_counter[0] = 0
            #if timeout_counter overflows, check if input buffer data is incomplete (>0, <4) & reset
            #timeout is set to 250ms
            if timeout_counter[0] > 5:
                if len(midi_nrpn_console_messages) > 0 and len(midi_nrpn_console_messages) < 4:
                    logging.warning(f'Timeout on midi input buffer! data: {midi_nrpn_console_messages}')
                    midi_nrpn_console_messages.clear()
                    timeout_counter[0] = 0
    except KeyboardInterrupt:
        print('Exiting...')
    finally:
        midi_in.close_port()
        sys.exit()


async def websocket_listener(websocket, arg1):
    async for message in websocket:
        cc_controller, cc_data = message.split(',')
        logging.debug(f'{cc_controller=}\t{cc_data=}')
        # we assume casting wont fail
        cc_controller = int(cc_controller)
        cc_data = int(cc_data)
        data = int((cc_data / 127.0) * MIDI_LS9.FADE_10DB_VALUE)
        #get the right MT SoF controller by checking which bidict cc_controller is an element
        if cc_controller in MIDI_LS9.USB_MIDI_MT5_SOF_CC_CTLRS:
            mix_name = MIDI_LS9.USB_MIDI_MT5_SOF_CC_CTLRS[cc_controller]
            if mix_name == 'MT5':
                controller = MIDI_LS9.FADER_CTLRS['MT5']
            else:
                controller = MIDI_LS9.MT5_SOF_CTRLS[mix_name]
            logging.info(f'MIDI OUT: {mix_name} Send to MT5 @ {hex(data)} dB')
            send_nrpn(arg1, controller, data)
        elif cc_controller in MIDI_LS9.USB_MIDI_MT6_SOF_CC_CTLRS:
            mix_name = MIDI_LS9.USB_MIDI_MT6_SOF_CC_CTLRS[cc_controller]
            if mix_name == 'MT6':
                controller = MIDI_LS9.FADER_CTLRS['MT6']
            else:
                controller = MIDI_LS9.MT6_SOF_CTRLS[mix_name]
            logging.info(f'MIDI OUT: {mix_name} Send to MT6 @ {hex(data)} dB')
            send_nrpn(arg1, controller, data)
        else:
            logging.error(f'The CC command received from USB keyboard is invalid! {cc_controller=}')

# Click wrapper for the async main function
@click.command()
@click.option('-v', '--verbose', is_flag=True, default=False, help='Set logging level to DEBUG')
@click.option('-c', '--console', default=None, type=click.Choice(['CC', 'NRPN'], case_sensitive=False), help='Run in console mode')
@click.option('-p', '--port', default=0, metavar='PORT', show_default=True, type=int, help='Specify MIDI port number')
def main(port, console, verbose):
    asyncio.run(async_main(port, console, verbose))

async def async_main(port, console, verbose):
    #if the console flag was passed, run one of the mini-tools instead of the main program (automations)
    if console is not None:
        await midi_console(port, console)
        return

    if verbose is True:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO

    #set the logger of websockets to warning only to avoid noise
    logger = logging.getLogger('websockets')
    logger.setLevel(logging.WARNING)

    # time is given in ISO8601 date format
    logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', level=log_level)
    logging.info('MIDI LS9 Automations. Waiting for incoming MIDI NRPN messages...')

    # Setup the MIDI input & output
    midi_in =  rtmidi.MidiIn()
    midi_in.open_port(port)
    midi_out = rtmidi.MidiOut()
    midi_out.open_port(port)

    midi_messages = []
    timeout_counter = [0]
    def main_midi_callback(event, unused):
        messages, timestamp = event
        # Filter out everything but CC (Control Change) commands
        if messages[0] == MIDI_LS9.CC_CMD_BYTE:
            midi_messages.append(messages)
            logging.debug(f'Received CC command {messages}')
        # Once we have 4 CC messages, process them
        if len(midi_messages) == 4:
            try:
                process_midi_messages(midi_messages, midi_out)
            # we will catch all exceptions to make this system a big more rugged.
            except Exception as e:
                error_message = traceback.format_exc()
                logging.error(error_message)
                logging.error(str(e))
            finally:
                midi_messages.clear()  # Clear the list for the next batch of 4 messages
                timeout_counter[0] = 0

    #set_callback needs to be after the function above, and the callback function needs to know
    # about midi_out, so place it here in the code.
    midi_in.set_callback(main_midi_callback)

    while True:
        try:
            #start websocket listener and attach callback websocket_listener() to serve()
            listener_with_args = partial(websocket_listener, arg1=midi_out)
            async with serve(listener_with_args, "localhost", 8001):
                await asyncio.get_running_loop().create_future()  # run forever

            #delay is necessary to not overload the CPU or RAM
            await asyncio.sleep(0.005)
            # if there is an incomplete packet in the buffer, increase the timeout
            if len(midi_messages) > 0:
                timeout_counter[0] += 1
            #if counter exceeds 0.005 * 20 = 100ms
            if timeout_counter[0] > 20:
                midi_messages.clear()
                timeout_counter[0] = 0
                logging.warning('Timeout! Resetting MIDI input buffer')
        except KeyboardInterrupt:
            logging.warning('CTRL+C pressed. Exiting...')
            midi_in.close_port()
            midi_out.close_port()
            sys.exit()

if __name__ == '__main__':
    main()
