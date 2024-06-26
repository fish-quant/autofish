# %% TEST SCRIPT for TLL synchronization
#  Python code to test the TTL synchronization.
#  If the provided Arduino code is used, the following pins are defined
#   12: TTL OUT: signal that imaging can be started
#   10: TTL IN: signal that imaging is done
#    7: set to high - can be used to imititate TTL that signals finished acquisition

# %%Importing Libraries
import serial
import time



# %% Connect to arduino and run a while loop 
arduino = serial.Serial(port='/dev/tty.usbmodem11301', baudrate=9600, timeout=1)

while True:
    i = input("start / exit:")

    print(i)
    if i == 'exit':
        print('finished program')
        break

    arduino.write((i + '\n').encode())
    time.sleep(0.25)

    if i == 'start':
        print('Will wait for acquitision to be done.')

        imaging = True
        while imaging:

            # Read from serial
            txt_serial = arduino.readline().decode('ascii').rstrip()
            print(f'Received serial txt: {txt_serial}')

            if txt_serial == 'finished':
                print('Acqusition seems to be terminated')
                imaging = False
            else:
                print('No termination command received')

            time.sleep(0.5)

arduino.close()

# %%
