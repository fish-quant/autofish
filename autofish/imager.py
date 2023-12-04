# Instruction for how to set up pycromanger: https://pycro-manager.readthedocs.io/en/stable/setup.html

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------

import numpy as np
import logging
import time
import yaml
import json
import serial
from threading import Event
import gc
from pathlib import Path


try:
    from pycromanager import Core
    from pycromanager import Acquisition, multi_d_acquisition_events, start_headless
except ImportError:
    print('Pyrcomanger is not existing, please install if required!')

# ---------------------------------------------------------------------------
# Parental class
# ---------------------------------------------------------------------------


class Microscope:
    def __init__(self, logger=None, logger_short=None):

        # Setup logger
        if isinstance(logger, type(None)):
            self.logger = logging.getLogger('AUTOMATOR-Robot')  # Logs the name of the function
            self.logger.setLevel(100)
        else:
            self.logger = logger

        if isinstance(logger_short, type(None)):
            self.logger_short = logging.getLogger('AUTOMATOR-Microscope')  # Logs the name of the function
            self.logger_short.setLevel(100)
        else:
            self.logger_short = logger_short

    def _type(self):
        return self.__class__.__name__

    def acquire_images(self):
        """acquire_images _summary_
        """
        pass

    # Function to handle both logging calls and different logging types
    def log_msg(self, type, msg, msg_short=''):
        """log_msg _summary_

        Args:
            type (_type_): _description_
            msg (_type_): _description_
            msg_short (str, optional): _description_. Defaults to ''.
        """
        if type == 'info':
            self.logger.info(msg)
            if msg_short:
                self.logger_short.info(msg_short)
            else:
                self.logger_short.info(msg)

        elif type == 'error':
            self.logger.error(msg)
            if msg_short:
                self.logger_short.error(msg_short)
            else:
                self.logger_short.error(msg)  


# ---------------------------------------------------------------------------
# Control with pycromanager
# ---------------------------------------------------------------------------
# https://github.com/micro-manager/pycro-manager


class pycroManager(Microscope):

    def __init__(self, logger=None, logger_short=None):

        # Involve the init function of the parent class
        super().__init__(logger, logger_short)

        # For threading
        self.stop = Event()

        # Other parameters
        self.config = []
        self.positions = []

        # Robot status flags
        self.status = {
            'micromanger_connect': False,
            'config': False,
            'positions': False,
            'acquisition_event': False
        }

    # Read config file
    def load_config_file(self, file_config):
        """load_config_file _summary_

        Args:
            file_config (_type_): _description_
        """
        with open(file_config) as file:
            config_load = yaml.load(file, Loader=yaml.FullLoader)    
            self.config = config_load['microscope']

        # Set time-out
        if 'timeout' in self.config:
            self.timeout = self.config['timeout']
        else:
            self.timeout = 500

        self.status['config'] = True
        self.log_msg('info', f'Microscope config loaded: {self.config}.')

        # Reset acquisition event flag
        self.status['acquisition_event'] = False

    # Read config file
    def mm_connect(self, mm_headless=True):
        """mm_connect _summary_

        Args:
            mm_headless (_type_): _description_
        """
        # Connect to micromanager
        #  ToDo: allow headles start
        try:
            if mm_headless:

                mm_app_path = self.config['mm_app_path']
                config_file = str(Path(self.config['mm_app_path'], self.config['mm_config_file']))

                if Path(mm_app_path).is_dir() and Path(config_file).is_file():
                    start_headless(mm_app_path, config_file)
                else:
                    self.log_msg('error',f'MM configuration file/path does not exist: {config_file}!')
            else:
                self.core = Core()

            self.status['micromanger_connect'] = True
            self.log_msg('info', 'Communction with micromanager etablished.')

        except Exception as e:
            self.log_msg('error', f'Could not connect to micromanger ({e}).')

    # Read config file with some settings
    def load_position_list(self, file_pos=None):
        """load_position_list _summary_

        For Nikon
         - xy: TIXYDrive
         - z (regular stage): TIZDrive
         - z (pietzo): TIZDrive

        Args:
            file_pos (_type_): _description_
        """

        self.log_msg('info', f'Reading position list for microscope type {self.config["type"]}')

        # For demo
        if self.config['type'] == 'Demo':
            x = np.arange(0, 5)
            y = np.arange(0, -5, -1)
            z = np.arange(0, 5)
            self.positions = np.hstack([x[:, None], y[:, None], z[:, None]])

        # Nikon TI
        elif self.config['type'] == 'NIKON_TI':

            # Read file
            with open(file_pos) as f:
                data = json.load(f)

            x = []
            y = []
            z = []

            # Loop over all different saved positions
            for settings_position in data['map']['StagePositions']['array']:

                # For a given position, loop over tifferent axes
                for settings_axes in settings_position['DevicePositions']['array']:
                    axes_type = settings_axes['Device']['scalar']

                    # Extract xy coordinates
                    if axes_type == self.config['xy_drive_name']:
                        xy_loop = settings_axes['Position_um']['array']
                        x.append(xy_loop[0])
                        y.append(xy_loop[1])

                    # Extract z coordinates
                    elif axes_type == self.config['z_drive_name']:
                        z_loop = settings_axes['Position_um']['array']
                        z.append(z_loop[0])

            self.log_msg('info', f'x : {x}')
            self.log_msg('info', f'y : {y}')
            self.log_msg('info', f'z : {z}')

            # Check that if z-positions are defined, they are defined for every xy position
            n_x = len(x)
            n_z = len(z)

            if n_z > 0 and n_x != n_z:
                self.log_msg('error', 'Problem with position list. Not every xy position has a z position')
                return

            # Create array with xyz positions
            x = np.asarray(x)
            y = np.asarray(y)
            z = np.asarray(z)
            self.positions = np.hstack([x[:, None],  y[:, None], z[:, None]])

        self.status['positions'] = True

        # Reset acquisition event flag
        self.status['acquisition_event'] = False

    # Create the acquisition event with the specified parameters in the config file
    def create_acquisition_event(self):
        """create_acquisition_event _summary_
        """
        # Actual acquisition event
        self.event = multi_d_acquisition_events(
            channel_group=self.config['channel_group'],
            channels=self.config['channels'],
            channel_exposures_ms=self.config['channel_exposures_ms'],
            xyz_positions=self.positions,
            z_start=self.config['z_start'],
            z_end=self.config['z_end'],
            z_step=self.config['z_step'])

        # - Create a blank acquisition event
        #     Can be necessary to turn off light on certain systems
        self.event_blank = None
        if 'channel_blank' in self.config.keys():

            self.event_blank = multi_d_acquisition_events(
                channel_group=self.config['channel_group'],
                channels=[self.config['channel_blank']],
                channel_exposures_ms=[0],
                xyz_positions=np.asarray([self.positions[0]]))

        self.status['acquisition_event'] = True
        self.log_msg('info', 'Multi-D acquisition event created.')

    def acquire_images(self, dir_save, name_base='test'):
        """acquire_images _summary_

        Args:
            dir_save (_type_): _description_
            name_base (str, optional): _description_. Defaults to 'test'.
        """

        # Regular acquisition
        self.log_msg('info', 'Start acquisition.')
        with Acquisition(directory=dir_save, name=name_base, show_display=False, timeout=self.timeout) as acq:
            self.log_msg('info', f'Acquisition will be saved as: {acq._dataset_disk_location}')
            acq.acquire(self.event)
        del acq
        gc.collect()

        # Blank acquisition
        if self.event_blank:
            self.log_msg('info', 'Start blank acquisition.')
            with Acquisition(directory=dir_save, name='_delete_blank', show_display=False, timeout=self.timeout) as acq:
                self.log_msg('info', f'Acquisition will be saved as: {acq._dataset_disk_location}')
                acq.acquire(self.event_blank)
            del acq
            gc.collect()

        self.log_msg('info', 'End of acquisition')


# ------------------------------------------------------------------------------------------------
# Control with sync file : existing file, 1 to start acquisition, 0 to signal acquisition is done
# ------------------------------------------------------------------------------------------------


class TTL_sync(Microscope):
    def __init__(self, **kargs):

        # Involve the init function of the parent class
        super().__init__(**kargs)

        # For threading
        self.stop = Event()

        # Robot status flags
        self.status = {
        }

    def connect_serial_port(self, file_config_TTL):
        """ Load json file with configuration of serial communication with Arduino for TTL synchronization.

        Args:
            file_config_TTL (_type_): _description_
        """

        # Load file
        with open(file_config_TTL) as json_file:
            config_TLL = json.load(json_file)
        self.log_msg('info', 'Config file for TTL loaded')

        # Connect to port
        try:
            ser = serial.Serial(port=config_TLL['TTL']['COM'],
                                baudrate=config_TLL['TTL']['baudrate'],
                                #parity=config_TLL['TTL']['parity'],
                                stopbits=serial.STOPBITS_ONE,
                                bytesize=serial.EIGHTBITS,
                                timeout=0.5)
            config_TLL['TTL']['ser'] = ser
            self.log_msg('info', '  Connected to Arduino')

        except serial.SerialException as e:
            self.log_msg('error', f'  ERROR when opening serial port: {e}')

        self.config_TLL = config_TLL

    def acquire_images(self):
        """acquire_images _summary_
        """

        # Start acquisition by sending command to serial port
        # send 'Start acquisition'
        self.config_TLL['TTL']['ser'].write(('start' + '\n').encode())

        # Read from serial port until acquisition is done
        self.log_msg('info', 'Checking TTL for completion')

        imaging = True

        while imaging:

            # Read from serial
            txt_serial = self.config_TLL['TTL']['ser'].readline().decode('ascii').rstrip()
            # self.log_msg('info', f'Serial received {txt_serial}')

            if txt_serial == 'finished':
                self.log_msg('info', 'Acqusition seems to be terminated')
                imaging = False

            time.sleep(0.1)

    def close_serial_port(self):
        """_summary_
        """
        if 'ser' in self.config_TLL['TTL'].keys():
            ser = self.config_TLL['TTL']['ser']
            if ser is not None:
                if ser.isOpen() is True:
                    ser.close()


# ------------------------------------------------------------------------------------------------
# Control with sync file : existing file, 1 to start acquisition, 0 to signal acquisition is done
# ------------------------------------------------------------------------------------------------


class fileSync_write(Microscope):
    def __init__(self, **kargs):

        # Involve the init function of the parent class
        super().__init__(**kargs)

        # For threading
        self.stop = Event()

        # Robot status flags
        self.status = {
        }

    def initiate_sync_file(self, name_sync_file):
        """initiate_sync_file _summary_

        Args:
            name_sync_file (_type_): _description_
        """
        with open(name_sync_file, 'w') as f:
            f.write('0')
        self.name_sync_file = name_sync_file
        self.log_msg('info', f'Acquisition sync file initiated {name_sync_file}')

    def acquire_images(self):
        """acquire_images _summary_
        """
        # Start acquisition by setting file content to 1
        with open(self.name_sync_file, 'w') as f:
            f.write('1')

        # Read status of sync file
        self.log_msg('info', 'Checking sync file for completion')

        syncfile = open(self.name_sync_file, "r")
        imaging = True
        while imaging:
            tmp = syncfile.read()
            syncfile.seek(0, 0)  # Reset position to beginning of file

            if (tmp == 0) or (tmp == '0'):
                self.log_msg('info', 'Acqusition seems to be terminated')
                imaging = False

            time.sleep(0.5)

        syncfile.close()


# ------------------------------------------------------------------------------------------------
# Control with sync file : existing file, 1 to start acquisition, 0 to signal acquisition is done
# ------------------------------------------------------------------------------------------------


class fileSync_create(Microscope):
    def __init__(self, **kargs):

        # Involve the init function of the parent class
        super().__init__(**kargs)

        self.sync_file = None

        # For threading
        self.stop = Event()

        # Robot status flags
        self.status = {
        }

    def initiate_sync_file(self, path_sync_file, name_sync_file):
        """_summary_

        Args:
            path_sync_file (_type_): _description_
            name_sync_file (_type_): _description_
        """
        self.path_sync_file = path_sync_file
        self.name_sync_file = name_sync_file

        sync_file = Path(path_sync_file, name_sync_file)
        if sync_file.exists():
            err_txt = f'Sync file already exists, please delete {str(sync_file)}'
            self.log_msg('error', err_txt)
            sync_file = err_txt
        else:
            self.log_msg('info', f'Acquisition sync file initiated {str(sync_file)}')
            self.sync_file = sync_file

        return sync_file

    def acquire_images(self):
        """acquire_images _summary_
        """

        with open(str(self.sync_file), 'w') as f:
            f.write('Temporary file to intiate acquisition!')

        # Check if file exists
        self.log_msg('info', 'Checking exisstance of sync file')
        imaging = True

        while imaging:

            if not self.sync_file.exists():
                self.log_msg('info', 'Acqusition seems to be terminated')
                imaging = False
            time.sleep(0.5)
