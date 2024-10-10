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
import bidict
import rtmidi

import time
import logging
import traceback
import sys

## TO DO:
# - implement a timeout on receiving 4 midi messages (they should all happen in rapid succession)
#   this will harden the midi receive machine
# - unit tests!
#   assert all is_ statements
#   assert channel out of bounds
#   assert simple midi cc filter 
#   assert invalid nrpn message
#   assert rx buffer timeout

#_OP means operation
#MIDI_ON_OFF_OP =             0x0B
#MIDI_FADE_OP   =             0x00
#MIDI_SEND_TO_MIX_OP =        0xFF
#MIDI_ST_LR_SEND_TO_MT_OP =   0xFF
#MIDI_PATCH_IN_OP =           0xFF
#MIDI_MONO_SEND_TO_MT_OP =    0xFF
#MIDI_MIX_PATCH_TO_ST_LR_OP = 0xFF
#MIDI_MIX_SEND_TO_MT_OP =     0xFF

MIDI_CH_ON_VALUE  = 0x3FFF
MIDI_CH_OFF_VALUE = 0x0000

#### fill these in!
MIDI_FADE_0DB_VALUE =    0xFF
MIDI_FADE_40DB_VALUE =   0xFF
MIDI_FADE_50DB_VALUE =   0xFF
MIDI_FADE_60DB_VALUE =   0xFF
MIDI_FADE_NEGINF_VALUE = 0xFF

MIDI_IN_PATCH_ON_VALUE =  0xFF
MIDI_IN_PATCH_OFF_VALUE = 0xFF

#MIDI defined constants for CC commands & NRPN sequence
MIDI_CC_CMD_BYTE = 0xB0
MIDI_NRPN_BYTE_1 = 0x62
MIDI_NRPN_BYTE_2 = 0x63
MIDI_NRPN_BYTE_3 = 0x06
MIDI_NRPN_BYTE_4 = 0x26

MIDI_ON_OFF_CONTROLLERS = bidict({
    "CH01" : 80, "CH02" : 80, "CH03" : 80, "CH04" : 80, "CH05" : 80, "CH06" : 80, "CH07" : 80, "CH08" : 80,
    "CH09" : 80, "CH10" : 80, "CH11" : 80, "CH12" : 80, "CH13" : 80, "CH14" : 80, "CH15" : 80, "CH16" : 80,
    "CH17" : 80, "CH18" : 80, "CH19" : 80, "CH20" : 80, "CH21" : 80, "CH22" : 80, "CH23" : 80, "CH24" : 80,
    "CH25" : 80, "CH26" : 80, "CH27" : 80, "CH28" : 80, "CH29" : 80, "CH30" : 80, "CH31" : 80, "CH32" : 80,

    "CH33" : 80, "CH34" : 80, "CH35" : 80, "CH36" : 80, "CH37" : 80, "CH38" : 80, "CH39" : 80, "CH40" : 80,
    "CH41" : 80, "CH42" : 80, "CH43" : 80, "CH44" : 80, "CH45" : 80, "CH46" : 80, "CH47" : 80, "CH48" : 80,
    "CH49" : 80, "CH50" : 80, "CH51" : 80, "CH52" : 80, "CH53" : 80, "CH54" : 80, "CH55" : 80, "CH56" : 80,
    "CH57" : 80, "CH58" : 80, "CH59" : 80, "CH60" : 80, "CH61" : 80, "CH62" : 80, "CH63" : 80, "CH64" : 80,

    "MIX1" : 80, "MIX2"  : 80, "MIX3"  : 80, "MIX4"  : 80, "MIX5"  : 80, "MIX6"  : 80, "MIX7"  : 80, "MIX8"  : 80,
    "MIX9" : 80, "MIX10" : 80, "MIX11" : 80, "MIX12" : 80, "MIX13" : 80, "MIX14" : 80, "MIX15" : 80, "MIX16" : 80,
    "MT1"  : 80, "MT2"   : 80, "MT3"   : 80, "MT4"   : 80, "MT5"   : 80, "MT6"   : 80, "MT7"   : 80, "MT8"   : 80,

    "ST-IN1" : 80, "ST-IN2" : 80, "ST-IN3" : 80, "ST-IN4" : 80, "ST LR" : 80, "MONO" : 80, "MON" : 80
})

MIDI_FADER_CONTROLLERS = bidict({
    "CH01" : 80, "CH02" : 80, "CH03" : 80, "CH04" : 80, "CH05" : 80, "CH06" : 80, "CH07" : 80, "CH08" : 80,
    "CH09" : 80, "CH10" : 80, "CH11" : 80, "CH12" : 80, "CH13" : 80, "CH14" : 80, "CH15" : 80, "CH16" : 80,
    "CH17" : 80, "CH18" : 80, "CH19" : 80, "CH20" : 80, "CH21" : 80, "CH22" : 80, "CH23" : 80, "CH24" : 80,
    "CH25" : 80, "CH26" : 80, "CH27" : 80, "CH28" : 80, "CH29" : 80, "CH30" : 80, "CH31" : 80, "CH32" : 80,

    "CH33" : 80, "CH34" : 80, "CH35" : 80, "CH36" : 80, "CH37" : 80, "CH38" : 80, "CH39" : 80, "CH40" : 80,
    "CH41" : 80, "CH42" : 80, "CH43" : 80, "CH44" : 80, "CH45" : 80, "CH46" : 80, "CH47" : 80, "CH48" : 80,
    "CH49" : 80, "CH50" : 80, "CH51" : 80, "CH52" : 80, "CH53" : 80, "CH54" : 80, "CH55" : 80, "CH56" : 80,
    "CH57" : 80, "CH58" : 80, "CH59" : 80, "CH60" : 80, "CH61" : 80, "CH62" : 80, "CH63" : 80, "CH64" : 80,

    "MIX1" : 80, "MIX2"  : 80, "MIX3"  : 80, "MIX4"  : 80, "MIX5"  : 80, "MIX6"  : 80, "MIX7"  : 80, "MIX8"  : 80,
    "MIX9" : 80, "MIX10" : 80, "MIX11" : 80, "MIX12" : 80, "MIX13" : 80, "MIX14" : 80, "MIX15" : 80, "MIX16" : 80,
    "MT1"  : 80, "MT2"   : 80, "MT3"   : 80, "MT4"   : 80, "MT5"   : 80, "MT6"   : 80, "MT7"   : 80, "MT8"   : 80,

    "ST-IN1" : 80, "ST-IN2" : 80, "ST-IN3" : 80, "ST-IN4" : 80, "ST LR" : 80, "MONO" : 80, "MON" : 80
})

MIDI_MIX1_MIX2_SENDS_ON_FADER_CONTROLLERS = bidict({
    "CH01" : 80, "CH02" : 80, "CH03" : 80, "CH04" : 80, "CH05" : 80, "CH06" : 80, "CH07" : 80, "CH08" : 80,
    "CH09" : 80, "CH10" : 80, "CH11" : 80, "CH12" : 80, "CH13" : 80, "CH14" : 80, "CH15" : 80, "CH16" : 80,
    "CH17" : 80, "CH18" : 80, "CH19" : 80, "CH20" : 80, "CH21" : 80, "CH22" : 80, "CH23" : 80, "CH24" : 80,
    "CH25" : 80, "CH26" : 80, "CH27" : 80, "CH28" : 80, "CH29" : 80, "CH30" : 80, "CH31" : 80, "CH32" : 80,

    "CH33" : 80, "CH34" : 80, "CH35" : 80, "CH36" : 80, "CH37" : 80, "CH38" : 80, "CH39" : 80, "CH40" : 80,
    "CH41" : 80, "CH42" : 80, "CH43" : 80, "CH44" : 80, "CH45" : 80, "CH46" : 80, "CH47" : 80, "CH48" : 80,
    "CH49" : 80, "CH50" : 80, "CH51" : 80, "CH52" : 80, "CH53" : 80, "CH54" : 80, "CH55" : 80, "CH56" : 80,
    "CH57" : 80, "CH58" : 80, "CH59" : 80, "CH60" : 80, "CH61" : 80, "CH62" : 80, "CH63" : 80, "CH64" : 80
})


MIDI_MIX16_SEND_TO_MT_CONTROLLERS = bidict({
    "MT1" : 80, "MT2" : 80, "MT3" : 80, "MT4" : 80, "MT5" : 80, "MT6" : 80, "MT7" : 80, "MT8" : 80
})

MIDI_MIX16_PATCH_TO_ST_LR = bidict({
    "ON" : 80, "OFF" : 81
})

# Patch in for "PC IN2" to ST-IN1,2 channel strips
MIDI_STIN1_PATCH_IN_CONTROLLERS = bidict({
    "CH21" : 80, "OFF" : 81
})
MIDI_STIN2_PATCH_IN_CONTROLLERS = bidict({
    "CH21" : 80, "OFF" : 81
})

MIDI_MON_DEFINE_IN = bidict({
    "CH31"  :  80, "CH32"  :  80
})

MIDI_ST_LR_SEND_TO_MT_CONTROLLERS = bidict({
    "MT1" : 80, "MT2" : 80, "MT3" : 80, "MT4" : 80, "MT5" : 80, "MT6" : 80, "MT7" : 80, "MT8" : 80
})
MIDI_MONO_SEND_TO_MT_CONTROLLERS = bidict({
    "MT1" : 80, "MT2" : 80, "MT3" : 80, "MT4" : 80, "MT5" : 80, "MT6" : 80, "MT7" : 80, "MT8" : 80
})

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
    # We use inverse() as the mapping is <ch_name> -> <controller_number>
    if ( MIDI_ON_OFF_CONTROLLERS.inverse[get_nrpn_controller(msg)] ) != None:
        return True
    return False
    

def is_fade_operation(msg):
    if ( MIDI_FADER_CONTROLLERS.inverse[get_nrpn_controller(msg)] ) != None:
        return True
    return False

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

def get_nrpn_controller(msg):
    return combine_bytes(msg[0][2], msg[1][2])

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
    channel = get_channel(messages)
    data = get_nrpn_data(messages)

    # Processing for Fade operations
    if is_fade_operation(messages):
        # We automate muting vocal mics on the monitor mix if they are lowered below -50dB, and snap back to 0dB if they go above -40dB (so a software schmitt trigger)
        if data < MIDI_FADE_60DB_VALUE:
            send_nrpn(midi_out, MIDI_MIX1_MIX2_SENDS_ON_FADER_CONTROLLERS[channel], MIDI_FADE_NEGINF_VALUE)
        elif data > MIDI_FADE_50DB_VALUE and data < MIDI_FADE_40DB_VALUE:
            send_nrpn(midi_out, MIDI_MIX1_MIX2_SENDS_ON_FADER_CONTROLLERS[channel], MIDI_FADE_0DB_VALUE)

    # Processing for ON/OFF message operations
    if is_on_off_operation(messages):
    #### Automation for CH01-CH10: When any on/off is pressed, the layer 33-64 duplicate is toggled the opposite state
        # if the channel is in the forward values of the mapping, it is one of the original channels. CH01-CH10
        if channel in CHORUS_CH_TO_LEAD_CH_MAPPING:
            #if the channel is switched ON, switch OFF the duplicate channel
            if get_on_off_data(messages) == True:
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
            if get_on_off_data(messages) == True:
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
    if len(sys.argv > 2):
        if sys.argv[1] == "console":
            midi_in =  rtmidi.MidiIn()
            midi_in.open_port(0)
            try:
                midi_console(midi_in)
            except KeyboardInterrupt:
                print("Exiting...")
            finally:
                midi_in.close_port()
                sys.exit()

    main()
