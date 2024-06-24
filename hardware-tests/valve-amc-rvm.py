#%% TEST HARDWARE : VALVE : HAMILTON MVP
# - Python code to test if hardware can be accessed
# - Only parameter to change is COM port

# %% Imports
import time
import serial

# %% Connect to serial port 
rvm = serial.Serial(port = 'COM8',
                    baudrate = 9600,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                    bytesize=serial.EIGHTBITS,
                    timeout=1000)
print(rvm.isOpen())
print('RVM connected on ',rvm.name)

#%% Initiate valve according to user guide
rvm.write(b"/1ZR\r")
time.sleep(5)
print('RVM ready')


#%% Go to port 3
# /1 ... command start
#  B ... Move to port wiht shortest path movement
#  6 ...  go to port 6
#  R  ... command end
rvm.write(b"/1B6R\r")
print('RVM ready')

# %%
