
#%% TEST HARDWARE : ROBOT : Genmitsu GRBL
# Allows to test if a robot controlled by GRBl (e.g. from Genmitsu) can be controlled
# - Python code to test if hardware can be accessed
# - Only parameter to change is COM port

# %% Imports
import serial


# %% Connect to serial port 
ser = serial.Serial(port = 'COM7',
                    baudrate = 115200,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                    bytesize=serial.EIGHTBITS,
                    timeout=1000)
print(ser.isOpen())
print('Robot connected on ',ser.name)


# %% Initiate and set status mask
ser.flushInput()
ser.write(('$10=2\n\r').encode('utf-8'))
grbl_out = ser.readline().decode('utf-8')
print('PLATE: set Status report mask: ' + grbl_out)

# %% Jog x-axis by 1mm
feed = 500
jog_axis = 'X'
jog_dist = 1
ser.write(('$J=G91 G21 '+jog_axis.upper()+str(jog_dist)+'F'+str(feed)+' \n').encode('utf-8'))  # Move code to GRBL, xy first
# %%
