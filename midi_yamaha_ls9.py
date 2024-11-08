#!../bin/python3
####################################################################################################
############################ MIDI Automation for Yamaha LS9-32 Mixer ###############################
#### - Usage:
####   > Run main program: run automations
####       midi_yamaha_ls9.py [verbose]
####   > Run in console mode: program will echo any NRPN msgs received with controller+data values
####       midi_yamaha_ls9.py console
####
#### - Description:
####   This code automates some functions in the Yamaha LS-9 Mixer for the Ottawa Sai Centre
####   Here are the automations
####       1. CHR<->WL ON/OFF toggling.
####            When a CHR ch is turned ON/OFF, its LEAD ch will toggle the opposite state
####       2. WLMC<->WLCHR<->LEADWL swapping.
####            Wireless Mics can be swapped between an M.C. role, a chorus role, or a lead role
####       3. Monitor Mute vocal mic on fader drop to -inf.
####            When the fader for CH01-10 (i.e. vocals) drops below -60 dB the send
####            of that channel to MIX1/2 will drop to -inf. when it is raised back above
####            -40dB the send to MIX1/2 will go to 0 dB
####       4. The musician monitors exist in the following states (theres 4 when you consider mains)
####            Mains ON  | Musician ON:  Yes
####            Mains ON  | Musician OFF: Yes (PC IN, USB, PC IN2 playback)
####            Mains OFF | Musician ON:  No
####            Mains OFF | Musician OFF: Yes
####            And so, to prevent the case of Mains OFF / Musician ON,
####            we turn OFF MONITR when ST LR is pressed OFF
####            and we turn ON ST LR when MONITR is pressed ON (it may already be on, that is fine)
####
#### - pip Package Reference:
####     https://pypi.org/project/python-rtmidi/
####     https://pypi.org/project/bidict/
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
####       pip install python-rtmidi bidict
####       cd src
####       ./midi_yamaha_ls9.py
#### - Run on Startup (install as a systemd service):
####       Copy exactly what is inside of the ''' quotation marks into a terminal
'''
cat <<EOF > /etc/systemd/system/midi_ls9.service
# systemd Service for Yamaha LS9 automations using MIDI (python)
[Unit]
Description=midi_ls9.service
#AssertPathExists=
After=multi-user.target

[Service]
Type=simple
ExecStart=python3 /root/midi_ls9/src/midi_yamaha_ls9.py
Restart=on-failure
RestartSec=3
User=root

[Install]
WantedBy=multi-user.target
EOF
systemctl enable midi_ls9.service
systemctl start  midi_ls9.service
'''
####################################################################################################
####   TO DO:
# - unit tests!
#     assert all is_ statements
#     assert channel out of bounds
#     assert simple midi cc filter
#     assert invalid nrpn message
#     assert rx buffer timeout
####################################################################################################
# NPRN message structure for Yamaha LS9 (messages are 7 bits):
# CC cmd #   Byte 1   Byte 2   Byte 3
#        1   0xB0     0x62     <CONTROLLER[0]>
#        2   0xB0     0x63     <CONTROLLER[1]>
#        3   0xB0     0x06     <DATA[0]>
#        4   0xB0     0x26     <DATA[1]>

import time
import logging
import traceback
import sys

from bidict import bidict
import rtmidi
import click

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


def midi_cc_callback(event, unused):
    message, deltatime = event
    if message[0] == MIDI_LS9.CC_CMD_BYTE:
        logging.info(f'CC Message    {message[0]}\t{message[1]}\t{message[2]}')

midi_nrpn_console_messages = []
def midi_nrpn_callback(event, timeout_counter):
    message, deltatime = event

    if message[0] == MIDI_LS9.CC_CMD_BYTE:
        midi_nrpn_console_messages.append(message)
    if len(midi_nrpn_console_messages) == 4:
        controller = get_nrpn_ctlr(midi_nrpn_console_messages)
        data =       get_nrpn_data(midi_nrpn_console_messages)
        logging.info(f'NRPN Message    Controller  {hex(controller)}\tData  {hex(data)}')
        midi_nrpn_console_messages.clear()
        timeout_counter = 0


# this is a small tool to echo any NRPN-formatted CC commands
timeout_counter = 0
def midi_console(midi_port, console):
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
        midi_in.set_callback(midi_nrpn_callback, timeout_counter)

    try:
        while True:
            time.sleep(0.1)
            timeout_counter += 1
            if len(midi_nrpn_console_messages) < 4 and timeout_counter > 10:
                logging.warning(f'Timeout on midi input buffer! {midi_nrpn_console_messages=}')
                midi_nrpn_console_messages.clear()
                timeout_counter = 0
            print()
    except KeyboardInterrupt:
        print('Exiting...')
    finally:
        midi_in.close_port()
        sys.exit()

#This code is event based, it will only trigger upon receiving a message from the mixer
@click.command()
@click.option('-v', '--verbose', is_flag=True, default=False, help='Set logging level to DEBUG')
@click.option('-c', '--console', default=None, type=click.Choice(['CC', 'NRPN'], case_sensitive=False), help='Run in console mode')
@click.option('-p', '--port', default=0, metavar='PORT', show_default=True, type=int, help='Specify MIDI port number')
def main(port, console, verbose):
    #if the console flag was passed, run one of the mini-tools instead of the main program (automations)
    if console is not None:
        midi_console(port, console)

    # Setup the MIDI input & output
    midi_in =  rtmidi.MidiIn()
    midi_out = rtmidi.MidiOut()

    midi_in.open_port(port)
    midi_out.open_port(port)

    if verbose is True:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO
    # time is given in ISO8601 date format
    logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', level=log_level)
    logging.info('MIDI LS9 Automations. Waiting for incoming MIDI NRPN messages...')

    midi_messages = []
    timeout_counter = 0
    while True:
        #delay is necessary to not overload the CPU or RAM
        time.sleep(0.005)
        # if there is an incomplete packet in the buffer, increase the timeout
        if len(midi_messages) > 0:
            timeout_counter += 1
        #if counter exceeds 0.005 * 20 = 100ms
        if timeout_counter > 20:
            logging.warning('Timeout! Resetting MIDI input buffer')
            midi_messages.clear()
            timeout_counter = 0

        # Get the raw data from the midi get_message function.
        #   It will either return None, or a 2 element list
        midi_msg = midi_in.get_message()
        if midi_msg is not None:
            # the second element (midi_msg[1]) is the timestamp in unix time
            messages = midi_msg[0]
            # Filter out everything but CC (Control Change) commands
            if messages[0] == MIDI_LS9.CC_CMD_BYTE:
                midi_messages.append(messages)
                logging.debug(f'Received CC command {midi_msg[0]} @{midi_msg[1]}')
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
                    timeout_counter = 0

if __name__ == '__main__':
    main()
