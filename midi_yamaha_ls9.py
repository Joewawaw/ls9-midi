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
import time
import logging
import traceback
import sys

from bidict import bidict
import rtmidi

#### Constants
MIDI_ON_OFF_CTLRS = bidict({
    "CH01" : 0x1b0b, "CH02" : 0x1b8b, "CH03" : 0x1c0b, "CH04" : 0x1c8b, "CH05" : 0x1d0b,
    "CH06" : 0x1d8b, "CH07" : 0x1e0b, "CH08" : 0x1e8b, "CH09" : 0x1f0b, "CH10" : 0x1f8b,
    "CH11" : 0x200b, "CH12" : 0x208b, "CH13" : 0x210b, "CH14" : 0x218b, "CH15" : 0x220b,
    "CH16" : 0x228b, "CH17" : 0x230b, "CH18" : 0x238b, "CH19" : 0x240b, "CH20" : 0x248b,
    "CH21" : 0x250b, "CH22" : 0x258b, "CH23" : 0x260b, "CH24" : 0x268b, "CH25" : 0x270b,
    "CH26" : 0x278b, "CH27" : 0x280b, "CH28" : 0x288b, "CH29" : 0x290b, "CH30" : 0x298b,
    "CH31" : 0x2a0b, "CH32" : 0x2a8b, "CH33" : 0x2b0b, "CH34" : 0x2b8b, "CH35" : 0x2c0b,
    "CH36" : 0x2c8b, "CH37" : 0x2d0b, "CH38" : 0x2d8b, "CH39" : 0x2e0b, "CH40" : 0x2e8b,
    "CH41" : 0x2f0b, "CH42" : 0x2f8b, "CH43" : 0x300b, "CH44" : 0x308b, "CH45" : 0x310b,
    "CH46" : 0x318b, "CH47" : 0x320b, "CH48" : 0x328b, "CH49" : 0x370b, "CH50" : 0x378b,
    "CH51" : 0x380b, "CH52" : 0x388b, "CH53" : 0x390b, "CH54" : 0x398b, "CH55" : 0x3a0b,
    "CH56" : 0x3a8b, "CH57" : 0x3b0b, "CH58" : 0x3b8b, "CH59" : 0x3c0b, "CH60" : 0x3c8b,
    "CH61" : 0x3d0b, "CH62" : 0x3d8b, "CH63" : 0x3e0b, "CH64" : 0x3e8b,

    "MIX1" : 0xb0c,  "MIX2" : 0xb8c,  "MIX3" : 0xc0c,  "MIX4" : 0xc8c,
    "MIX5" : 0xd0c,  "MIX6" : 0xd8c,  "MIX7" : 0xe0c,  "MIX8" : 0xe8c,
    "MIX9" : 0xf0c,  "MIX10": 0xf8c,  "MIX11": 0x100c, "MIX12": 0x108c,
    "MIX13": 0x110c, "MIX14": 0x118c, "MIX15": 0x120c, "MIX16": 0x128c,
    "MT1"  : 0x150c, "MT2"  : 0x158c, "MT3"  : 0x160c, "MT4"  : 0x168c,
    "MT5"  : 0x170c, "MT6"  : 0x178c, "MT7"  : 0x180c, "MT8"  : 0x188c,

    "ST-IN1": 0x338b, "ST-IN2": 0x340b, "ST-IN3": 0x350b, "ST-IN4": 0x360b,
    "ST LR":  0x190c, "MONO":   0x1758
})

MIDI_FADER_CTLRS = bidict({
    "CH01" : 0x0,    "CH02" : 0x80,   "CH03" : 0x100,  "CH04" : 0x180,  "CH05" : 0x200,
    "CH06" : 0x280,  "CH07" : 0x300,  "CH08" : 0x380,  "CH09" : 0x400,  "CH10" : 0x480,
    "CH11" : 0x500,  "CH12" : 0x580,  "CH13" : 0x600,  "CH14" : 0x680,  "CH15" : 0x700,
    "CH16" : 0x780,  "CH17" : 0x800,  "CH18" : 0x880,  "CH19" : 0x900,  "CH20" : 0x980,
    "CH21" : 0xa00,  "CH22" : 0xa80,  "CH23" : 0xb00,  "CH24" : 0xb80,  "CH25" : 0xc00,
    "CH26" : 0xc80,  "CH27" : 0xd00,  "CH28" : 0xd80,  "CH29" : 0xe00,  "CH30" : 0xe80,
    "CH31" : 0xf00,  "CH32" : 0xf80,  "CH33" : 0x1000, "CH34" : 0x1080, "CH35" : 0x1100,
    "CH36" : 0x1180, "CH37" : 0x1200, "CH38" : 0x1280, "CH39" : 0x1300, "CH40" : 0x1380,
    "CH41" : 0x1400, "CH42" : 0x1480, "CH43" : 0x1500, "CH44" : 0x1580, "CH45" : 0x1600,
    "CH46" : 0x1680, "CH47" : 0x1700, "CH48" : 0x1780, "CH49" : 0x1c00, "CH50" : 0x1c80,
    "CH51" : 0x1d00, "CH52" : 0x1d80, "CH53" : 0x1e00, "CH54" : 0x1e80, "CH55" : 0x1f00,
    "CH56" : 0x1f80, "CH57" : 0x2000, "CH58" : 0x2080, "CH59" : 0x2100, "CH60" : 0x2180,
    "CH61" : 0x2200, "CH62" : 0x2280, "CH63" : 0x2300, "CH64" : 0x2380,
    "MIX1" : 0x3000, "MIX2" : 0x3080, "MIX3" : 0x3100, "MIX4" : 0x3180,
    "MIX5" : 0x3200, "MIX6" : 0x3280, "MIX7" : 0x3300, "MIX8" : 0x3380,
    "MIX9" : 0x3400, "MIX10": 0x3480, "MIX11": 0x3500, "MIX12": 0x3580,
    "MIX13": 0x3600, "MIX14": 0x3680, "MIX15": 0x3700, "MIX16": 0x3780,
    "MT1"  : 0x3a00, "MT2"  : 0x3a80, "MT3"  : 0x3b00, "MT4"  : 0x3b80,
    "MT5"  : 0x3c00, "MT6"  : 0x3c80, "MT7"  : 0x3d00, "MT8"  : 0x3d80,

    "ST-IN1": 0x1880, "ST-IN2": 0x1900, "ST-IN3": 0x1a00, "ST-IN4": 0x1b00,
    "ST LR":  0x3e00, "MONO":   0x3451 #, "MON": 0x
})

# "SOF" means "Sends on Fader"
MIDI_MIX1_SOF_CTLRS = bidict({
    "CH01" : 0x3551, "CH02" : 0x35d1, "CH03" : 0x3651, "CH04" : 0x36d1, "CH05" : 0x3751,
    "CH06" : 0x37d1, "CH07" : 0x3851, "CH08" : 0x38d1, "CH09" : 0x3951, "CH10" : 0x39d1,
    "CH11" : 0x3a51, "CH12" : 0x3ad1, "CH13" : 0x3b51, "CH14" : 0x3bd1, "CH15" : 0x3c51,
    "CH16" : 0x3cd1, "CH17" : 0x3d51, "CH18" : 0x3dd1, "CH19" : 0x3e51, "CH20" : 0x3ed1,
    "CH21" : 0x3f51, "CH22" : 0x3fd1, "CH23" : 0x52,   "CH24" : 0xd2,   "CH25" : 0x152,
    "CH26" : 0x1d2,  "CH27" : 0x252,  "CH28" : 0x2d2,  "CH29" : 0x352,  "CH30" : 0x3d2,
    "CH31" : 0x452,  "CH32" : 0x4d2,  "CH33" : 0x552,  "CH34" : 0x5d2,  "CH35" : 0x652,
    "CH36" : 0x6d2,  "CH37" : 0x752,  "CH38" : 0x7d2,  "CH39" : 0x852,  "CH40" : 0x8d2,
    "CH41" : 0x952,  "CH42" : 0x9d2,  "CH43" : 0xa52,  "CH44" : 0xad2,  "CH45" : 0xb52,
    "CH46" : 0xbd2,  "CH47" : 0xc52,  "CH48" : 0xcd2,  "CH49" : 0x1152, "CH50" : 0x11d2,
    "CH51" : 0x1252, "CH52" : 0x12d2, "CH53" : 0x1352, "CH54" : 0x13d2, "CH55" : 0x1452,
    "CH56" : 0x14d2, "CH57" : 0x2521, "CH58" : 0x25a1, "CH59" : 0x2621, "CH60" : 0x26a1,
    "CH61" : 0x2721, "CH62" : 0x27a1, "CH63" : 0x2821, "CH64" : 0x28a1
})

MIDI_MT5_SOF_CTRLS = bidict({
    "MIX1" : 0xb0c,  "MIX2" : 0xb8c,  "MIX3" : 0xc0c,  "MIX4" : 0xc8c,
    "MIX5" : 0xd0c,  "MIX6" : 0xd8c,  "MIX7" : 0xe0c,  "MIX8" : 0xe8c,
    "MIX9" : 0xf0c,  "MIX10": 0xf8c,  "MIX11": 0x100c, "MIX12": 0x108c,
    "MIX13": 0x110c, "MIX14": 0x118c, "MIX15": 0x120c, "MIX16": 0x128c
})

MIDI_MT6_SOF_CTRLS = bidict({
    "MIX1" : 0xb0c,  "MIX2" : 0xb8c,  "MIX3" : 0xc0c,  "MIX4" : 0xc8c,
    "MIX5" : 0xd0c,  "MIX6" : 0xd8c,  "MIX7" : 0xe0c,  "MIX8" : 0xe8c,
    "MIX9" : 0xf0c,  "MIX10": 0xf8c,  "MIX11": 0x100c, "MIX12": 0x108c,
    "MIX13": 0x110c, "MIX14": 0x118c, "MIX15": 0x120c, "MIX16": 0x128c
})

# values to switch a channel ON/OFF
MIDI_CH_ON_VALUE  = 0x3FFF
MIDI_CH_OFF_VALUE = 0x0000

# relevant values for fader controlling
MIDI_FADE_0DB_VALUE =    0x3370
MIDI_FADE_50DB_VALUE =   0xad0
MIDI_FADE_60DB_VALUE =   0x7b0
MIDI_FADE_NEGINF_VALUE = 0x0

# controller for STLR / MONO send to MT3
MIDI_ST_LR_SEND_TO_MT3 = 0x1f0a
MIDI_MONO_SEND_TO_MT3 =  0x3d57

MIDI_MONO_SEND_TO_MT1  = 0x3757
MIDI_MIX16_SEND_TO_MT1 = 0x68a
MIDI_STLR_SEND_TO_MT2  = 0x140a
MIDI_MIX16_SEND_TO_MT2 = 0x118a

# Mappings for chorus <-> lead automations. WL Mics cycle between 3 states: M.C., chorus & lead
CHORUS_TO_LEAD_MAPPING = bidict({
    "CH01" : "CH33",  "CH02" : "CH34",  "CH03" : "CH35",  "CH04" : "CH36",  "CH05" : "CH37",
    "CH06" : "CH38",  "CH07" : "CH39",  "CH08" : "CH40",  "CH09" : "CH41",  "CH10" : "CH42"
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

#MIDI defined constants for CC commands & NRPN sequence
MIDI_CC_CMD_BYTE = 0xB0
MIDI_NRPN_BYTE_1 = 0x62
MIDI_NRPN_BYTE_2 = 0x63
MIDI_NRPN_BYTE_3 = 0x06
MIDI_NRPN_BYTE_4 = 0x26

####################################################################################################
# NPRN message structure for Yamaha LS9 (messages are 7 bits):
# CC cmd #   Byte 1   Byte 2   Byte 3
#        1   0xB0     0x62     <CONTROLLER[0]>
#        2   0xB0     0x63     <CONTROLLER[1]>
#        3   0xB0     0x06     <DATA[0]>
#        4   0xB0     0x26     <DATA[1]>

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
    if get_nrpn_controller(msg) in MIDI_ON_OFF_CTLRS.inverse:
        return True
    return False

def is_fade_operation(msg):
    if get_nrpn_controller(msg) in MIDI_FADER_CTLRS.inverse:
        return True
    return False

#returns a string corresponding to the channel (or mix/mt) of the message
def get_channel(msg):
    if is_fade_operation(msg):
        return MIDI_FADER_CTLRS.inv[get_nrpn_controller(msg)]

    if is_on_off_operation(msg):
        return MIDI_ON_OFF_CTLRS.inv[get_nrpn_controller(msg)]
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
def get_nrpn_controller(msg):
    return combine_bytes(msg[0][2], msg[1][2])

#return midi NRPN data
def get_nrpn_data(msg):
    return combine_bytes(msg[2][2], msg[3][2])

#returns the state on the on/off button press, True = OFF->ON, False = ON->OFF
def get_on_off_data(msg):
    if not is_on_off_operation(msg):
        raise ValueError("Message is not an ON/OFF operation!")

    data = get_nrpn_data(msg)
    if data == MIDI_CH_OFF_VALUE:
        return False
    if data == MIDI_CH_ON_VALUE:
        return True

def send_nrpn(midi_output, controller, data):
    controller1, controller2 = split_bytes(controller)
    data1, data2 = split_bytes(data)

    midi_output.send_message([MIDI_CC_CMD_BYTE, MIDI_NRPN_BYTE_1,  controller1])
    midi_output.send_message([MIDI_CC_CMD_BYTE, MIDI_NRPN_BYTE_2,  controller2])
    midi_output.send_message([MIDI_CC_CMD_BYTE, MIDI_NRPN_BYTE_3,  data1])
    midi_output.send_message([MIDI_CC_CMD_BYTE, MIDI_NRPN_BYTE_4,  data2])

#these global vars holds the first 14 channel's on/off state (based on fader level)
#it is needed for fader muting/unmuting
channel_states = {
    "CH01": "OFF",  "CH02": "OFF",  "CH03": "OFF",  "CH04": "OFF",  "CH05": "OFF",
    "CH06": "OFF",  "CH07": "OFF",  "CH08": "OFF",  "CH09": "OFF",  "CH10": "OFF",
    "CH11": "OFF",  "CH12": "OFF",  "CH13": "OFF",  "CH14": "OFF"
}
wltbk_state = "OFF"

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
        if channel in CHORUS_TO_LEAD_MAPPING:
            lead_ch = CHORUS_TO_LEAD_MAPPING[channel]
            if data < MIDI_FADE_60DB_VALUE and channel_states[channel] == "ON":
                channel_states[channel] = "OFF"
                out_data = MIDI_FADE_0DB_VALUE
                logging.debug(f"MIXER IN: {channel} fade above -50dB")
                logging.info(f"MIDI OUT: {channel}, {lead_ch} Send to MIX1,2 @ 0 dB")
                send_nrpn(midi_out, MIDI_MIX1_SOF_CTLRS[channel], out_data)
                send_nrpn(midi_out, MIDI_MIX1_SOF_CTLRS[lead_ch], out_data)
            #fade back up to 0dB only if above -50dB, hence it is a software schmitt trigger
            elif data > MIDI_FADE_50DB_VALUE and channel_states[channel] == "OFF":
                channel_states[channel] = "ON"
                out_data = MIDI_FADE_NEGINF_VALUE
                logging.debug(f"MIXER IN: {channel} fade below -60dB")
                logging.info(f"MIDI OUT: {channel}, {lead_ch} Send to MIX1,2 @ -inf dB")
                send_nrpn(midi_out, MIDI_MIX1_SOF_CTLRS[channel], out_data)
                send_nrpn(midi_out, MIDI_MIX1_SOF_CTLRS[lead_ch], out_data)

#! this section is actually not needed
        elif channel in WIRELESS_MC_TO_CHR_MAPPING and channel_states[channel] == "ON":
            channel_states[channel] = "OFF"
            wl_chr_ch =  WIRELESS_MC_TO_CHR_MAPPING[channel]
            wl_lead_ch = WIRELESS_MC_TO_LEAD_MAPPING[channel]
            if data < MIDI_FADE_60DB_VALUE:
                out_data = MIDI_FADE_NEGINF_VALUE
                logging.debug(f"MIXER IN: {channel} fade below -60dB")
                logging.info(f"MIDI OUT: {channel}, {wl_chr_ch}, {wl_lead_ch} Send to MIX1,2 @ -inf dB")
            elif data > MIDI_FADE_50DB_VALUE:
                out_data = MIDI_FADE_0DB_VALUE
                logging.debug(f"MIXER IN: {channel} fade above -50dB")
                logging.info(f"MIDI OUT: {channel}, {wl_chr_ch}, {wl_lead_ch} Send to MIX1,2 @ 0dB")
            send_nrpn(midi_out, MIDI_MIX1_SOF_CTLRS[channel],    out_data)
            send_nrpn(midi_out, MIDI_MIX1_SOF_CTLRS[wl_chr_ch],  out_data)
            send_nrpn(midi_out, MIDI_MIX1_SOF_CTLRS[wl_lead_ch], out_data)

    # Processing for ON/OFF message operations
    if is_on_off_operation(messages):
        data = get_on_off_data(messages)
        if data is True:
        #### Automation for CH01-CH10 switched ON/OFF (switch OFF/ON alt_channel)
            # if the channel is in the forward values of this mapping, it's one of the original channels
            if channel in CHORUS_TO_LEAD_MAPPING:
                alt_channel = CHORUS_TO_LEAD_MAPPING[channel]
                if data is True:
                    out_data = MIDI_CH_OFF_VALUE
                    logging.debug(f"MIXER IN: {channel} switched ON")
                    logging.info(f"MIDI OUT: {alt_channel} OFF")
                else:
                    out_data = MIDI_CH_ON_VALUE
                    logging.debug(f"MIXER IN: {channel} switched OFF")
                    logging.info(f"MIDI OUT: {alt_channel} ON")
                send_nrpn(midi_out, MIDI_ON_OFF_CTLRS[alt_channel], out_data)

            #if the channel is part of the inverse bidict, it is a duplicate channel (i.e. CH33-CH42)
            elif channel in CHORUS_TO_LEAD_MAPPING.inv:
                alt_channel = CHORUS_TO_LEAD_MAPPING.inv[channel]
                if data is True:
                    out_data = MIDI_CH_OFF_VALUE
                    logging.debug(f"MIXER IN: {channel} switched ON")
                    logging.info(f"MIDI OUT: {alt_channel} OFF")
                else:
                    out_data - MIDI_CH_ON_VALUE
                    logging.debug(f"MIXER IN: {channel} switched OFF")
                    logging.info(f"MIDI OUT: {alt_channel} ON")
                send_nrpn(midi_out, MIDI_ON_OFF_CTLRS[alt_channel], out_data)

        #### Automation for Wireless Mics switched ON/OFF
            elif channel in WIRELESS_MC_TO_CHR_MAPPING:
                # If Wireless MC CH N switched ON, then turn off WLCHR N & LEADWL N
                if data is True:
                    #we disable toggling if wltbk_state is ON and the current channel is 13 or 14
                    if wltbk_state == "OFF" or (wltbk_state=="ON" and channel!="CH13" and channel!="CH14"):
                        chr_channel =  WIRELESS_MC_TO_CHR_MAPPING[channel]
                        lead_channel = WIRELESS_MC_TO_LEAD_MAPPING[channel]
                        logging.info(f"MIDI OUT: {lead_channel} OFF & CH {chr_channel} OFF")
                        send_nrpn(midi_out, MIDI_ON_OFF_CTLRS[chr_channel],  MIDI_CH_OFF_VALUE)
                        send_nrpn(midi_out, MIDI_ON_OFF_CTLRS[lead_channel], MIDI_CH_OFF_VALUE)
                    #if a channel that is WLTBK is switched ON while in WLTBK mode,
                    # we need to turn it back off.
                    else:
                        send_nrpn(midi_out, MIDI_ON_OFF_CTLRS[channel],  MIDI_CH_OFF_VALUE)
                else:
                    chr_channel =  WIRELESS_MC_TO_CHR_MAPPING[channel]
                    lead_channel = WIRELESS_MC_TO_LEAD_MAPPING[channel]
                    logging.info(f"MIDI OUT: {chr_channel} ON & CH {lead_channel} OFF")
                    send_nrpn(midi_out, MIDI_ON_OFF_CTLRS[chr_channel],  MIDI_CH_ON_VALUE)
                    send_nrpn(midi_out, MIDI_ON_OFF_CTLRS[lead_channel], MIDI_CH_OFF_VALUE)

            elif channel in WIRELESS_MC_TO_LEAD_MAPPING.inv:
                # If LEADWL CH N switched ON, then turn off WLCHR N & WLMC N
                if data is True:
                    if wltbk_state == "OFF" or (wltbk_state=="ON" and channel!="CH45" and channel!="CH46"):
                        mc_channel =  WIRELESS_MC_TO_LEAD_MAPPING.inv[channel]
                        chr_channel = WIRELESS_CHR_TO_LEAD_MAPPING.inv[channel]
                        logging.info(f"MIDI OUT: {chr_channel} OFF & CH {mc_channel} OFF")
                        send_nrpn(midi_out, MIDI_ON_OFF_CTLRS[chr_channel], MIDI_CH_OFF_VALUE)
                        send_nrpn(midi_out, MIDI_ON_OFF_CTLRS[mc_channel],  MIDI_CH_OFF_VALUE)
                    else:
                        send_nrpn(midi_out, MIDI_ON_OFF_CTLRS[channel],  MIDI_CH_OFF_VALUE)
                else:
                    mc_channel =  WIRELESS_MC_TO_LEAD_MAPPING.inv[channel]
                    chr_channel = WIRELESS_CHR_TO_LEAD_MAPPING.inv[channel]
                    logging.info(f"MIDI OUT: {chr_channel} ON & CH {mc_channel} OFF")
                    send_nrpn(midi_out, MIDI_ON_OFF_CTLRS[chr_channel], MIDI_CH_ON_VALUE)
                    send_nrpn(midi_out, MIDI_ON_OFF_CTLRS[mc_channel],  MIDI_CH_OFF_VALUE)

            elif channel in WIRELESS_CHR_TO_LEAD_MAPPING:
                # If WLCHR CH N switched ON, then turn off LEADWL N & WLMC N
                if data is True:
                    if wltbk_state == "OFF" or (wltbk_state=="ON" and channel!="CH49" and channel!="CH50"):
                        mc_channel =   WIRELESS_MC_TO_CHR_MAPPING.inv[channel]
                        lead_channel = WIRELESS_CHR_TO_LEAD_MAPPING[channel]
                        logging.info(f"MIDI OUT: {mc_channel} OFF & CH {lead_channel} OFF")
                        send_nrpn(midi_out, MIDI_ON_OFF_CTLRS[mc_channel],   MIDI_CH_OFF_VALUE)
                        send_nrpn(midi_out, MIDI_ON_OFF_CTLRS[lead_channel], MIDI_CH_OFF_VALUE)
                    else:
                        send_nrpn(midi_out, MIDI_ON_OFF_CTLRS[channel],  MIDI_CH_OFF_VALUE)
                else:
                    mc_channel =   WIRELESS_MC_TO_CHR_MAPPING.inv[channel]
                    lead_channel = WIRELESS_CHR_TO_LEAD_MAPPING[channel]
                    logging.info(f"MIDI OUT: {lead_channel} ON & CH {mc_channel} OFF")
                    send_nrpn(midi_out, MIDI_ON_OFF_CTLRS[lead_channel], MIDI_CH_ON_VALUE)
                    send_nrpn(midi_out, MIDI_ON_OFF_CTLRS[mc_channel],   MIDI_CH_OFF_VALUE)

        #### Automation for MIX1 or MIX2 switched ON (switch ON ST LR)
            elif channel == "MIX1" or channel == "MIX2" and data is True:
                send_nrpn(midi_out, MIDI_ON_OFF_CTLRS["ST LR"], MIDI_CH_ON_VALUE)
        #### Automation for ST L/R switched OFF (switch OFF MIX1 as well)
            elif channel == "ST LR" and data is False:
                send_nrpn(midi_out, MIDI_ON_OFF_CTLRS["MIX1"], MIDI_CH_OFF_VALUE)

        #### Automation for PC IN2 routing to BASMNT
            elif channel == "ST-IN1":
                if data is True:
                    logging.info("MIDI OUT: PC IN2 -> BASMNT")
                    out_data_mix16 = MIDI_FADE_0DB_VALUE
                    out_data_mono =  MIDI_FADE_NEGINF_VALUE
                else:
                    logging.info("MIDI OUT: STREAM -> BASMNT")
                    out_data_mix16 = MIDI_FADE_NEGINF_VALUE
                    out_data_mono =  MIDI_FADE_0DB_VALUE
                send_nrpn(midi_out, MIDI_MIX16_SEND_TO_MT1, out_data_mix16)
                send_nrpn(midi_out, MIDI_MONO_SEND_TO_MT1,  out_data_mono)

        #### Automation for PC IN2 routing to LOBBY
            elif channel == "ST-IN2":
                if data is True:
                    logging.info("MIDI OUT: PC IN2 -> LOBBY")
                    out_data_mix16 = MIDI_FADE_0DB_VALUE
                    out_data_stlr =  MIDI_FADE_NEGINF_VALUE
                else:
                    logging.info("MIDI OUT: ST L/R -> LOBBY")
                    out_data_mix16 = MIDI_FADE_NEGINF_VALUE
                    out_data_stlr =  MIDI_FADE_0DB_VALUE
                send_nrpn(midi_out, MIDI_MIX16_SEND_TO_MT2, MIDI_FADE_NEGINF_VALUE)
                send_nrpn(midi_out, MIDI_STLR_SEND_TO_MT2,  MIDI_FADE_0DB_VALUE)

        #### Automation for LOUNGE toggle between MONO and ST LR (ST-IN3 switched ON)
            elif channel == "ST-IN3":
                # if ON, route MONO to LOUNGE
                if data is True:
                    logging.info("MIDI OUT: MONO -> LOUNGE")
                    out_data_mono = MIDI_FADE_0DB_VALUE
                    out_data_stlr = MIDI_FADE_NEGINF_VALUE
                # if OFF, route ST LR to LOUNGE
                else:
                    logging.info("MIDI OUT: ST L/R -> LOUNGE")
                    out_data_mono = MIDI_FADE_NEGINF_VALUE
                    out_data_stlr = MIDI_FADE_0DB_VALUE
                send_nrpn(midi_out, MIDI_MONO_SEND_TO_MT3,  out_data_mono)
                send_nrpn(midi_out, MIDI_ST_LR_SEND_TO_MT3, out_data_stlr)

        #### Automation for toggling WLTBK 3 & 4 ON/OFF
            elif channel == "ST-IN4":
                if data is True:
                    logging.info("MIDI OUT: WLTBK3 & WLTBK4 ON")
                    wltbk_state = "ON" # we need this global var to disable WL MC/CHR/LEAD toggling
                    out_data_ch13 = MIDI_CH_OFF_VALUE
                    out_data_ch14 = MIDI_CH_OFF_VALUE
                else:
                    logging.info("MIDI OUT: WLTBK3 & WLTBK4 OFF")
                    wltbk_state = "OFF"
                    #turn on only MC channels (and turn off all alt channels below)
                    out_data_ch13 = MIDI_CH_ON_VALUE
                    out_data_ch14 = MIDI_CH_ON_VALUE

                send_nrpn(midi_out, MIDI_ON_OFF_CTLRS["CH13"], out_data_ch13)
                send_nrpn(midi_out, MIDI_ON_OFF_CTLRS["CH14"], out_data_ch14)
                #turn off all alt channels for wireless mics 3 & 4; as they all route to ST L/R
                send_nrpn(midi_out, MIDI_ON_OFF_CTLRS["CH46"], MIDI_CH_OFF_VALUE)
                send_nrpn(midi_out, MIDI_ON_OFF_CTLRS["CH47"], MIDI_CH_OFF_VALUE)
                send_nrpn(midi_out, MIDI_ON_OFF_CTLRS["CH49"], MIDI_CH_OFF_VALUE)
                send_nrpn(midi_out, MIDI_ON_OFF_CTLRS["CH50"], MIDI_CH_OFF_VALUE)

def midi_nrpn_console(midi_in):
    logging.basicConfig(format='%(asctime)s %(message)s', level=logging.INFO)
    logging.info("MIDI Console. Echoing all incoming MIDI NRPN messages (controller+data).\n\
                 Press CTRL+C to exit")
    midi_messages = []
    counter = 0
    while True:
        time.sleep(0.01)

        counter += 1
        if counter >= 100: # every 1s echo a blank line
            print()
            counter = 0

        midi_msg = midi_in.get_message()
        if midi_msg is not None:
            messages = midi_msg[0]
            logging.debug(f"{messages=}")

            if messages[0] == MIDI_CC_CMD_BYTE:
                midi_messages.append(messages)
            if len(midi_messages) == 4:
                controller = hex(get_nrpn_controller(midi_messages))
                data =       hex(get_nrpn_data(midi_messages))
                logging.info(f"Controller\t{controller}\t\tData\t{data}")
                counter = 0
                midi_messages.clear()


def midi_cc_console(midi_in):
    logging.basicConfig(format='%(asctime)s %(message)s', level=logging.INFO)
    logging.info("MIDI CC Console. Echoing all incoming single packet MIDI CC messages.\n\
                 Press CTRL+C to exit")
    midi_messages = []
    counter = 0
    while True:
        time.sleep(0.01)

        counter += 1
        if counter >= 100: # every 1s echo a blank line
            print()
            counter = 0

        midi_msg = midi_in.get_message()
        if midi_msg is not None:
            messages = midi_msg[0]
            counter = 0
            if messages[0] == MIDI_CC_CMD_BYTE:
                logging.info(f"CC Message\t{messages[0]}")


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
            logging.warning("Timeout! Resetting MIDI input buffer")
            midi_messages.clear()
            timeout_counter = 0

        # Get the raw data from the midi get_message function.
        #   It will either return None, or a 2 element list
        midi_msg = midi_in.get_message()
        if midi_msg is not None:
            # the second element (midi_msg[1]) is the timestamp in unix time
            messages = midi_msg[0]
            # Filter out everything but CC (Control Change) commands
            if messages[0] == MIDI_CC_CMD_BYTE:
                midi_messages.append(messages)
                logging.debug(f"Received CC command {midi_msg[0]} @{midi_msg[1]}")
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
    LOG_LEVEL = logging.INFO
    #run the console mini-app if the argument passed to script
    if len(sys.argv) > 1:
        #if "console", "midi" or "shell" is passed as first argument
        if "console" in sys.argv[1] or "midi" in sys.argv[1] or "shell" in sys.argv[1]:
            midi_in_console = rtmidi.MidiIn()
            midi_in_console.open_port(0)
            try:
                midi_nrpn_console(midi_in_console)
            except KeyboardInterrupt:
                print("Exiting...")
            finally:
                midi_in_console.close_port()
                sys.exit()
        if "cc" in sys.argv[1]:
            midi_in_cc_console = rtmidi.MidiIn()
            midi_in_cc_console.open_port(0)
            try:
                midi_cc_console(midi_in_cc_console)
            except KeyboardInterrupt:
                print("Exiting...")
            finally:
                midi_in_cc_console.close_port()
                sys.exit()
        
        # if -v, --verbose, or similar is passed as only argument
        elif "-v" in sys.argv[1] or "verbose" in sys.argv[1] or "debug" in sys.argv[1]:
            LOG_LEVEL = logging.DEBUG

    # Run the main function with LOG_LEVEL logging
    main(LOG_LEVEL)
