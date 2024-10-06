#!/usr/bin/env python3

import time
import rtmidi
import logging

#_OP means operation
MIDI_ON_OFF_OP =             0x0B
MIDI_FADE_OP   =             0xFF
MIDI_SEND_TO_MIX_OP =        0xFF
MIDI_ST_LR_SEND_TO_MT_OP =   0xFF
MIDI_MONO_SEND_TO_MT_OP =    0xFF
MIDI_MIX_PATCH_TO_ST_LR_OP = 0xFF
MIDI_MIX_SEND_TO_MT_OP =     0xFF

MIDI_CH_ON_OP  = 0x7F
MIDI_CH_OFF_OP = 0x00

#MIDI defined constants for CC commands & NRPN sequence
MIDI_CC_CMD_BYTE = 0xB0
MIDI_NRPN_BYTE_1 = 0x62
MIDI_NRPN_BYTE_2 = 0x63
MIDI_NRPN_BYTE_3 = 0x06
MIDI_NRPN_BYTE_4 = 0x26

MIDI_CH_OFFSET = 53

# NPRN message structure for Yamaha LS9:
# CC cmd #   Byte 1   Byte 2   Byte 3
#        1   0xB0     0x62     <CHANNEL>
#        2   0xB0     0x63     <OPERATION>
#        3   0xB0     0x06     <DATA[0]>
#        4   0xB0     0x26     <DATA[1]>

def is_valid_nrpn_message(msg):
    if int(msg[0][1]) != MIDI_NRPN_BYTE_1 or int(msg[1][1]) != MIDI_NRPN_BYTE_2 or int(msg[2][1]) != MIDI_NRPN_BYTE_3 or int(msg[3][1]) != MIDI_NRPN_BYTE_4:
        raise ValueError("Incorrect NRPN MIDI data sequence! Message Dump: "+ str(msg))
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

    if  int(msg[2][2])==MIDI_CH_OFF_OP and int(msg[3][2])==MIDI_CH_OFF_OP:
        return False
    elif int(msg[3][2])==MIDI_CH_ON_OP and int(msg[3][2])==MIDI_CH_ON_OP:
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
    
    #remove the offset when sending out
    midi_output.send_message([MIDI_CC_CMD_BYTE, MIDI_NRPN_BYTE_1,  channel+MIDI_CH_OFFSET])
    midi_output.send_message([MIDI_CC_CMD_BYTE, MIDI_NRPN_BYTE_2,  operation])
    midi_output.send_message([MIDI_CC_CMD_BYTE, MIDI_NRPN_BYTE_3,  data[0]])
    midi_output.send_message([MIDI_CC_CMD_BYTE, MIDI_NRPN_BYTE_4,  data[1]])


# Process the 4 collected CC messages
def process_cc_messages(messages, midi_out):

    if is_fade_operation(messages):
        pass
        #logging.debug("MIDI IN: Channel "+str(get_channel(msg))+" fade to "+str(get_fade_data(messages)))

    ## Processing for ON/OFF message operations
    if is_on_off_operation(messages):
        channel = get_channel(messages)

        ## Automation for CH01-CH10: When any on/off is pressed, the layer 33-64 duplicate is toggled the opposite state
        if channel >= 1 and channel <= 10:
            #if the channel is switched ON, switch OFF the duplicate channel
            if get_on_off_data(messages) == True:
                logging.debug("MIXER IN: Channel "+str(channel)+" switched ON")
                channel += 32
                data = [MIDI_CH_OFF_OP, MIDI_CH_OFF_OP]
                logging.info("MIDI OUT: CH"+str(channel)+" OFF")
#                send_nrpn(midi_out, channel, MIDI_ON_OFF_OP, data)
            else:
                logging.debug("MIXER IN: Channel "+str(channel)+" switched OFF")
                channel += 32
                data = [MIDI_CH_ON_OP, MIDI_CH_ON_OP]
                logging.info("MIDI OUT: CH"+str(channel)+" ON")
#                send_nrpn(midi_out, channel, MIDI_ON_OFF_OP, data)
        
        elif channel >= 33 and channel <= 42:
            #if the channel is switched ON, switch OFF the original channel
            if get_on_off_data(messages) == True:
                logging.debug("MIXER IN: CH"+str(channel)+" switched ON")
                channel -= 32
                data = [MIDI_CH_OFF_OP, MIDI_CH_OFF_OP]
                logging.info("MIDI OUT: CH"+str(channel)+" OFF")
#                send_nrpn(midi_out, channel, MIDI_ON_OFF_OP, data)
            else:
                logging.debug("MIXER IN: CH"+str(channel)+" switched OFF")
                channel -= 32
                data = [MIDI_CH_ON_OP, MIDI_CH_ON_OP]
                logging.info("MIDI OUT: CH"+str(channel)+" ON")
#                send_nrpn(midi_out, channel, MIDI_ON_OFF_OP, data)

#This code is event based, it will only trigger upon receiving a message from the mixer
def main():
    LOG_LEVEL = logging.DEBUG


    # Setup the MIDI input & output
    midi_in = rtmidi.MidiIn()
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

        msg, timestamp = midi_in.get_message()

        if msg:
            # Filter out everything but CC (Control Change) commands
            if msg[0] == MIDI_CC_CMD_BYTE:
                cc_messages.append(msg)
                logging.debug("Received CC command "+ str(msg))

            # Once we have 4 CC messages, process them
            if len(cc_messages) == 4:
                try:
                    process_cc_messages(cc_messages, midi_out)
                except ValueError as e:
                    logging.error(e.msg + e.args)
                finally:
                    cc_messages.clear()  # Clear the list for the next batch of 4 messages


if __name__ == '__main__':
    main()
