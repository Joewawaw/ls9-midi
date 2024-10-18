#!../bin/python3
####################################################################################################
############################## MIDI Automation for Yamaha LS9-32 Mixer #############################
#### - Usage:
####   > Run main program
####       midi_yamaha_ls9.py [verbose]
####   > Run in console mode: program will echo any NRPN msgs received with controller+data values
####       midi_yamaha_ls9.py console
####   
#### - Description:
####   This code automates some functions in the Yamaha LS-9 Mixer for the Ottawa Sai Centre
####   Here are the automations
####       1. CHR<->WL ON/OFF toggling. when a CHR ch is turned ON/OFF, 
####          its lead ch will toggle the opposite state
####       2. WLMC<->WLCHR<->LEADWL swapping
####          Wireless Mics can be swapped between an M.C. role, a chorus role, or a lead role
####       3. Monitor Mute mic on fader drop. When the fader for CH01-10 (i.e. vocals) drops below
####          -60 dB the send of that channel to MIX1/2 will drop to -inf
####          when it is raised back above -50dB the send to MIX1/2 will go to 0 dB
####       4. WLTBK Mics. Wireless Mics 3 & 4 can be used as talkback mics 
####          (via ST-IN3/ST-IN4 ON/OFF), i.e. mics that route to MON bus do not route to ST LR
####       5. LINE2 routing to BASMNT or LOBBY via ST-IN1/ST-IN2 ON/OFF switches.
####
#### - Requirements:
####   This code requires a python venv with packages python-rtmidi & bidict installed.
####   Here are the steps
####       apt update
####       apt install python-venv
####       python -m venv ls9-midi
####       cd ls9-midi
####       git clone https://github.com/joewawaw/ls9-midi src
####       source bin/activate
####       pip install python-rtmidi bidict
####       cd src
#### - pip Package Reference:
####     https://pypi.org/project/python-rtmidi/
####     https://pypi.org/project/bidict/
####################################################################################################
####################################################################################################
import time
import logging
import traceback
import sys

from bidict import bidict
import rtmidi

## TO DO:
# - unit tests!
#     assert all is_ statements
#     assert channel out of bounds
#     assert simple midi cc filter
#     assert invalid nrpn message
#     assert rx buffer timeout

MIDI_ON_OFF_CONTROLLERS = bidict({
    "CH01" : 0x1b0b, "CH02" : 0x1b8b, "CH03" : 0x1c0b, "CH04" : 0x1c8b, "CH05" : 0x1d0b, "CH06" : 0x1d8b, "CH07" : 0x1e0b, "CH08" : 0x1e8b,
    "CH09" : 0x1f0b, "CH10" : 0x1f8b, "CH11" : 0x200b, "CH12" : 0x208b, "CH13" : 0x210b, "CH14" : 0x218b, "CH15" : 0x220b, "CH16" : 0x228b,
    "CH17" : 0x230b, "CH18" : 0x238b, "CH19" : 0x240b, "CH20" : 0x248b, "CH21" : 0x250b, "CH22" : 0x258b, "CH23" : 0x260b, "CH24" : 0x268b,
    "CH25" : 0x270b, "CH26" : 0x278b, "CH27" : 0x280b, "CH28" : 0x288b, "CH29" : 0x290b, "CH30" : 0x298b, "CH31" : 0x2a0b, "CH32" : 0x2a8b,

    "CH33" : 0x2b0b, "CH34" : 0x2b8b, "CH35" : 0x2c0b, "CH36" : 0x2c8b, "CH37" : 0x2d0b, "CH38" : 0x2d8b, "CH39" : 0x2e0b, "CH40" : 0x2e8b,
    "CH41" : 0x2f0b, "CH42" : 0x2f8b, "CH43" : 0x300b, "CH44" : 0x308b, "CH45" : 0x310b, "CH46" : 0x318b, "CH47" : 0x320b, "CH48" : 0x328b,
    "CH49" : 0x370b, "CH50" : 0x378b, "CH51" : 0x380b, "CH52" : 0x388b, "CH53" : 0x390b, "CH54" : 0x398b, "CH55" : 0x3a0b, "CH56" : 0x3a8b,
    "CH57" : 0x3b0b, "CH58" : 0x3b8b, "CH59" : 0x3c0b, "CH60" : 0x3c8b, "CH61" : 0x3d0b, "CH62" : 0x3d8b, "CH63" : 0x3e0b, "CH64" : 0x3e8b,

    "MIX1" : 0xb0c,  "MIX2" : 0xb8c,  "MIX3" : 0xc0c,  "MIX4" : 0xc8c,  "MIX5" : 0xd0c,  "MIX6" : 0xd8c,  "MIX7" : 0xe0c,  "MIX8" : 0xe8c,
    "MIX9" : 0xf0c,  "MIX10": 0xf8c,  "MIX11": 0x100c, "MIX12": 0x108c, "MIX13": 0x110c, "MIX14": 0x118c, "MIX15": 0x120c, "MIX16": 0x128c,
    "MT1"  : 0x150c, "MT2"  : 0x158c, "MT3"  : 0x160c, "MT4"  : 0x168c, "MT5"  : 0x170c, "MT6"  : 0x178c, "MT7"  : 0x180c, "MT8"  : 0x188c,

    "ST-IN1": 0x330b, "ST-IN2": 0x340b, "ST-IN3": 0x350b, "ST-IN4": 0x360b, "ST LR": 0x190c, "MONO": 0x1758
})

#! fill this in
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

# "SOF" means "Sends on Fader"
MIDI_MIX1_2_SOF_CONTROLLERS = bidict({
    "CH01" : 0x1858, "CH02" : 0x18d8, "CH03" : 0x1958, "CH04" : 0x19d8, "CH05" : 0x1a58, "CH06" : 0x1ad8, "CH07" : 0x1b58, "CH08" : 0x1bd8,
    "CH09" : 0x1c58, "CH10" : 0x1cd8, "CH11" : 0x1d58, "CH12" : 0x1dd8, "CH13" : 0x1e58, "CH14" : 0x1ed8, "CH15" : 0x1f58, "CH16" : 0x1fd8,
    "CH17" : 0x2058, "CH18" : 0x20d8, "CH19" : 0x2158, "CH20" : 0x21d8, "CH21" : 0x2258, "CH22" : 0x22d8, "CH23" : 0x2358, "CH24" : 0x23d8,
    "CH25" : 0x2458, "CH26" : 0x24d8, "CH27" : 0x2558, "CH28" : 0x25d8, "CH29" : 0x2658, "CH30" : 0x26d8, "CH31" : 0x2758, "CH32" : 0x27d8,

#! this part is incomplete
    "CH33" : 0x0041, "CH34" : 0x0042, "CH35" : 0x0043, "CH36" : 0x0044, "CH37" : 0x0045, "CH38" : 0x0046, "CH39" : 0x0047, "CH40" : 0x0048,
    "CH41" : 0x0051, "CH42" : 0x0052, "CH43" : 0x0053, "CH44" : 0x0054, "CH45" : 0x0055, "CH46" : 0x0056, "CH47" : 0x0057, "CH48" : 0x0058,
    "CH49" : 0x0061, "CH50" : 0x0062, "CH51" : 0x0063, "CH52" : 0x0064, "CH53" : 0x0065, "CH54" : 0x0066, "CH55" : 0x0067, "CH56" : 0x0068,
    "CH57" : 0x0071, "CH58" : 0x0072, "CH59" : 0x0073, "CH60" : 0x0074, "CH61" : 0x0075, "CH62" : 0x0076, "CH63" : 0x0077, "CH64" : 0x0078
})

# values to switch a channel ON/OFF
MIDI_CH_ON_VALUE  = 0x3FFF
MIDI_CH_OFF_VALUE = 0x0000

# relevant values for fader controlling
MIDI_FADE_0DB_VALUE =    0xFFFF
MIDI_FADE_50DB_VALUE =   0xFFFF
MIDI_FADE_60DB_VALUE =   0xFFFF
MIDI_FADE_NEGINF_VALUE = 0xFFFF

# controller + value for patch in for "PC IN2" to ST-IN1/ST-IN2 channel strips
MIDI_STIN1_PATCH_IN26 =    0xFFFF
MIDI_STIN1_PATCH_IN_OFF =  0xFFFF
MIDI_STIN2_PATCH_IN26 =    0xFFFF
MIDI_STIN2_PATCH_IN_OFF =  0xFFFF
MIDI_STIN3_PATCH_IN31 =    0xFFFF
MIDI_STIN3_PATCH_IN_OFF =  0xFFFF
MIDI_STIN4_PATCH_IN32 =    0xFFFF
MIDI_STIN4_PATCH_IN_OFF =  0xFFFF
MIDI_IN_PATCH_ON_VALUE =   0xFFFF
MIDI_IN_PATCH_OFF_VALUE =  0xFFFF

# controller + value to output patch a MT to an OMNI port
MT1_PATCH_OUT_TO_OMNI11 = 0x0000
MT2_PATCH_OUT_TO_OMNI12 = 0x0000
MIDI_PATCH_ON_VALUE =     0x0000

# controller + value for selecting a new patch to a CH's direct input
CH21_DIRECT_PATCH_TO_OMNI11 = 0x0001
CH21_DIRECT_PATCH_TO_OMNI12 = 0x0002
MIDI_DIRECT_PATCH_ON_VALUE =  0x0000
MIDI_DIRECT_PATCH_OFF_VALUE = 0x0001

# controller + value for toggling the direct on/off button
CH21_DIRECT_PATCH_ONOFF = 0x0000
MIDI_DIRECT_ON_VALUE =    0x0000
MIDI_DIRECT_OFF_VALUE =   0x0000

# controller + value for MON bus defined inputs for IN31 & IN32
MIDI_MON_DEFINE_IN31 =      0xFFFF
MIDI_MON_DEFINE_IN32 =      0xFFFF
MIDI_MON_DEFINE_ON_VALUE =  0x0000
MIDI_MON_DEFINE_OFF_VALUE = 0x0001

# Mappings for chorus <-> lead automations. WL Mics cycle between 3 states: M.C., chorus & lead
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

#MIDI defined constants for CC commands & NRPN sequence
MIDI_CC_CMD_BYTE = 0xB0
MIDI_NRPN_BYTE_1 = 0x62
MIDI_NRPN_BYTE_2 = 0x63
MIDI_NRPN_BYTE_3 = 0x06
MIDI_NRPN_BYTE_4 = 0x26

def is_valid_nrpn_message(msg):
    if int(msg[0][1]) != MIDI_NRPN_BYTE_1 or int(msg[1][1]) != MIDI_NRPN_BYTE_2 or \
       int(msg[2][1]) != MIDI_NRPN_BYTE_3 or int(msg[3][1]) != MIDI_NRPN_BYTE_4:
        raise ValueError(f"Invalid NRPN MIDI data sequence! MIDI Message Dump: {msg}")
    return True

def is_on_off_operation(msg):
    # Since the bidict below contains all of the on/off channels, we can take message and check
    #   if it matches a value in the ON_OFF_CONTROLLERS mapping to find out if this
    #   message is an on/off operation.
    # We use inverse() as the mapping is <ch_name> -> <controller_number> (we want to find ch_name)
    if ( MIDI_ON_OFF_CONTROLLERS.inverse[get_nrpn_controller(msg)] ) is not None:
        return True
    return False

def is_fade_operation(msg):
    if ( MIDI_FADER_CONTROLLERS.inverse[get_nrpn_controller(msg)] ) is not None:
        return True
    return False

#returns a string corresponding to the channel (or mix/mt) of the message
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

#this returns the nrpn controller. this is passed through one of the bidicts to return a string
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
        # We only process on CH01-CH10
        if channel in CHORUS_CH_TO_LEAD_CH_MAPPING:
            # automate muting vocal mics on the MIX1,2 (for lead and chorus) if they are < -60
            if data < MIDI_FADE_60DB_VALUE:
                logging.debug(f"MIXER IN: CH{channel} fade below -60dB")
                logging.info(f"MIDI OUT: CH{channel} Send to MIX1,2 @ -inf dB")
                send_nrpn(midi_out, MIDI_MIX1_2_SOF_CONTROLLERS[channel], MIDI_FADE_NEGINF_VALUE)

                lead_channel = CHORUS_CH_TO_LEAD_CH_MAPPING[channel]
                logging.info(f"MIDI OUT: CH{lead_channel} Send to MIX1,2 @ -inf dB")
                send_nrpn(midi_out, MIDI_MIX1_2_SOF_CONTROLLERS[lead_channel], MIDI_FADE_NEGINF_VALUE)
            # pull back to 0dB if -60dB < data < -50dB
            elif data < MIDI_FADE_50DB_VALUE:
                logging.debug(f"MIXER IN: CH{channel} fade above -60dB")
                logging.info(f"MIDI OUT: CH{lead_channel} Send to MIX1,2 @ 0 dB")
                send_nrpn(midi_out, MIDI_MIX1_2_SOF_CONTROLLERS[channel],      MIDI_FADE_0DB_VALUE)

                lead_channel = CHORUS_CH_TO_LEAD_CH_MAPPING[channel]
                logging.info(f"MIDI OUT: CH{lead_channel} Send to MIX1,2 @ 0 dB")
                send_nrpn(midi_out, MIDI_MIX1_2_SOF_CONTROLLERS[lead_channel], MIDI_FADE_0DB_VALUE)

    # Processing for ON/OFF message operations
    if is_on_off_operation(messages):
        data = get_on_off_data(messages)
    #### Automation for CH01-CH10: When any on/off is pressed, the layer 33-64 duplicate is toggled the opposite state
        # if the channel is in the forward values of the mapping, it is one of the original channels. CH01-CH10
        if channel in CHORUS_CH_TO_LEAD_CH_MAPPING:
            #if the channel is switched ON, switch OFF the duplicate channel
            if  data is True:
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
            if data is True:
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
        elif channel in WIRELESS_MC_TO_CHR_MAPPING:
            chr_channel =  WIRELESS_MC_TO_CHR_MAPPING[channel]
            lead_channel = WIRELESS_MC_TO_LEAD_MAPPING[channel]
            # If Wireless MC CH N switched ON, then turn off WLCHR N & LEADWL N
            if data is True:
                logging.info(f"MIDI OUT: CH{lead_channel} OFF & CH {chr_channel} OFF")
                send_nrpn(midi_out, chr_channel,  MIDI_CH_OFF_VALUE)
                send_nrpn(midi_out, lead_channel, MIDI_CH_OFF_VALUE)
            # If Wireless MC CH N switched off, then switch on WLCHR N and turn off LEADWL N
            else:
                logging.info(f"MIDI OUT: CH{chr_channel} ON & CH {lead_channel} OFF")
                send_nrpn(midi_out, chr_channel,  MIDI_CH_ON_VALUE)
                send_nrpn(midi_out, lead_channel, MIDI_CH_OFF_VALUE)

        ## handling switch presses on the LEADWL channels
        elif channel in WIRELESS_MC_TO_LEAD_MAPPING.inv:
            mc_channel =  WIRELESS_MC_TO_LEAD_MAPPING.inv[channel]
            chr_channel = WIRELESS_CHR_TO_LEAD_MAPPING.inv[channel]
            # If LEADWL CH N switched ON, then turn off WLCHR N & WLMC N
            if data is True:
                logging.info(f"MIDI OUT: CH{chr_channel} OFF & CH {mc_channel} OFF")
                send_nrpn(midi_out, chr_channel, MIDI_CH_OFF_VALUE)
                send_nrpn(midi_out, mc_channel,  MIDI_CH_OFF_VALUE)
            # If LEADWL CH N switched off, then switch on WLCHR N & turn off WLMC N
            else:
                logging.info(f"MIDI OUT: CH{chr_channel} ON & CH {mc_channel} OFF")
                send_nrpn(midi_out, chr_channel, MIDI_CH_ON_VALUE)
                send_nrpn(midi_out, mc_channel,  MIDI_CH_OFF_VALUE)

        ## handling switch presses on the WLCHR channels
        elif channel in WIRELESS_CHR_TO_LEAD_MAPPING:
            mc_channel =   WIRELESS_MC_TO_CHR_MAPPING.inv[channel]
            lead_channel = WIRELESS_CHR_TO_LEAD_MAPPING[channel]
            # If WLCHR CH N switched ON, then turn off LEADWL N & WLMC N
            if data is True:
                logging.info(f"MIDI OUT: CH{mc_channel} OFF & CH {lead_channel} OFF")
                send_nrpn(midi_out, mc_channel,   MIDI_CH_OFF_VALUE)
                send_nrpn(midi_out, lead_channel, MIDI_CH_OFF_VALUE)
            # If WLCHR CH N switched off, then switch on LEADWL N and turn off WLMC N
            else:
                logging.info(f"MIDI OUT: CH{lead_channel} ON & CH {mc_channel} OFF")
                send_nrpn(midi_out, lead_channel, MIDI_CH_ON_VALUE)
                send_nrpn(midi_out, mc_channel,   MIDI_CH_OFF_VALUE)

    ##### Automation for ST-IN1 & ST-IN2 channels: we reroute LINE 2 to LOBBY or BASMNT (or both)
#! with persistent data (global vars?) we can have LINE2 patch to ST LR if ST-IN1 & ST-IN2 are OFF
        elif channel == "ST-IN1":
            # if ST-IN1 was switched ON, DIRECT patch LINE 2 to BASMNT, and patch PC IN2 to ST-IN1
            if data is True:
                # turn off ST-IN2
                send_nrpn(midi_out, CH21_DIRECT_PATCH_ONOFF,   MIDI_DIRECT_OFF_VALUE)
                send_nrpn(midi_out, MT2_PATCH_OUT_TO_OMNI12,   MIDI_PATCH_ON_VALUE )
                send_nrpn(midi_out, MIDI_STIN2_PATCH_IN_OFF,   MIDI_IN_PATCH_OFF_VALUE)
                send_nrpn(midi_out, MIDI_ON_OFF_CONTROLLERS["ST-IN2"],   MIDI_CH_OFF_VALUE)

                logging.info("MIDI OUT: Patch LINE2 to BASMNT")
                send_nrpn(midi_out, CH21_DIRECT_PATCH_TO_OMNI11, MIDI_DIRECT_PATCH_ON_VALUE)
                send_nrpn(midi_out, CH21_DIRECT_PATCH_ONOFF,     MIDI_DIRECT_ON_VALUE)
                send_nrpn(midi_out, MIDI_STIN1_PATCH_IN26,       MIDI_IN_PATCH_ON_VALUE)
            # if switched off, patch back OMNI11 (steal patch will disable LINEIN automatically)
            #   to BASMNT and unpatch ST-IN1
            else:
                logging.info("MIDI OUT: Patch LINE2 OFF")
                send_nrpn(midi_out, CH21_DIRECT_PATCH_ONOFF, MIDI_DIRECT_OFF_VALUE)
                send_nrpn(midi_out, MT1_PATCH_OUT_TO_OMNI11, MIDI_PATCH_ON_VALUE)
                send_nrpn(midi_out, MIDI_STIN1_PATCH_IN_OFF, MIDI_IN_PATCH_OFF_VALUE)

        elif channel == "ST-IN2":
            # if ST-IN2 was switched ON, route LINE 2 to LOBBY, and patch PC IN2 to ST-IN2
            if data is True:
                # turn off ST-IN1
                send_nrpn(midi_out, CH21_DIRECT_PATCH_ONOFF,   MIDI_DIRECT_OFF_VALUE)
                send_nrpn(midi_out, MT1_PATCH_OUT_TO_OMNI11,   MIDI_PATCH_ON_VALUE )
                send_nrpn(midi_out, MIDI_STIN1_PATCH_IN_OFF,   MIDI_IN_PATCH_OFF_VALUE)
                send_nrpn(midi_out, MIDI_ON_OFF_CONTROLLERS["ST-IN1"],   MIDI_CH_OFF_VALUE)

                logging.info("MIDI OUT: Patch LINE2 to LOBBY")
                send_nrpn(midi_out, CH21_DIRECT_PATCH_TO_OMNI12, MIDI_DIRECT_PATCH_ON_VALUE)
                send_nrpn(midi_out, CH21_DIRECT_PATCH_ONOFF,     MIDI_DIRECT_ON_VALUE)
                send_nrpn(midi_out, MIDI_STIN2_PATCH_IN26,       MIDI_IN_PATCH_ON_VALUE)
            #else unroute LINE 2 from LOBBY and patch OMNI port back to MT2, and unpatch ST-IN2
            else:
                logging.info("MIDI OUT: Patch LINE2 OFF")
                send_nrpn(midi_out, MT1_PATCH_OUT_TO_OMNI11, MIDI_PATCH_ON_VALUE )
                send_nrpn(midi_out, CH21_DIRECT_PATCH_ONOFF, MIDI_DIRECT_OFF_VALUE)
                send_nrpn(midi_out, MIDI_STIN2_PATCH_IN_OFF, MIDI_IN_PATCH_OFF_VALUE)

    #### Automation for ST-IN3 & ST-IN4 channels: WLTKBK switches
        elif channel == "ST-IN3":
            # WLTBK3: Turn OFF WL3 MC,CHR,LEAD & define input IN31 for MON bus & patch in ST-IN3
            if data is True:
                logging.info("MIDI OUT: WLTBK3 ON")
                send_nrpn(midi_out, MIDI_ON_OFF_CONTROLLERS["CH13"], MIDI_CH_OFF_VALUE)
                send_nrpn(midi_out, MIDI_ON_OFF_CONTROLLERS["CH45"], MIDI_CH_OFF_VALUE)
                send_nrpn(midi_out, MIDI_ON_OFF_CONTROLLERS["CH49"], MIDI_CH_OFF_VALUE)
                #send define input patch ON to IN31
                send_nrpn(midi_out, MIDI_MON_DEFINE_IN31,     MIDI_MON_DEFINE_ON_VALUE)
                #patch in to ST-IN3's channel strip
                send_nrpn(midi_out, MIDI_STIN3_PATCH_IN31,    MIDI_IN_PATCH_ON_VALUE)
            #else, always revert mic back to MC mode, and define OFF for MON bus
            else:
                logging.info("MIDI OUT: WLTBK3 OFF")
                send_nrpn(midi_out, MIDI_ON_OFF_CONTROLLERS["CH13"], MIDI_CH_ON_VALUE)
                send_nrpn(midi_out, MIDI_MON_DEFINE_IN31,            MIDI_MON_DEFINE_OFF_VALUE)
                send_nrpn(midi_out, MIDI_STIN3_PATCH_IN31,           MIDI_IN_PATCH_OFF_VALUE)

        elif channel == "ST-IN4":
            # WLTBK4: Turn OFF WL4 MC,CHR,LEAD & define input IN32 for MON bus & patch to ST-IN4
            if data is True:
                logging.info("MIDI OUT: WLTBK4 ON")
                send_nrpn(midi_out, MIDI_ON_OFF_CONTROLLERS["CH14"], MIDI_CH_OFF_VALUE)
                send_nrpn(midi_out, MIDI_ON_OFF_CONTROLLERS["CH46"], MIDI_CH_OFF_VALUE)
                send_nrpn(midi_out, MIDI_ON_OFF_CONTROLLERS["CH50"], MIDI_CH_OFF_VALUE)
                #send define input patch ON to IN32
                send_nrpn(midi_out, MIDI_MON_DEFINE_IN32,     MIDI_MON_DEFINE_ON_VALUE)
                #patch in to ST-IN4's channel strip
                send_nrpn(midi_out, MIDI_STIN4_PATCH_IN32,    MIDI_IN_PATCH_ON_VALUE)
            #else, always revert mic back to MC mode, and define OFF for MON bus
            else:
                logging.info("MIDI OUT: WLTBK4 OFF")
                send_nrpn(midi_out, MIDI_ON_OFF_CONTROLLERS["CH14"], MIDI_CH_ON_VALUE)
                send_nrpn(midi_out, MIDI_MON_DEFINE_IN32,            MIDI_MON_DEFINE_OFF_VALUE)
                send_nrpn(midi_out, MIDI_STIN4_PATCH_IN32,           MIDI_IN_PATCH_OFF_VALUE)

def midi_console(midi_in):
    cc_messages = []

    logging.basicConfig(format='%(asctime)s %(message)s', level=logging.INFO)
    logging.info("MIDI Console. Echoing all incoming MIDI NRPN messages (controller+data).\n\
                 Press CTRL+C to exit")

    while True:
        time.sleep(0.01)
        midi_msg = midi_in.get_message()
        if midi_msg is not None:
            messages = midi_msg[0]
            if messages[0] == MIDI_CC_CMD_BYTE:
                cc_messages.append(messages)
            if len(cc_messages) == 4:
                controller = hex(get_nrpn_controller(cc_messages))
                data =       hex(get_nrpn_data(cc_messages))
                logging.info(f"Controller\t{controller}\t\tData\t{data}")
                cc_messages.clear()


#This code is event based, it will only trigger upon receiving a message from the mixer
def main(log_level=logging.INFO):
    # Setup the MIDI input & output
    midi_in =  rtmidi.MidiIn()
    midi_out = rtmidi.MidiOut()

    midi_in.open_port(0)
    midi_out.open_port(0)

    # time is given in ISO8601 date format
    logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', level=log_level)

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

        # Get the raw data from the midi get_message function.
        #   It will either return None, or a 2 element list
        midi_msg = midi_in.get_message()

        if midi_msg is not None:
            # get the message packet, the other
            #   entry (midi_msg[1]) is the timestamp in unix time
            messages = midi_msg[0]
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
                    cc_messages.clear()  # Clear the list for the next batch of 4 messages
                    timeout_counter = 0

if __name__ == '__main__':
    LOG_LEVEL = logging.INFO
    #run the console mini-app if the argument "console" was passed to the script
    if len(sys.argv) > 1:
        #if "console", "midi" or "shell" is passed as first argument
        if "console" in sys.argv[1] or "midi" in sys.argv[1] or "shell" in sys.argv[1]:
            midi_in_console = rtmidi.MidiIn()
            midi_in_console.open_port(0)
            try:
                midi_console(midi_in_console)
            except KeyboardInterrupt:
                print("Exiting...")
            finally:
                midi_in_console.close_port()
                sys.exit()
        # if -v, --verbose, or similar is passed as only argument
        elif "-v" in sys.argv[1] or "verbose" in sys.argv[1] or "debug" in sys.argv[1]:
            LOG_LEVEL = logging.DEBUG

    # Run the main function with LOG_LEVEL logging
    main(LOG_LEVEL)
