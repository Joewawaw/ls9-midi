#!/usr/bin/env python3
import time
import rtmidi

# Function to handle incoming MIDI messages
def handle_midi_message(event, data=None):
    message, delta_time = event

    # Check if the message is a Control Change (status byte is 0xB0 to 0xBF)
    if 0xB0 == message[0]:
        cc_messages.append(message)
#        print("Appended data "+ str(message))

    # Once we have 4 CC messages, process them
    if len(cc_messages) == 4:
        process_cc_messages(cc_messages)
        cc_messages.clear()  # Clear the list for the next batch of 4 messages

# Process the 4 collected CC messages
def process_cc_messages(messages):
#    print("Processing 4 CC messages:")
#    for msg in messages:
        # CC number is message[1], CC value is message[2]
#        print(f"CC Number: {msg[1]}, CC Value: {msg[2]}")
    # You can add your custom logic here, based on the message data
    #chekc if its an ON operation
    if messages[1][2] == 11:
        channel = int(messages[0][2]) - 53
        if messages[2][2]==0 and messages[3][2]==0:
            print("Channel "+str(channel)+ " OFF")
        elif messages[3][2]==127 and messages[3][2]==127:
            print("Channel "+str(channel)+ " ON")

# Setup the MIDI input
midi_in = rtmidi.MidiIn()
midi_in.open_port(0)  # Open the first available MIDI input port

# List to store CC messages
cc_messages = []

print("Waiting for MIDI CC messages...")

try:
    # Start receiving MIDI messages
    while True:
        msg = midi_in.get_message()
#### this line fixed it        
        time.sleep(0.01)
        if msg:
            handle_midi_message(msg)
except KeyboardInterrupt:
    print("Exiting...")

# Cleanup
midi_in.close_port()