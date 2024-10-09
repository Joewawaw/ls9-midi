#!../bin/python3

#this requires a python venv with python-rtmidi installed
import time
import rtmidi
import logging
import traceback

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
MIDI_ON_OFF_OP =             0x0B
MIDI_FADE_OP   =             0x00
MIDI_SEND_TO_MIX_OP =        0xFF
MIDI_ST_LR_SEND_TO_MT_OP =   0xFF
MIDI_PATCH_IN_OP =           0xFF
MIDI_MONO_SEND_TO_MT_OP =    0xFF
MIDI_MIX_PATCH_TO_ST_LR_OP = 0xFF
MIDI_MIX_SEND_TO_MT_OP =     0xFF

MIDI_CH_ON_VALUE  = 0x7F
MIDI_CH_OFF_VALUE = 0x00
#### fill these in!
MIDI_FADE_0DB_MIX_SEND_VALUE =  0xFF
MIDI_FADE_NEGINF_MIX_SEND_VALUE = 0xFF


#MIDI defined constants for CC commands & NRPN sequence
MIDI_CC_CMD_BYTE = 0xB0
MIDI_NRPN_BYTE_1 = 0x62
MIDI_NRPN_BYTE_2 = 0x63
MIDI_NRPN_BYTE_3 = 0x06
MIDI_NRPN_BYTE_4 = 0x26

MIDI_CH_OFFSET =   0x35

#### fill these in!
MIDI_ST_IN1_CH = 81
MIDI_ST_IN2_CH = 82
MIDI_ST_IN3_CH = 83
MIDI_ST_IN4_CH = 84
MIDI_MIX16_CHANNEL = 90
MIDI_MT3_CHANNEL = 91

#### fill these in!
MIDI_FADE_0DB_VALUE =    0xFF
MIDI_FADE_40DB_VALUE =   0xFF
MIDI_FADE_50DB_VALUE =   0xFF
MIDI_FADE_NEGINF_VALUE = 0xFF


WIRELESS_MC_TO_CHR_MAPPING = [
    (11, 47), 
    (12, 48), 
    (13, 49),
    (14, 50)
]

WIRELESS_MC_TO_LEAD_MAPPING = [
    (11, 43), 
    (12, 44), 
    (13, 45),
    (14, 46)
]

WIRELESS_CHR_TO_LEAD_MAPPING = [
    (47, 43), 
    (48, 44), 
    (49, 45),
    (50, 46)
]

#these two functions are the getters to the lists of tuples above.
def get_second_elem(pairs, first):
    return next((second for f, second in pairs if f == first), None)

def get_first_elem(pairs, second):
    return next((first for first, s in pairs if s == second), None)


# NPRN message structure for Yamaha LS9:
# CC cmd #   Byte 1   Byte 2   Byte 3
#        1   0xB0     0x62     <CHANNEL>
#        2   0xB0     0x63     <OPERATION>
#        3   0xB0     0x06     <DATA[0]>
#        4   0xB0     0x26     <DATA[1]>

def is_valid_nrpn_message(msg):
    if int(msg[0][1]) != MIDI_NRPN_BYTE_1 or int(msg[1][1]) != MIDI_NRPN_BYTE_2 or int(msg[2][1]) != MIDI_NRPN_BYTE_3 or int(msg[3][1]) != MIDI_NRPN_BYTE_4:
        raise ValueError(f"Invalid NRPN MIDI data sequence! MIDI Message Dump: {msg}")
    return True

def is_on_off_operation(msg):
    if int(msg[1][2]) == MIDI_ON_OFF_OP:
        return True
    return False

def is_fade_operation(msg):
    if int(msg[1][2]) == MIDI_FADE_OP:
        return True
    return False

def get_channel(msg):
    channel = int(msg[0][2])
    real_channel = channel - MIDI_CH_OFFSET
    return real_channel

#returns the state on the on/off button press, True = OFF->ON, False = ON->OFF
def get_on_off_data(msg):
    if not is_on_off_operation(msg):
        raise ValueError("Message is not an ON/OFF operation!")

    if  int(msg[2][2])==MIDI_CH_OFF_VALUE and int(msg[3][2])==MIDI_CH_OFF_VALUE:
        return False
    elif int(msg[3][2])==MIDI_CH_ON_VALUE and int(msg[3][2])==MIDI_CH_ON_VALUE:
        return True
    
def get_fade_data(msg):
    if not is_fade_operation(msg):
        raise ValueError("Message is not a fade operation!")

    return combine_bytes(msg[2][2], msg[3][2])

def combine_bytes(msb, lsb):
    return (msb << 8) | lsb

#data is a 2 list array
def send_nrpn(midi_output, channel, operation, data):
    if len(data) != 2:
        raise ValueError("<data> is not a 2 element list!")
    
    if channel > 64 or channel < 1:
        raise ValueError("<channel> is out of bounds!")
    
    if operation != MIDI_ON_OFF_OP and operation != MIDI_FADE_OP:
        raise ValueError("<operation> is invalid!")
    
    #remove the channel offset when sending out
    midi_output.send_message([MIDI_CC_CMD_BYTE, MIDI_NRPN_BYTE_1,  channel+MIDI_CH_OFFSET])
    midi_output.send_message([MIDI_CC_CMD_BYTE, MIDI_NRPN_BYTE_2,  operation])
    midi_output.send_message([MIDI_CC_CMD_BYTE, MIDI_NRPN_BYTE_3,  data[0]])
    midi_output.send_message([MIDI_CC_CMD_BYTE, MIDI_NRPN_BYTE_4,  data[1]])


# Process the 4 collected CC messages
def process_cc_messages(messages, midi_out):
    ## Processing for Fade operations
    if is_fade_operation(messages):
        #logging.debug(f"MIDI IN: CH{get_channel(messages)} fade to {get_fade_data(messages)}")
        pass
        # We automate muting vocal mics on the monitor mix if they are lowered below -50dB, and snap back to 0dB if they go above -40dB (so a software schmitt trigger)
        if get_fade_data(channel) < MIDI_FADE_50DB_VALUE:
            send_nrpn(midi_out, channel, MIDI_FADE_OP, [MIDI_FADE_NEGINF_VALUE, MIDI_FADE_NEGINF_VALUE])
        elif get_fade_data(channel) > MIDI_FADE_40DB_VALUE:
            send_nrpn(midi_out, channel, MIDI_FADE_OP, [MIDI_FADE_0DB_VALUE, MIDI_FADE_0DB_VALUE])

    ## Processing for ON/OFF message operations
    if is_on_off_operation(messages):
        channel = get_channel(messages)

        ## Automation for CH01-CH10: When any on/off is pressed, the layer 33-64 duplicate is toggled the opposite state
        if channel >= 1 and channel <= 10:
            #if the channel is switched ON, switch OFF the duplicate channel
            if get_on_off_data(messages) == True:
                logging.debug(f"MIXER IN: CH{channel} switched ON")
                #get the upper layer channel by adding 32
                channel += 32
                #use the MIDI_CH_OFF_VALUE constant in the data block
                logging.info(f"MIDI OUT: CH{channel} OFF")
                send_nrpn(midi_out, channel, MIDI_ON_OFF_OP, [MIDI_CH_OFF_VALUE, MIDI_CH_OFF_VALUE])
            else:
                logging.debug(f"MIXER IN: CH{channel} switched OFF")
                channel += 32
                logging.info(f"MIDI OUT: CH{channel} ON")
                send_nrpn(midi_out, channel, MIDI_ON_OFF_OP, [MIDI_CH_ON_VALUE, MIDI_CH_ON_VALUE])
        elif channel >= 33 and channel <= 42:
            #if the duplicate channel is switched ON, switch OFF the original channel
            if get_on_off_data(messages) == True:
                logging.debug(f"MIXER IN: CH{channel} switched ON")
                #get the lower layer channel by subtracting 32
                channel -= 32
                logging.info(f"MIDI OUT: CH{channel} OFF")
                send_nrpn(midi_out, channel, MIDI_ON_OFF_OP, [MIDI_CH_OFF_VALUE, MIDI_CH_OFF_VALUE])
            else:
                logging.debug(f"MIXER IN: CH{channel} switched OFF")
                channel -= 32
                logging.info(f"MIDI OUT: CH{channel} ON")
                send_nrpn(midi_out, channel, MIDI_ON_OFF_OP, [MIDI_CH_ON_VALUE, MIDI_CH_ON_VALUE])
        
        
        ## Automation for Wireless M.C. Mics
        ## handling switch presses on the WL MC channels
        elif channel >=11 and channel <= 14:
            chr_channel = get_second_elem(WIRELESS_MC_TO_CHR_MAPPING, channel)
            lead_channel = get_second_elem(WIRELESS_MC_TO_LEAD_MAPPING, channel)
            # If Wireless MC CH N switched ON, then turn off WLCHR N & LEADWL N
            if get_on_off_data(messages) == True:
                send_nrpn(midi_out, chr_channel, MIDI_ON_OFF_OP, [MIDI_CH_OFF_VALUE, MIDI_CH_OFF_VALUE])
                send_nrpn(midi_out, lead_channel, MIDI_ON_OFF_OP, [MIDI_CH_OFF_VALUE, MIDI_CH_OFF_VALUE])
            # If Wireless MC CH N switched off, then switch on WLCHR N and turn off LEADWL N
            else:
                send_nrpn(midi_out, chr_channel, MIDI_ON_OFF_OP, [MIDI_CH_ON_VALUE, MIDI_CH_ON_VALUE])
                send_nrpn(midi_out, lead_channel, MIDI_ON_OFF_OP, [MIDI_CH_OFF_VALUE, MIDI_CH_OFF_VALUE])

        ## handling switch presses on the LEADWL channels
        elif channel >=43 and channel <= 46:
            mc_channel = get_first_elem(WIRELESS_MC_TO_LEAD_MAPPING, channel)
            chr_channel = get_first_elem(WIRELESS_CHR_TO_LEAD_MAPPING, channel)
            # If LEADWL CH N switched ON, then turn off WLCHR N & WLMC N
            if get_on_off_data(messages) == True:
                send_nrpn(midi_out, chr_channel, MIDI_ON_OFF_OP, [MIDI_CH_OFF_VALUE, MIDI_CH_OFF_VALUE])
                send_nrpn(midi_out, mc_channel, MIDI_ON_OFF_OP, [MIDI_CH_OFF_VALUE, MIDI_CH_OFF_VALUE])
            # If LEADWL CH N switched off, then switch on WLCHR N & turn off WLMC N
            else:                
                send_nrpn(midi_out, chr_channel, MIDI_ON_OFF_OP, [MIDI_CH_ON_VALUE, MIDI_CH_ON_VALUE])
                send_nrpn(midi_out, mc_channel, MIDI_ON_OFF_OP, [MIDI_CH_OFF_VALUE, MIDI_CH_OFF_VALUE])

        ## handling switch presses on the WLCHR channels
        elif channel >=43 and channel <= 46:
            mc_channel = get_first_elem(WIRELESS_MC_TO_CHR_MAPPING, channel)
            lead_channel = get_second_elem(WIRELESS_CHR_TO_LEAD_MAPPING, channel)
            # If WLCHR CH N switched ON, then turn off LEADWL N & WLMC N
            if get_on_off_data(messages) == True:                
                send_nrpn(midi_out, mc_channel, MIDI_ON_OFF_OP, [MIDI_CH_OFF_VALUE, MIDI_CH_OFF_VALUE])
                send_nrpn(midi_out, lead_channel, MIDI_ON_OFF_OP, [MIDI_CH_OFF_VALUE, MIDI_CH_OFF_VALUE])
            # If WLCHR CH N switched off, then switch on LEADWL N and turn off WLMC N
            else:
                send_nrpn(midi_out, lead_channel, MIDI_ON_OFF_OP, [MIDI_CH_ON_VALUE, MIDI_CH_ON_VALUE])
                send_nrpn(midi_out, mc_channel, MIDI_ON_OFF_OP, [MIDI_CH_OFF_VALUE, MIDI_CH_OFF_VALUE])

        #Automation for ST-IN channels: we reroute LINE 2 to LOBBY or BASMNT, and activate/deactivate WLTKBK
        elif channel == MIDI_ST_IN1_CH:
            # if ST-IN1 was switched ON, route LINE 2 to BASMNT, and patch PC IN2 to ST-IN1
            if get_on_off_data(messages) == True:
                send_nrpn(midi_out, MIDI_MIX16_CHANNEL, MIDI_MIX_SEND_TO_MT_OP, [0x00, 0x00])
                send_nrpn(midi_out, MIDI_ST_IN1_CH, MIDI_PATCH_IN_OP, [0x00, 0x00])
            # if switched off, patch MONO to BASMNT and unpatch ST-IN1
            else:
                send_nrpn(midi_out, MIDI_MIX16_CHANNEL, MIDI_MIX_SEND_TO_MT_OP, [0x00, 0x00])
                send_nrpn(midi_out, MIDI_MT3_CHANNEL, MIDI_MONO_SEND_TO_MT_OP, [0x00, 0x00])
                send_nrpn(midi_out, MIDI_ST_IN1_CH, MIDI_PATCH_IN_OP, [0x00, 0x00])

        elif channel == MIDI_ST_IN2_CH:
            # if ST-IN2 was switched ON, route LINE 2 to LOBBY, and patch PC IN2 to ST-IN2
            if get_on_off_data(messages) == True:
                send_nrpn(midi_out, MIDI_MIX16_CHANNEL, MIDI_MIX_SEND_TO_MT_OP, [0x00, 0x00])
                send_nrpn(midi_out, MIDI_ST_IN1_CH, MIDI_PATCH_IN_OP, [0x00, 0x00])
            else:
                send_nrpn(midi_out, MIDI_MIX16_CHANNEL, MIDI_MIX_SEND_TO_MT_OP, [0x00, 0x00])
                send_nrpn(midi_out, MIDI_ST_IN1_CH, MIDI_PATCH_IN_OP, [0x00, 0x00])






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
    
    logging.info("Waiting for MIDI CC messages...")

    cc_messages = []
    while True:
        #delay is necessary to not overload the CPU or RAM
        time.sleep(0.01)

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
                   cc_messages.clear()  # Clear the list for the next batch of 4 messages

def midi_console():
    # Setup the MIDI input & output
    midi_in =  rtmidi.MidiIn()
    midi_out = rtmidi.MidiOut()

    midi_in.open_port(0)
    midi_out.open_port(0)
    
    cc_messages = []
    while True:
        #delay is necessary to not overload the CPU or RAM
        time.sleep(0.01)

        #get the raw data from the midi get_message function. It will either return None, or a 2 element list
        midi_msg = midi_in.get_message()

        if midi_msg != None:
            messages = midi_msg[0] #get the message packet, the other entry (midi_msg[1]) is the timestamp in unix time
            # Filter out everything but CC (Control Change) commands
            if messages[0] == MIDI_CC_CMD_BYTE:
                cc_messages.append(messages)
            # Once we have 4 CC messages, process them
            if len(cc_messages) == 4:
                try:
                    logging.info(f"Channel: {msg[0][2]} Operation: {msg[1][2]} Data: {msg[2][2]} {msg[3][2]}")
                except ValueError as e:
                    error_message = traceback.format_exc()
                    logging.error(error_message)
                    logging.error(str(e))

                finally:
                   cc_messages.clear()  # Clear the list for the next batch of 4 messages


if __name__ == '__main__':
    main()
