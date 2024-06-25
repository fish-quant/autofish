
# %% TEST HARDWARE : PUMP : Longer BT100
# Allows to test if a robot controlled by GRBl (e.g. from Genmitsu) can be controlled
# - Python code to test if hardware can be accessed
# - Only parameter to change is COM port


# %% Imports
import serial

# %% Connect to serial port
ser = serial.Serial(port='COM9',
                    baudrate=1200,
                    parity=serial.PARITY_EVEN,
                    stopbits=serial.STOPBITS_ONE,
                    bytesize=serial.EIGHTBITS,
                    timeout=0.5)
print(ser.isOpen())


# %% Several helper functions


def send_command(ser_cmd):
    ser.write(bytes.fromhex(ser_cmd))


def xor_hex(h1, h2):
    return hex(int(h1, 16) ^ int(h2, 16))[2:]


def xor_cmd(ser_cmd):
    arr = ser_cmd.split()
    fcs = '0'
    for i in range(len(arr)):
        fcs = xor_hex(fcs, arr[i])
    return fcs


def speed_to_hex(speed):
    return int(speed*10).to_bytes(2, "big").hex(' ')

# %% Launch pump

# Parameters of pump
speed = 60
pump_start = False
pump_cw = False

# Construct control string : start/stop pump
if pump_start:
    str_start = '01'
else:
    str_start = '00'

# Turn clockwise / counter-clockwise
if pump_cw:
    str_cw = '01'
else:
    str_cw = '00'

speed_hex = speed_to_hex(speed)
ser_cmd = '1F 06 57 4A ' + speed_hex + ' ' + str_start + ' ' + str_cw

# Calculate fcs
fcs = xor_cmd(ser_cmd)
ser_cmd_complete = 'E9 ' + ser_cmd + ' ' + fcs
print(ser_cmd_complete)

# Send command
send_command(ser_cmd_complete)

# %%
