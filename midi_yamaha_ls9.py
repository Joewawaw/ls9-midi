#!../bin/python3

# Automation for Yamaha LS9-32 Mixer

#! This code requires a python venv with python-rtmidi and bidict installed. Here are the steps
# https://pypi.org/project/python-rtmidi/
# https://pypi.org/project/bidict/
#    apt update
#    apt install python-venv
#    python -m venv ls9-midi
#    cd ls9-midi
#    git clone https://github.com/joewawaw/ls9-midi src
#    source bin/activate
#    pip install python-rtmidi bidict
from bidict import bidict
import rtmidi

import time
import logging
import traceback
import sys

## TO DO:
# - unit tests!
#     assert all is_ statements
#     assert channel out of bounds
#     assert simple midi cc filter 
#     assert invalid nrpn message
#     assert rx buffer timeout
MIDI_CH_ON_VALUE  = 0x3FFF
MIDI_CH_OFF_VALUE = 0x0000

#### fill these in!
MIDI_FADE_0DB_VALUE =    0xFFFF
MIDI_FADE_50DB_VALUE =   0xFFFF
MIDI_FADE_60DB_VALUE =   0xFFFF
MIDI_FADE_NEGINF_VALUE = 0xFFFF

MIDI_IN_PATCH_ON_VALUE =  0xFFFF
MIDI_IN_PATCH_OFF_VALUE = 0xFFFF

#MIDI defined constants for CC commands & NRPN sequence
MIDI_CC_CMD_BYTE = 0xB0
MIDI_NRPN_BYTE_1 = 0x62
MIDI_NRPN_BYTE_2 = 0x63
MIDI_NRPN_BYTE_3 = 0x06
MIDI_NRPN_BYTE_4 = 0x26

MIDI_ON_OFF_CONTROLLERS = bidict({
    "CH01" : 0x0001, "CH02" : 0x0002, "CH03" : 0x0003, "CH04" : 0x0004, "CH05" : 0x0005, "CH06" : 0x0006, "CH07" : 0x0007, "CH08" : 0x0008,
    "CH09" : 0x0011, "CH10" : 0x0012, "CH11" : 0x0013, "CH12" : 0x0014, "CH13" : 0x0015, "CH14" : 0x0016, "CH15" : 0x0017, "CH16" : 0x0018,
    "CH17" : 0x0021, "CH18" : 0x0022, "CH19" : 0x0023, "CH20" : 0x0024, "CH21" : 0x0025, "CH22" : 0x0026, "CH23" : 0x0027, "CH24" : 0x0028,
    "CH25" : 0x0031, "CH26" : 0x0032, "CH27" : 0x0033, "CH28" : 0x0034, "CH29" : 0x0035, "CH30" : 0x0036, "CH31" : 0x0037, "CH32" : 0x0038,

    "CH33" : 0x0041, "CH34" : 0x0042, "CH35" : 0x0043, "CH36" : 0x0044, "CH37" : 0x0045, "CH38" : 0x0046, "CH39" : 0x0047, "CH40" : 0x0048,
    "CH41" : 0x0051, "CH42" : 0x0052, "CH43" : 0x0053, "CH44" : 0x0054, "CH45" : 0x0055, "CH46" : 0x0056, "CH47" : 0x0057, "CH48" : 0x0058,
    "CH49" : 0x0061, "CH50" : 0x0062, "CH51" : 0x0063, "CH52" : 0x0064, "CH53" : 0x0065, "CH54" : 0x0066, "CH55" : 0x0067, "CH56" : 0x0068,
    "CH57" : 0x0071, "CH58" : 0x0072, "CH59" : 0x0073, "CH60" : 0x0074, "CH61" : 0x0075, "CH62" : 0x0076, "CH63" : 0x0077, "CH64" : 0x0078,

    "MIX1" : 0x0081, "MIX2" : 0x0082, "MIX3" : 0x0083, "MIX4" : 0x0084, "MIX5" : 0x0085, "MIX6" : 0x0086, "MIX7" : 0x0087, "MIX8" : 0x0088,
    "MIX9" : 0x0091, "MIX10": 0x0092, "MIX11": 0x0093, "MIX12": 0x0094, "MIX13": 0x0095, "MIX14": 0x0096, "MIX15": 0x0097, "MIX16": 0x0098,
    "MT1"  : 0x00A1, "MT2"  : 0x00A2, "MT3"  : 0x00A3, "MT4"  : 0x00A4, "MT5"  : 0x00A5, "MT6"  : 0x00A6, "MT7"  : 0x00A7, "MT8"  : 0x00A8,

    "ST-IN1": 0x00B1, "ST-IN2": 0x00B2, "ST-IN3": 0x00B3, "ST-IN4": 0x00B4, "ST LR": 0x00B5, "MONO": 0x00B6, "MON": 0x00B7, "PB L": 0x00B8
})

MIDI_FADER_CONTROLLERS = bidict({
    "CH01" : 0x0001, "CH02" : 0x0002, "CH03" : 0x0003, "CH04" : 0x0004, "CH05" : 0x0005, "CH06" : 0x0006, "CH07" : 0x0007, "CH08" : 0x0008,
    "CH09" : 0x0011, "CH10" : 0x0012, "CH11" : 0x0013, "CH12" : 0x0014, "CH13" : 0x0015, "CH14" : 0x0016, "CH15" : 0x0017, "CH16" : 0x0018,
    "CH17" : 0x0021, "CH18" : 0x0022, "CH19" : 0x0023, "CH20" : 0x0024, "CH21" : 0x0025, "CH22" : 0x0026, "CH23" : 0x0027, "CH24" : 0x0028,
    "CH25" : 0x0031, "CH26" : 0x0032, "CH27" : 0x0033, "CH28" : 0x0034, "CH29" : 0x0035, "CH30" : 0x0036, "CH31" : 0x0037, "CH32" : 0x0038,

    "CH33" : 0x0041, "CH34" : 0x0042, "CH35" : 0x0043, "CH36" : 0x0044, "CH37" : 0x0045, "CH38" : 0x0046, "CH39" : 0x0047, "CH40" : 0x0048,
    "CH41" : 0x0051, "CH42" : 0x0052, "CH43" : 0x0053, "CH44" : 0x0054, "CH45" : 0x0055, "CH46" : 0x0056, "CH47" : 0x0057, "CH48" : 0x0058,
    "CH49" : 0x0061, "CH50" : 0x0062, "CH51" : 0x0063, "CH52" : 0x0064, "CH53" : 0x0065, "CH54" : 0x0066, "CH55" : 0x0067, "CH56" : 0x0068,
    "CH57" : 0x0071, "CH58" : 0x0072, "CH59" : 0x0073, "CH60" : 0x0074, "CH61" : 0x0075, "CH62" : 0x0076, "CH63" : 0x0077, "CH64" : 0x0078,

    "MIX1" : 0x0081, "MIX2" : 0x0082, "MIX3" : 0x0083, "MIX4" : 0x0084, "MIX5" : 0x0085, "MIX6" : 0x0086, "MIX7" : 0x0087, "MIX8" : 0x0088,
    "MIX9" : 0x0091, "MIX10": 0x0092, "MIX11": 0x0093, "MIX12": 0x0094, "MIX13": 0x0095, "MIX14": 0x0096, "MIX15": 0x0097, "MIX16": 0x0098,
    "MT1"  : 0x00A1, "MT2"  : 0x00A2, "MT3"  : 0x00A3, "MT4"  : 0x00A4, "MT5"  : 0x00A5, "MT6"  : 0x00A6, "MT7"  : 0x00A7, "MT8"  : 0x00A8,

    "ST-IN1": 0x00B1, "ST-IN2": 0x00B2, "ST-IN3": 0x00B3, "ST-IN4": 0x00B4, "ST LR": 0x00B5, "MONO": 0x00B6, "MON": 0x00B7, "PB L": 0x00B8
})

MIDI_MIX1_MIX2_SENDS_ON_FADER_CONTROLLERS = bidict({
    "CH01" : 0x0001, "CH02" : 0x0002, "CH03" : 0x0003, "CH04" : 0x0004, "CH05" : 0x0005, "CH06" : 0x0006, "CH07" : 0x0007, "CH08" : 0x0008,
    "CH09" : 0x0011, "CH10" : 0x0012, "CH11" : 0x0013, "CH12" : 0x0014, "CH13" : 0x0015, "CH14" : 0x0016, "CH15" : 0x0017, "CH16" : 0x0018,
    "CH17" : 0x0021, "CH18" : 0x0022, "CH19" : 0x0023, "CH20" : 0x0024, "CH21" : 0x0025, "CH22" : 0x0026, "CH23" : 0x0027, "CH24" : 0x0028,
    "CH25" : 0x0031, "CH26" : 0x0032, "CH27" : 0x0033, "CH28" : 0x0034, "CH29" : 0x0035, "CH30" : 0x0036, "CH31" : 0x0037, "CH32" : 0x0038,

    "CH33" : 0x0041, "CH34" : 0x0042, "CH35" : 0x0043, "CH36" : 0x0044, "CH37" : 0x0045, "CH38" : 0x0046, "CH39" : 0x0047, "CH40" : 0x0048,
    "CH41" : 0x0051, "CH42" : 0x0052, "CH43" : 0x0053, "CH44" : 0x0054, "CH45" : 0x0055, "CH46" : 0x0056, "CH47" : 0x0057, "CH48" : 0x0058,
    "CH49" : 0x0061, "CH50" : 0x0062, "CH51" : 0x0063, "CH52" : 0x0064, "CH53" : 0x0065, "CH54" : 0x0066, "CH55" : 0x0067, "CH56" : 0x0068,
    "CH57" : 0x0071, "CH58" : 0x0072, "CH59" : 0x0073, "CH60" : 0x0074, "CH61" : 0x0075, "CH62" : 0x0076, "CH63" : 0x0077, "CH64" : 0x0078
})


MIDI_MIX16_SEND_TO_MT_CONTROLLERS = bidict({
    "MT1"  : 0x00A1, "MT2"  : 0x00A2, "MT3"  : 0x00A3, "MT4"  : 0x00A4, "MT5"  : 0x00A5, "MT6"  : 0x00A6, "MT7"  : 0x00A7, "MT8"  : 0x00A8
})

MIDI_ST_LR_SEND_TO_MT_CONTROLLERS = bidict({
    "MT1"  : 0x00A1, "MT2"  : 0x00A2, "MT3"  : 0x00A3, "MT4"  : 0x00A4, "MT5"  : 0x00A5, "MT6"  : 0x00A6, "MT7"  : 0x00A7, "MT8"  : 0x00A8
})
MIDI_MONO_SEND_TO_MT_CONTROLLERS = bidict({
    "MT1"  : 0x00A1, "MT2"  : 0x00A2, "MT3"  : 0x00A3, "MT4"  : 0x00A4, "MT5"  : 0x00A5, "MT6"  : 0x00A6, "MT7"  : 0x00A7, "MT8"  : 0x00A8
})

MIDI_MIX16_PATCH_TO_ST_LR = bidict({
    "ON"  : 0x0000, "OFF"   : 0x0001
})

# Patch in for "PC IN2" to ST-IN1,2 channel strips
MIDI_STIN1_PATCH_IN_CONTROLLERS = bidict({
    "CH21" : 0x0000, "OFF"  : 0x0001
})
MIDI_STIN2_PATCH_IN_CONTROLLERS = bidict({
    "CH21" : 0x0000, "OFF"  : 0x0001
})

MIDI_MON_DEFINE_IN = bidict({
    "CH31" : 0x0000, "CH32" : 0x0001
})

# mappings for chorus <-> lead automations. wireless mics cycle between 3 states: M.C., chorus and lead
CHORUS_CH_TO_LEAD_CH_MAPPING = bidict({
    "CH01" : "CH33",    "CH02" : "CH34",    "CH03" : "CH35",    "CH04" : "CH36",    "CH05" : "CH37",
    "CH06" : "CH38",    "CH07" : "CH39",    "CH08" : "CH40",    "CH09" : "CH41",    "CH10" : "CH42"
})

WIRELESS_MC_TO_CHR_MAPPING = bidict({
    "CH11" : "CH47",    "CH12" : "CH48",    "CH13" : "CH49",    "CH14" : "CH50"
})

WIRELESS_MC_TO_LEAD_MAPPING = bidict({
    "CH11" : "CH43",    "CH12" : "CH44",    "CH13" : "CH45",    "CH14" : "CH46"
})

WIRELESS_CHR_TO_LEAD_MAPPING = bidict({
    "CH47" : "CH43",    "CH48" : "CH44",    "CH49" : "CH45",    "CH50" : "CH46"
})

# NPRN message structure for Yamaha LS9 (messages are 7 bits):
# CC cmd #   Byte 1   Byte 2   Byte 3
#        1   0xB0     0x62     <CONTROLLER[0]>
#        2   0xB0     0x63     <CONTROLLER[1]>
#        3   0xB0     0x06     <DATA[0]>
#        4   0xB0     0x26     <DATA[1]>

def is_valid_nrpn_message(msg):
    if int(msg[0][1]) != MIDI_NRPN_BYTE_1 or int(msg[1][1]) != MIDI_NRPN_BYTE_2 or int(msg[2][1]) != MIDI_NRPN_BYTE_3 or int(msg[3][1]) != MIDI_NRPN_BYTE_4:
        raise ValueError(f"Invalid NRPN MIDI data sequence! MIDI Message Dump: {msg}")
    return True

def is_on_off_operation(msg):
    # Since the bidict below contains all the on/off channels, we can take message and check if it matches 
    #   a value in the ON_OFF_CONTROLLERS mapping to find out if this message is an on/off operation. 
    # We use inverse() as the mapping is <ch_name> -> <controller_number> (we want to find ch_name)
    if ( MIDI_ON_OFF_CONTROLLERS.inverse[get_nrpn_controller(msg)] ) != None:
        return True
    return False

def is_fade_operation(msg):
    if ( MIDI_FADER_CONTROLLERS.inverse[get_nrpn_controller(msg)] ) != None:
        return True
    return False

#returns a string correspong to the channel (or mix/mt) of the message
def get_channel(msg):
    if is_fade_operation(msg):
        return MIDI_FADER_CONTROLLERS.inverse[get_nrpn_controller(msg)]

    if is_on_off_operation(msg):
        return MIDI_ON_OFF_CONTROLLERS.inverse[get_nrpn_controller(msg)]
    return None

#we need these in the midi message interpretation
def combine_bytes(msb, lsb):
    # & 0b1111111 to mask out the 8th bit (MIDI data is 7 bits)
    return ((msb & 0b1111111) << 7) | (lsb & 0b1111111)
#returns multiple values!
def split_bytes(combined):
    msb = (combined >> 7) & 0b1111111
    lsb = combined & 0b1111111
    return msb, lsb

#this returns the nrpn controller in 0xNNNN hex format. this is passed through one of the bidicts to return a string
def get_nrpn_controller(msg):
    return combine_bytes(msg[0][2], msg[1][2])

#nrpn data corresponds to fade value or on/off presses
def get_nrpn_data(msg):
    return combine_bytes(msg[2][2], msg[3][2])

#returns the state on the on/off button press, True = OFF->ON, False = ON->OFF
def get_on_off_data(msg):
    if not is_on_off_operation(msg):
        raise ValueError("Message is not an ON/OFF operation!")
    
    data = get_nrpn_data(msg)
    if data == MIDI_CH_OFF_VALUE:
        return False
    elif data == MIDI_CH_ON_VALUE:
        return True

def send_nrpn(midi_output, controller, data):
    controller1, controller2 = split_bytes(controller)
    data1, data2 = split_bytes(data)
    
    midi_output.send_message([MIDI_CC_CMD_BYTE, MIDI_NRPN_BYTE_1,  controller1])
    midi_output.send_message([MIDI_CC_CMD_BYTE, MIDI_NRPN_BYTE_2,  controller2])
    midi_output.send_message([MIDI_CC_CMD_BYTE, MIDI_NRPN_BYTE_3,  data1])
    midi_output.send_message([MIDI_CC_CMD_BYTE, MIDI_NRPN_BYTE_4,  data2])

# Process the 4 collected CC messages
def process_cc_messages(messages, midi_out):
    channel = get_channel(messages) #i.e. the NRPN controller

    # Processing for Fade operations
    if is_fade_operation(messages):
        data = get_nrpn_data(messages)
        # We only process on CH01-CH10 and CH11-CH14
        if channel in CHORUS_CH_TO_LEAD_CH_MAPPING or channel in WIRELESS_MC_TO_CHR_MAPPING:
            # We automate muting vocal mics on the monitor mix (for lead and chorus) if they are lowered to -60
            if data < MIDI_FADE_60DB_VALUE:
                logging.debug(f"MIXER IN: CH{channel} fade below -60dB")
                logging.info(f"MIDI OUT: CH{channel} Send to MIX1,2 @ -inf dB")
                send_nrpn(midi_out, MIDI_MIX1_MIX2_SENDS_ON_FADER_CONTROLLERS[channel],      MIDI_FADE_NEGINF_VALUE)
                lead_channel = CHORUS_CH_TO_LEAD_CH_MAPPING[channel]
                logging.info(f"MIDI OUT: CH{lead_channel} Send to MIX1,2 @ -inf dB")
                send_nrpn(midi_out, MIDI_MIX1_MIX2_SENDS_ON_FADER_CONTROLLERS[lead_channel], MIDI_FADE_NEGINF_VALUE)
            # pull back to 0dB if -60dB < data < -50dB
            elif data < MIDI_FADE_50DB_VALUE:
                logging.debug(f"MIXER IN: CH{channel} fade above -60dB")
                logging.info(f"MIDI OUT: CH{lead_channel} Send to MIX1,2 @ 0dB")
                send_nrpn(midi_out, MIDI_MIX1_MIX2_SENDS_ON_FADER_CONTROLLERS[channel],      MIDI_FADE_0DB_VALUE)
                lead_channel = CHORUS_CH_TO_LEAD_CH_MAPPING[channel]
                logging.info(f"MIDI OUT: CH{lead_channel} Send to MIX1,2 @ 0dB")
                send_nrpn(midi_out, MIDI_MIX1_MIX2_SENDS_ON_FADER_CONTROLLERS[lead_channel], MIDI_FADE_0DB_VALUE)
                

    # Processing for ON/OFF message operations
    if is_on_off_operation(messages):
        data = get_on_off_data(messages)
    #### Automation for CH01-CH10: When any on/off is pressed, the layer 33-64 duplicate is toggled the opposite state
        # if the channel is in the forward values of the mapping, it is one of the original channels. CH01-CH10
        if channel in CHORUS_CH_TO_LEAD_CH_MAPPING:
            #if the channel is switched ON, switch OFF the duplicate channel
            if  data == True:
                logging.debug(f"MIXER IN: CH{channel} switched ON")
                channel = CHORUS_CH_TO_LEAD_CH_MAPPING[channel]
                logging.info(f"MIDI OUT: CH{channel} OFF")
                send_nrpn(midi_out, channel, MIDI_CH_OFF_VALUE)
            else:
                logging.debug(f"MIXER IN: CH{channel} switched OFF")
                channel = CHORUS_CH_TO_LEAD_CH_MAPPING[channel]
                logging.info(f"MIDI OUT: CH{channel} ON")
                send_nrpn(midi_out, channel, MIDI_CH_ON_VALUE)
        #if the channel is part of the inverse bidict, it is a duplicate channel (i.e. CH33-CH42)
        elif channel in CHORUS_CH_TO_LEAD_CH_MAPPING.inv:
            #if the duplicate channel is switched ON, switch OFF the original channel
            if data == True:
                logging.debug(f"MIXER IN: CH{channel} switched ON")
                channel = CHORUS_CH_TO_LEAD_CH_MAPPING.inv[channel]
                logging.info(f"MIDI OUT: CH{channel} OFF")
                send_nrpn(midi_out, channel, MIDI_CH_OFF_VALUE)
            else:
                logging.debug(f"MIXER IN: CH{channel} switched OFF")
                channel = CHORUS_CH_TO_LEAD_CH_MAPPING.inv[channel]
                logging.info(f"MIDI OUT: CH{channel} ON")
                send_nrpn(midi_out, channel, MIDI_CH_ON_VALUE)

    #### Automation for Wireless M.C. Mics (CH11-CH14)
        ## handling switch presses on the WL MC channels
        elif channel == "CH11" or channel == "CH12" or channel == "CH13" or channel == "CH14":
            chr_channel =  WIRELESS_MC_TO_CHR_MAPPING[channel]
            lead_channel = WIRELESS_MC_TO_LEAD_MAPPING[channel]
            # If Wireless MC CH N switched ON, then turn off WLCHR N & LEADWL N
            if get_on_off_data(messages) == True:
                send_nrpn(midi_out, chr_channel,  MIDI_CH_OFF_VALUE)
                send_nrpn(midi_out, lead_channel, MIDI_CH_OFF_VALUE)
            # If Wireless MC CH N switched off, then switch on WLCHR N and turn off LEADWL N
            else:
                send_nrpn(midi_out, chr_channel,  MIDI_CH_ON_VALUE)
                send_nrpn(midi_out, lead_channel, MIDI_CH_OFF_VALUE)

        ## handling switch presses on the LEADWL channels
        elif channel == "CH43" or channel == "CH44" or channel == "CH45" or channel == "CH46":
            mc_channel =  WIRELESS_MC_TO_LEAD_MAPPING.inv[channel]
            chr_channel = WIRELESS_CHR_TO_LEAD_MAPPING.inv[channel]
            # If LEADWL CH N switched ON, then turn off WLCHR N & WLMC N
            if get_on_off_data(messages) == True:
                send_nrpn(midi_out, chr_channel, MIDI_CH_OFF_VALUE)
                send_nrpn(midi_out, mc_channel,  MIDI_CH_OFF_VALUE)
            # If LEADWL CH N switched off, then switch on WLCHR N & turn off WLMC N
            else:                
                send_nrpn(midi_out, chr_channel, MIDI_CH_ON_VALUE)
                send_nrpn(midi_out, mc_channel,  MIDI_CH_OFF_VALUE)

        ## handling switch presses on the WLCHR channels
        elif channel == "CH47" or channel == "CH48" or channel == "CH49" or channel == "CH50":
            mc_channel =   WIRELESS_MC_TO_CHR_MAPPING.inv[channel]
            lead_channel = WIRELESS_CHR_TO_LEAD_MAPPING[channel]
            # If WLCHR CH N switched ON, then turn off LEADWL N & WLMC N
            if get_on_off_data(messages) == True:                
                send_nrpn(midi_out, mc_channel,   MIDI_CH_OFF_VALUE)
                send_nrpn(midi_out, lead_channel, MIDI_CH_OFF_VALUE)
            # If WLCHR CH N switched off, then switch on LEADWL N and turn off WLMC N
            else:
                send_nrpn(midi_out, lead_channel, MIDI_CH_ON_VALUE)
                send_nrpn(midi_out, mc_channel,   MIDI_CH_OFF_VALUE)

    ##### Automation for ST-IN1 & ST-IN2 channels: we reroute LINE 2 to LOBBY or BASMNT (or both)
        elif channel == "ST-IN1":
            # if ST-IN1 was switched ON, route LINE 2 to BASMNT, and patch PC IN2 to ST-IN1
            if get_on_off_data(messages) == True:
                send_nrpn(midi_out, MIDI_MONO_SEND_TO_MT_CONTROLLERS["MT1"],  MIDI_FADE_NEGINF_VALUE)
                send_nrpn(midi_out, MIDI_MIX16_SEND_TO_MT_CONTROLLERS["MT1"], MIDI_FADE_0DB_VALUE)
                send_nrpn(midi_out, MIDI_STIN1_PATCH_IN_CONTROLLERS["CH21"],  MIDI_IN_PATCH_ON_VALUE)
            # if switched off, patch MONO to BASMNT and unpatch ST-IN1
            else:
                send_nrpn(midi_out, MIDI_MIX16_SEND_TO_MT_CONTROLLERS["MT1"], MIDI_FADE_NEGINF_VALUE)
                send_nrpn(midi_out, MIDI_MONO_SEND_TO_MT_CONTROLLERS["MT1"],  MIDI_FADE_0DB_VALUE )
                send_nrpn(midi_out, MIDI_STIN1_PATCH_IN_CONTROLLERS["OFF"],   MIDI_IN_PATCH_OFF_VALUE)

        elif channel == "ST-IN2":
            # if ST-IN2 was switched ON, route LINE 2 to LOBBY, and patch PC IN2 to ST-IN2
            if get_on_off_data(messages) == True:
                send_nrpn(midi_out, MIDI_ST_LR_SEND_TO_MT_CONTROLLERS["MT2"], MIDI_FADE_NEGINF_VALUE)
                send_nrpn(midi_out, MIDI_MIX16_SEND_TO_MT_CONTROLLERS["MT2"], MIDI_FADE_0DB_VALUE)
                send_nrpn(midi_out, MIDI_STIN2_PATCH_IN_CONTROLLERS["CH21"],  MIDI_IN_PATCH_ON_VALUE)
            #else unroute LINE 2 from LOBBY and route ST LR to LOBBY, and unpatch ST-IN2
            else:
                send_nrpn(midi_out, MIDI_MIX16_SEND_TO_MT_CONTROLLERS["MT2"], MIDI_FADE_NEGINF_VALUE)
                send_nrpn(midi_out, MIDI_ST_LR_SEND_TO_MT_CONTROLLERS["MT2"], MIDI_FADE_0DB_VALUE )
                send_nrpn(midi_out, MIDI_STIN2_PATCH_IN_CONTROLLERS["OFF"],   MIDI_IN_PATCH_OFF_VALUE )

    #### Automation for ST-IN3 & ST-IN4 channels: WLTKBK switches
        #elif channel == "ST-IN3":


def midi_console(midi_in):
    cc_messages = []

    logging.basicConfig(format='%(asctime)s %(message)s', level=logging.INFO)
    logging.info("MIDI Console. Echoing all incoming MIDI NRPN messages (controller+data). Press CTRL+C to exit")

    while True:
        time.sleep(0.01)
        midi_msg = midi_in.get_message()
        if midi_msg != None:
            messages = midi_msg[0]
            if messages[0] == MIDI_CC_CMD_BYTE:
                cc_messages.append(messages)
            if len(cc_messages) == 4:
                logging.info(f"Controller\t{hex(get_nrpn_controller(cc_messages))}\t\tData\t{get_nrpn_data(cc_messages)}")
                cc_messages.clear()


#This code is event based, it will only trigger upon receiving a message from the mixer
def main():
    LOG_LEVEL = logging.DEBUG

    # Setup the MIDI input & output
    midi_in =  rtmidi.MidiIn()
    midi_out = rtmidi.MidiOut()

    midi_in.open_port(0)
    midi_out.open_port(0)

    # time is given in ISO8601 date format
    logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', level=LOG_LEVEL)
    
    logging.info("Waiting for incoming MIDI NRPN messages...")

    cc_messages = []
    timeout_counter = 0
    while True:
        #delay is necessary to not overload the CPU or RAM
        time.sleep(0.005)
        # if there is an incomplete packet in the buffer, increase the timeout
        if len(cc_messages) > 0:
            timeout_counter += 1
        #if counter exceeds 0.005 * 20 = 100ms
        if timeout_counter > 20:
            logging.warning("Timeout! Resetting MIDI input buffer")
            cc_messages.clear()
            timeout_counter = 0

        #get the raw data from the midi get_message function. It will either return None, or a 2 element list
        midi_msg = midi_in.get_message()

        if midi_msg != None:
            messages = midi_msg[0] #get the message packet, the other entry (midi_msg[1]) is the timestamp in unix time
            # Filter out everything but CC (Control Change) commands
            if messages[0] == MIDI_CC_CMD_BYTE:
                cc_messages.append(messages)
                logging.debug(f"Received CC command {midi_msg[0]} @{midi_msg[1]}")
            # Once we have 4 CC messages, process them
            if len(cc_messages) == 4:
                try:
                    process_cc_messages(cc_messages, midi_out)
                except ValueError as e:
                    error_message = traceback.format_exc()
                    logging.error(error_message)
                    logging.error(str(e))

                finally:
                    timeout_counter = 0
                    cc_messages.clear()  # Clear the list for the next batch of 4 messages

if __name__ == '__main__':
    #run the console mini-app if the argument "console" was passed to the script
    if len(sys.argv) > 1:
        if "console" in sys.argv[1]   or   "midi" in sys.argv[1]   or   "shell" in sys.argv[1]:
            midi_in = rtmidi.MidiIn()
            midi_in.open_port(0)
            try:
                midi_console(midi_in)
            except KeyboardInterrupt:
                print("Exiting...")
            finally:
                midi_in.close_port()
                sys.exit()

    main()
