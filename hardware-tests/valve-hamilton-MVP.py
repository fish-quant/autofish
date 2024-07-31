#%% TEST HARDWARE : VALVE : HAMILTON MVP
# - Python code to test if hardware can be accessed
# - Only parameter to change is COM port

# %% imports
import time
import serial

# %% Connect to valve 
ser_v1 = serial.Serial(port = 'COM9',
                    baudrate = 9600,
                    parity=serial.PARITY_EVEN,
                    stopbits=serial.STOPBITS_ONE,
                    bytesize=serial.EIGHTBITS,
                    timeout=0.5)
print(ser_v1.isOpen())

#%% Initiate valve according to user guide
#   NOTE: if properly working, you should hear some noise from the valve
valve_id=1
ser_cmd = '/{}h30001R\r'.format(valve_id)  # Enable h-factor commands
ser_v1.write(ser_cmd.encode('utf-8'))
ser_cmd = '/{}h20000R\r'.format(valve_id)  # Initialize valve
ser_v1.write(ser_cmd.encode('utf-8'))
ser_cmd = '/{}h10001R\r'.format(valve_id)
ser_v1.write(ser_cmd.encode('utf-8'))
ser_cmd = '/{}h21003R\r'.format(valve_id)
ser_v1.write(ser_cmd.encode('utf-8'))


# %% Change valve position
#  This should again make some noise when the valve moves to another position
valve_id = 1
valve_pos = 7
ser_cmd = '/{}h2600{}R\r'.format(valve_id, valve_pos)
ser_v1.write(ser_cmd.encode('utf-8'))
# %%
