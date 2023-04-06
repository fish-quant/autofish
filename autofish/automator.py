# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------

import serial
import time
from serial.tools.list_ports import comports
import re
import json
import yaml
import logging
import time
from datetime import datetime
import math
from threading import Event
from itertools import compress
import os
import numpy as np
import csv
from pathlib import Path

# ---------------------------------------------------------------------------
#  ROBOT class: manages the entire fluidics system
# ---------------------------------------------------------------------------

class Robot():
    """
    == demo mode
    Can be use in "demo" mode (via the fluidics_config.json file). Here, no connection
    to the fluidics components are established and runs times as set to a minimum. Permits
    to test if the code itself runs without errors. 
    """
    def __init__(self, config_file_system, logger=None, logger_short=None, demo=False):
        
        # Robot status flags
        self.status = {
            'demo': False,
            'ports_assigned': False,
            'robot_zeroed': False,
            'experiment_config': False,
            'buffer_selected': False,
            'ready': False,
            'launch_acquisition': True      # Should images be acquired after the completion of this round
        }
        
        # Setup logger
        if isinstance(logger, type(None)):
            self.logger = logging.getLogger('AUTOMATOR-Robot')  # Logs the name of the function
            self.logger.setLevel(100)
        else:
             self.logger = logger
        
        if isinstance(logger_short, type(None)):
            self.logger_short = logging.getLogger('AUTOMATOR-Robot')  # Logs the name of the function
            self.logger_short.setLevel(100)
        else:
             self.logger_short = logger_short

        # Enable demo mode
        if demo:
            self.log_msg('info', f"Demo mode ON")
            self.status['demo'] = True

        # For threading
        self.stop = Event()

        # flow measurements
        self.flow = {
            'verify': False,
            'expected': None,
            'tolerance': None
        }

        self.volume_measurements = []
        self.volume_measurements.append(['Time','round','buffer','duration','vol_expected','vol_measured'])

        # General robot configuration
        self.config_file_experiment = []
        self.experiment_config = {}
        self.buffer_names = []
        self.current_buffer = None
        self.current_round = 'NA'
        self.file_volume_measurements = None

        # Load robot configuration (but don't initiate the components) 
        self.config_file_system = config_file_system
        self.config_system = self.load_config_system()
        
        # Finished
        self.log_msg('info', 'Robot ready to be initiated.')

    # Function to handle both logging calls and different logging types
    def log_msg(self,type, msg, msg_short=''):
        """log_msg _summary_

        Args:
            type (_type_): _description_
            msg (str): _description_
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
        
    # Pause for specifid duration in seconds
    def pause(self, sleep_time):
        """ Pauses robot for indicated duration in seconds.

        Args:
            sleep_time (int): time to sleep in seconds.
        """        

        time.sleep(int(sleep_time))
        self.logger.info('Paused for '+str(sleep_time))


    def verify_flow(self, duration, volume_measured):
        """ Verifies measured flow against the expected flow.

        Args:
            flow_rate (float): flow rate in ml/min
            duration (float): pump duration in seconds
            flow_measured (_type_): measured flow in ml/min
            tol (float, optional): Maximum difference between measured and theoretical flow. Defaults to 0.2.
        """        

        flow_expected  = self.flow['expected']
        tol = self.flow['tolerance']

        volume_expected = round(flow_expected*duration/60,3)
        vol_diff = abs(volume_measured-volume_expected)/volume_expected
        self.log_msg('info', f'VOLUME. measured {volume_measured} ml, expected {volume_expected} ml -> diff {round(100*vol_diff)} %')
        
        now = datetime.now()
        current_time = now.strftime("%H:%M:%S")
        self.volume_measurements.append([current_time,
                                     self.current_round, 
                                     self.current_buffer,
                                     duration,
                                     volume_expected,
                                     volume_measured])

        if vol_diff > tol:
            self.log_msg('error', f'Measured volume is outside of specified tolerance of expected volume. WILL STOP, user verification required.')
            #ToDo: add a real verification
   
            input("Press Enter to continue... ")

    def save_volume_measurements(self):
        """save_volume_measurements _summary_

        Args:
            file_save (_type_, optional): _description_. Defaults to None.
        """
        if not self.file_volume_measurements :
            now = datetime.now()
            data_string = now.strftime("%Y-%m-%d_%H-%M")
            self.file_volume_measurements = str(Path(self.config_file_experiment).parent / f'volume_log__{data_string}.csv')
        
        with open(self.file_volume_measurements, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerows(self.volume_measurements)

        return file_save

    def pump_run(self, pump_time):
        """pump_run _summary_

        Args:
            pump_time (_type_): _description_
        """
        # Start flow measurement if sensor present
        if self.sensor:
            self.sensor.start()
        
        # Start pump for specified duration
        self.log_msg('info', f'Starting pump for {pump_time}s.')
        self.pump.start()
        time.sleep(pump_time)
        self.pump.stop()
        self.log_msg('info',f'Pump was running for {int(pump_time)} s.')
            
        time.sleep(1)
        
        # Stop flow measurement if sensor present
        if self.sensor:
            volume_measured = self.sensor.stop()
            
            # Make sure that volume was returned (None for problems)
            if volume_measured is not None:
                self.log_msg('info', f'Measured volume: {volume_measured} ml')

                if self.flow['verify']:
                    self.verify_flow(pump_time, volume_measured)
            else:
                self.log_msg('error', f'No volume measurement returned. Check sensor!')
            

    # Move robot to specified buffer
    def select_buffer(self, buffer_sel):
        """ Changes the valves and plate to the correct position for the provided buffer

        BUFFER POSITIONS
        
        Buffer are provided with a tuple with 3 elements
        [valve-id, plate-id,plate-pos]
        
            valve-id: we are using a valve with 8 entries (could also be daisy-chained)
                0: no valve
                1-8: one valve with 8 inputs
                Could be extended to more buffers with higher values and then addressing additional valves
            plate-id: we can put 2 plates on the plate reader
                0: no plate -> position as to be specified with XY coordinates
                1: plate 1 -> position has to be specfied with well numbers (A1, A2, ...)
                2: plate 2
            plate-pos: can be either the well (A1, ...) or an absolute position (XY coordinates)


        Args:
            buffer_sel ([type]): [description]
        """
        
        self.log_msg('info', f'Moving robot to buffer {buffer_sel}')
        
        if buffer_sel == self.current_buffer:
            self.log_msg('info', f'Robot is already in place ... will chill out.')

        else: 

            buffers = self.experiment_config['buffers']
                    
            if not buffer_sel in self.buffer_names:
                self.log_msg('error', 'Buffer not defined in buffer list '+str(buffer_sel),'Buffer not defined in buffer list '+str(buffer_sel))
                self.log_msg('error', 'Stopping robot','Stopping robot')
                raise SystemExit
            
            valve_id, plate_id, plate_pos = buffers[buffer_sel]

            # Move valve if specified
            self.log_msg('info', f'Moving valve to position: {valve_id}')
            if valve_id > 0:
                
                if  self.valve is None:
                    self.log_msg('error', 'NO VALVE DEFINED. STOPPING SYSTEM.','NO VALVE DEFINED. STOPPING SYSTEM.')
                    raise SystemExit
                else:
                    self.valve.move(valve_id)
                
            # Move plate
            self.log_msg('info', f'Plate ID: {plate_id}')
            self.log_msg('info', f'Plate POS: {plate_pos}')
                
            # Either not used, or absolute position on plate
            if plate_id == 0:
                
                # Absolute position on plate
                if plate_pos is not None:
                    
                    reg_exp = re.compile('X(?P<X>.*)_Y(?P<Y>.*)_Z(?P<Z>.*)', re.IGNORECASE)
                    match  = re.search(reg_exp, plate_pos)
                    
                    if match:
                        match_dict = match.groupdict()
                        x_pos = float(match_dict['X'])            
                        y_pos = float(match_dict['Y'])  
                        z_pos = float(match_dict['Z'])  
                    else:
                        self.log_msg('error', f'Position on well not in good format: {plate_pos}')
                        raise SystemExit
                        
                    # Move to XY position
                    self.plate.move_stage({'X':x_pos,'Y':y_pos})
                    while not 'Idl' in self.plate.check_stage() : #Wait until move is done before proceeding.
                        time.sleep(0.5)
                        
                    # Move to Z position
                    self.plate.move_stage({'Z':z_pos})    
                    while not 'Idl' in self.plate.check_stage() : #Wait until move is done before proceeding.
                        time.sleep(0.5)    
                        
            # Well (plate 1).
            if plate_id == 1:
                
                if plate_pos in self.well_coords.keys():
                    
                    # Move to XY
                    new_pos_xy = {'x': self.well_coords[plate_pos]['x'],
                                'y': self.well_coords[plate_pos]['y']}                                         
                    
                    self.plate.move_stage(new_pos_xy)
                    while not 'Idl' in self.plate.check_stage() : # Wait until move is done before proceeding.
                        self.logger.info(self.plate.check_stage())
                        time.sleep(1)
                    
                    # Move to Z
                    new_pos_z = {'z': self.well_coords[plate_pos]['z']}                                         
                    self.plate.move_stage(new_pos_z)
                    while not 'Idl' in self.plate.check_stage() : # Wait until move is done before proceeding.
                        time.sleep(1)
                        
                else:
                    self.log_msg('error', f'Well is not defined: {plate_pos}')
                    raise SystemExit

            self.current_buffer = buffer_sel

        
        
    def run_step(self, step, round_id, total_time):
        """ Run a single step in the fludics cycle.
        
        == Demo
        Will check if demo is defined. If yes, no call to fluidics system will be executed, and
        times are shortened.
        
        """
        
        demo = self.status['demo']
        
        action = list(step.keys())[0]
        param = list(step.values())[0]
        
        self.log_msg('info', f'STEP: {action}, with parameter {param}')
        
        # == Move robot to specified buffer
        if action == 'buffer': #
            if self.stop.is_set():
                self.logger.info('Stopping robot.')
                raise SystemExit

            # Check if buffer should be cycled over
            if 'ii' in param:
                param = param.replace('ii', round_id)
                self.log_msg('info', f'Cycling buffer: {param}')
            
            if not demo:
                self.select_buffer(param)
            
        # == Activate pump
        elif action == 'pump':
            self.log_msg('info', f'Remaining time (approx): {total_time}')
            
            if self.stop.is_set():
                self.logger.info('Stopping robot.')
                raise SystemExit
            
            if not demo:
                self.pump_run(param)
            
            time.sleep(1)
            total_time =  total_time - float(param/60)

        # == Pause
        elif action == 'pause':
            self.log_msg('info', f'Remaining time (approx): {total_time}')
            if self.stop.is_set():
                self.logger.info('Stopping robot.')
                raise SystemExit
            if not demo:
                self.pause(param)
            total_time =  total_time - float(param/60)
            
        # === Move robot to specified position
        elif action == 'zero_plate':
            self.log_msg('info', f'Moving plate to position Zero')
            self.plate.move_stage({'Z':0,'X':0,'Y':0})
        
         # === Wait for user input
        elif action == 'wait':
            self.log_msg('info', f'WAITING FOR USER INPUT ... press ENTER to continue')
            input("Press Enter to continue...")       

        elif action == 'image':
            
            if param ==1: 
                self.log_msg('info', f'Ready for imaging')
                self.status['launch_acquisition'] = True
            else:
                self.log_msg('info', f'Will skip imaging this time')
                self.status['launch_acquisition'] = False    
            
        elif action == 'round':    
            pass

        # == Not defined  
        else:
            self.log_msg('error', f'Unrecognized step: {action} ')     
        
        return total_time
        
    # >>>> Functions to run one round
    def run_single_round(self, round_id, total_time=None, steps=None):
        """ Run a single fluidic round as specified by the round_id.
            Can be called recursively in case conditional steps are provided. 

        Args:
            round_id (integer): number of round that should be run.
            total_time (_type_, optional): _description_. Defaults to None.
            steps (_type_, optional): _description_. Defaults to None.

        Returns:
            _type_: _description_
        """        
        
        self.current_round = round_id

        # Check if this is the first call (and not a recursive one)
        if total_time is None:

            # Reset imaging flag 
            self.status['launch_acquisition'] = True
            
            # Set run times
            run_time_all = self.run_time_all
            
            if round_id in run_time_all.keys():
                total_time = run_time_all[round_id]      
            else:
                total_time = run_time_all['default']
    
        
        # Check if sequence of steps is defined
        #  Permits to determine if the call is for a conditional round, where steps is defined.
        #  For a first call, the loaded sequence of steps is used
        cond_steps = True
        if steps is None: 
            steps = self.experiment_config['sequence']
            cond_steps = False
            
        self.log_msg('info', f'RUNNING ROUND: {round_id}, expected duration {total_time}')
        
        # Loop over all steps
        for step in steps:                # Sequence is defined as list in config file.
            
            if isinstance(step, list):
                
                # ToDo: could htis be intergrated into the run_step function?
                self.logger_short.info(f'Conditional step: {step}')
                
                action = list(step[0].keys())[0]
                round_ids_cond = list(step[0].values())[0].split(",")

                if action == 'round':
                    if round_id in round_ids_cond: 
                        self.log_msg('info', f'Running conditional steps for round: {round_id}')
                        total_time = self.run_single_round(round_id, total_time=total_time, steps=step)
                else:
                    self.log_msg('error', f'First action has to be "round" and not {action}.')
            
            else: 
                total_time = self.run_step(step, round_id, total_time)
    
        # Remove round id only if function call is not for a conditional step
        if not cond_steps:
            self.rounds_available.remove(round_id)
            self.log_msg('info', f'Available rounds: {self.rounds_available}')
            
            if self.sensor:
                self.save_volume_measurements()

        return total_time
    
    
    # >>>> Functions to initiate robot   
    def load_config_experiment(self, config_file_experiment):
        """
        Open config json file and returns configured hardware components.
        """
        
        self.log_msg('info', f'Load robot specification file: {config_file_experiment}')
        self.config_file_experiment = config_file_experiment
        
        with open(config_file_experiment) as file:
            self.experiment_config = yaml.load(file, Loader=yaml.FullLoader)

        # Buffer names
        self.buffer_names = list(self.experiment_config['buffers'].keys())
        self.log_msg('info', f'All specified buffers: {self.buffer_names}')
        
        # Check if buffer positions on plate are unique
        self.check_plate_positions()
        
        # Estimate over which buffers should be looped
        self.round_id_all, self.buffers_round_all, self.run_time_all = self.analyse_sequence()
        
        # Keep track which cyles where not executed yet (a round can only be executed once)
        self.rounds_available = self.round_id_all  
        
        # Calculate well positions
        if 'well_plate' in self.experiment_config.keys():
            self.log_msg('info', 'Calculation positions of wells.')
            self.well_coords = self.calc_well_coords()
        
        
    def check_plate_positions(self,):
        """
        Check if positions on plates are unique.
        """
        
        # Get plate ids and plate positions 
        pos_all = list(self.experiment_config['buffers'].values())

        # >>> Get positions for plate 1
        plate1_pos = [row[2] for row in pos_all if row[1] ==1]

        # Find duplicate 
        tmp  = set()
        duplicates = set(x for x in plate1_pos if (x in tmp or tmp.add(x)))
        
        if len(duplicates) > 0:
            self.log_msg('error', f'These Plate 1 positions are listed multiple times: {list(duplicates)}')
        
    
    def calc_well_coords(self,):
        """Generate coordinate list for whole and selected wells of a 96-well plate.
        Also adjusts for a rotated plate by using measured top left and bottom right positions from
        config file.

        Returns:
            _type_: _description_
        """        

        # >>> Function to calculate well positions
        def rotate_around_point(point, radians, origin=(0,0)):
            """Rotate a point around a given point.
            """
            x, y = point
            ox, oy = origin

            qx = ox + math.cos(radians) * (x - ox) - math.sin(radians) * (y - oy)
            qy = oy + math.sin(radians) * (x - ox) + math.cos(radians) * (y - oy)

            return qx, qy

        # >>> Get relevant parameters
        n_rows =self.experiment_config['well_plate']['rows']
        n_cols =self.experiment_config['well_plate']['columns']
        well_spacing=self.experiment_config['well_plate']['well_spacing']
        bl_x=self.experiment_config['well_plate']['bottom_left']['x']
        bl_y=self.experiment_config['well_plate']['bottom_left']['y']
        tr_x=self.experiment_config['well_plate']['top_right']['x']
        tr_y=self.experiment_config['well_plate']['top_right']['y']
        z_base = self.experiment_config['well_plate']['z_base']

        # >>> Calculate rotation angle of plat
        dx = (n_cols-1)*well_spacing
        d_max_x = tr_x-bl_x

        dy = (n_rows-1)*well_spacing
        d_max_y = tr_y-bl_y

        phi_wells =  math.atan(dy/dx)
        phi_plate =  math.atan(d_max_y/d_max_x)
        phi_rotate = phi_plate - phi_wells 

        self.logger.info(f'Plate rotated by {math.degrees(phi_rotate)}')

        # >>>> Assign coordinates for rotated plate
        all_coords={} 
        for i in range(n_cols):
            for j in range(n_rows):
                x = bl_x+i*well_spacing
                y = bl_y+j*well_spacing
                x_rot, y_rot = rotate_around_point((x,y),phi_rotate,(bl_x,bl_y))
                all_coords[chr(65+i)+str(1+j)]={'x': round(x_rot), 
                                                'y': round(y_rot), 
                                                'z': z_base}  # ASCII code: 65 corresponds to A
        return all_coords
    
    
    def analyse_step(self, step, buffers_fix, buffers_cycle, run_time):
        """analyse_step _summary_

        Args:
            step (_type_): _description_
            buffers_fix (_type_): _description_
            buffers_cycle (_type_): _description_
            run_time (_type_): _description_

        Returns:
            _type_: _description_
        """        
        
        step_action = list(step.keys())[0]
        step_argument = list(step.values())[0]
        
        if step_action == 'buffer': 
            
            reg_exp = re.compile('(?P<buffer_plate>.*)ii', re.IGNORECASE)
            
            if isinstance(step_argument, str):
                match  = re.search(reg_exp, step_argument)
                if match:
                    match_dict = match.groupdict()
                    buffer_cyle = match_dict['buffer_plate']
                    buffers_cycle.append(buffer_cyle)
                else:
                    buffers_fix.append(step_argument)
        
        if step_action == 'pump' or step_action == 'pause':
            run_time = run_time + int(step_argument)
        
        return buffers_fix, buffers_cycle, run_time
    
    
    
    def analyse_sequence(self):
        """ Function to analyze the buffers specified in the robot file

        Returns:
            _type_: _description_
        """        

        self.logger.info(f'Analyze buffers that will change in sequential runs')
        
        # Analyze sequence file: check which buffers are defined in the protocol
        buffers_cycle = []
        buffers_fix = []

        run_time = 0
        run_time_all={'default':0}

        buffers_round_all = {}
        buffers_round_all = {'default':{}}

        for step in self.experiment_config['sequence']:
            
            # dict: normal step in round
            if isinstance(step, dict):
                buffers_fix, buffers_cycle, run_time = self.analyse_step(step, buffers_fix, buffers_cycle, run_time)
            
            # List: conditional sequence, first element has have key "round"
            elif isinstance(step, list):
                step_action = (list(step[0].keys())[0])
                step_argument = (list(step[0].values())[0])
                
                if step_action != 'round':
                    self.log_msg('error', f'ERROR! First action in conditional sequence has to be "round" and not {step_action}')
                    
                else:
                    buffers_runs_cond = []
                    run_time_cond = 0 
                    for step_cond in step:
                        buffers_fix, buffers_runs_cond, run_time_cond = self.analyse_step(step_cond, buffers_fix, buffers_runs_cond, run_time_cond)

                    # Get ids of all specified conditional runs
                    id_conds = step_argument.split(",")
                    
                    for id_cond in id_conds:
                        
                        # Verify if conditional sets already exist
                        if id_cond in buffers_round_all.keys():
                            buffers_round_all[id_cond]=buffers_round_all[id_cond]+buffers_runs_cond
                            run_time_all[id_cond] = run_time_all[id_cond]+round(run_time_cond/60)
                        else:
                            buffers_round_all[id_cond]=buffers_runs_cond
                            run_time_all[id_cond] = round(run_time_cond/60)

        run_time_all['default'] = round(run_time/60)
        buffers_round_all['default']=buffers_cycle  # Add general round buffers
        
        # >> Check fixed buffers
        buffers_fix = list(set(buffers_fix))   # Unique entries only
        self.log_msg('info', f'Buffers fixed in each run: {buffers_fix}')
        buffer_fix_not_defined_bool = [item not in self.buffer_names for item in buffers_fix]
        buffer_fix_not_defined = list(compress(buffers_fix, buffer_fix_not_defined_bool))
        if buffer_fix_not_defined:
           self.log_msg('error', f'Not all FIXED buffers are defined in buffer list! Please check: {buffer_fix_not_defined}')     
        else:
            self.log_msg('info', f'All FIXED buffers are defined in buffer list. Well done.')  
        
        # >> Update conditional runs

        # Add default run time to conditional rounds
        for round_id, run_time in run_time_all.items():
            if round_id != 'default':
                run_time_all[round_id]  = run_time + run_time_all['default']  # Add general "looping buffers"

        # Add general buffers to conditional rounds
        for round_id, buffers_round in buffers_round_all.items():
            if round_id != 'default':
                buffers_round_all[round_id]  = buffers_round + buffers_round_all['default']  # Add general "looping buffers"

        # >> Check buffers to cycle over

        # Get name of all round with conditional steps
        runs_cond = list(buffers_round_all.keys())
        runs_cond.remove('default')

        # Loop over all cyling buffers
        round_id_all = []
        
        for round_id, buffers_round in buffers_round_all.items():
            buffers_index_all = []
            
            # Loop over all buffers that are changed in the sequential run
            for buffer_loop in buffers_round:
                buffers_index = []
                
                # For default runs: use regular expression to find name of run
                if round_id == 'default':
                
                    reg_exp = re.compile(f'^{buffer_loop}(?P<buffer_id>.*)' , re.IGNORECASE)

                    # Find all run indices that are listed in buffer list
                    for buffer_name in self.buffer_names: 
                        
                        match = re.search(reg_exp, buffer_name)
                        if match:
                            match_dict = match.groupdict()
                            buffer_id = match_dict['buffer_id']
                            buffers_index.append(buffer_id)
                    
                        # Clean up: remove conditional runs (otherwise they pass check if their conditional buffers are not defined)
                        buffers_index = [x for x in buffers_index if x not in runs_cond]
                
                # Conditional runs: look specifically for buffer names
                else:
                    if buffer_loop+round_id in self.buffer_names:
                        buffers_index.append(round_id)
                    else:
                        self.log_msg('error', f'Buffer {buffer_loop+round_id} in conditional steps for round {round_id} not defined!')
                         
                buffers_index_all.append(buffers_index)
                
            
            # >>> Make sure that for each run all buffers are present
            
            # Covers extreme case where no cycling buffer is defined
            if len(buffers_index_all) == 0:
                self.log_msg('info', f'No buffer identified to loop over.')
                run_round_id = 'None'
            else:
                # Get rounds that are present for all buffers  
                rounds_all_buffers = list(set.intersection(*map(set,buffers_index_all)))
                
                # >> Quality check - get rounds where not all cycling buffers are listed
                
                # Get rounds that are present for one (or more) but not all buffers
                rounds_all = list(set.union(*map(set,buffers_index_all)))
                rounds_bad = list(set.difference(set(rounds_all), set(rounds_all_buffers)))
       
                if len(rounds_bad) > 0:
                        self.log_msg('error', f'Round(s): {rounds_bad} can not be performed. Not all buffers defined.')
                        
                round_id_all = round_id_all + rounds_all_buffers
        
        # >>>  Order rounds as they appear in buffer list (by using the first default cycling buffer)
        buffer_cycle = buffers_cycle[0]
        reg_exp = re.compile(f'^{buffer_cycle}(?P<buffer_id>.*)' , re.IGNORECASE)
        buffers_order = []
        for buffer_name in self.buffer_names: 
            
            match = re.search(reg_exp, buffer_name)
            if match:
                match_dict = match.groupdict()
                buffer_id = match_dict['buffer_id']
                buffers_order.append(buffer_id)
        
        # Keep only the ones that passed analysis, and leave order of occurance as listed in buffer list
        round_id_all = [id for id in buffers_order if id in round_id_all]
        
        self.log_msg('info', f'Buffers for sequential hybridization: {buffers_round_all}')
        self.log_msg('info', f'Run times: {run_time_all}')
        self.log_msg('info', f'Identified run IDs: {round_id_all}')

        return round_id_all, buffers_round_all, run_time_all 

                
    # >>>> Functions to initiate robot   
    def load_config_system(self):
        """ Open config json file and returns configured hardware components.
        This file contains information about the serial commands used to

        Returns:
            _type_: _description_
        """
        with open(self.config_file_system) as json_file:
            config_system = json.load(json_file)
        self.log_msg('info','Config file for fluidics loaded!')
        
        # Check if demo mode is enabled
        if "demo" in config_system.keys():
            self.log_msg('info',f"Config file contains demo specification: {config_system['demo']}")
            if config_system['demo'].lower() in ['1', 'true', 't', 'y', 'yes', 'on'] :
                self.status['demo'] = True
                self.log_msg('info',"DEMO mode enabled")
        
        return config_system
    
    
    def close_serial_ports(self):
        """ Closes all open serial ports.
        """
        self.logger.info('Closing all connections.')
        config_system = self.config_system
        for hardware_comp in config_system:
           self.log_msg('info', "  Closing serial port of component: %s", config_system[hardware_comp]['type'])
           if 'ser' in config_system[hardware_comp].keys():
                ser = config_system[hardware_comp]['ser']
                if ser is not None:
                    if ser.isOpen() is True:
                        ser.close()    


    def initiate_system(self):
        """ If available, use predefined COM ports to connect to hardware.
        """

        config_system = self.config_system
        
        # Loop over all hardware components to connect to serial port
        if not self.status['demo']:
            for hardware_comp in config_system:    

                    # >>>> Connect to serial port when specified
                    if ('COM' in config_system[hardware_comp].keys()):
                        self.log_msg('info', f"  Initiating {hardware_comp}: {config_system[hardware_comp]['type']} on serial port {config_system[hardware_comp]['COM']}")
            
                        # Connect to serial port
                        try:
                            ser = serial.Serial(port = config_system[hardware_comp]['COM'],
                                                baudrate = config_system[hardware_comp]['baudrate'],
                                                bytesize=8,
                                                parity='N',
                                                timeout=0.5)
                            self.config_system[hardware_comp]['ser'] = ser
                            
                        except serial.SerialException as e:
                            self.log_msg('error', f'  ERROR when opening serial port: {e}')

        # >>> Assign all specified robot elements
        try:
            
            if 'pump' in self.config_system.keys():
                self.pump = self.assign_pump()      
            else:
                self.pump = None

            if 'plate' in self.config_system.keys():
                self.plate = self.assign_plate()
            else:
                self.plate = None

            if 'valve' in self.config_system.keys():
                self.valve = self.assign_valve()
            else:
                self.valve = None
                
            if 'flow_sensor' in self.config_system.keys():
                self.sensor = self.assign_sensor()
            else:
                self.sensor = None
            
            if False not in (self.pump, self.valve, self.plate, self.sensor):
                self.log_msg('info', 'All components assigned.')
                self.status['ports_assigned'] = True
                self.status['robot_zeroed'] = False
            else:
                self.log_msg('error', 'Could not connect to one or more component (see error above).')
            
    
        except (UnboundLocalError, AttributeError) as e:
            self.log_msg('error', f'Assignment of robot components failed. {e}')
            self.log_msg('error', config_system)


    def assign_sensor(self):
        """ Use fluidics configuration file and generate a pump object

        Returns:
            _type_: _description_
        """
        self.log_msg('info', f'Assigning sensor')

        if self.config_system['flow_sensor']['type'] == 'Sensirion_csv':
            self.log_msg('info', f'Assign SENSIRION CSV flow sensor')
            if not Path(self.config_system['flow_sensor']['log_file']).is_file():
                self.log_msg('error', f'File for flow measurement not found {self.config_system["flow_sensor"]["log_file"]}!')
                self.log_msg('error', f'{self.config_system["flow_sensor"]}')           
                return False

            sensor = sensirion_csv(self.config_system['flow_sensor']['log_file'],
                                   self.config_system['flow_sensor']['kernel_size'],
                                   self.config_system['flow_sensor']['flow_min'],
                                   logger=self.logger)
            self.log_msg('info', sensor)
            
            return sensor

    def assign_pump(self):
        """  Use fluidics configuration file and generate a pump object

        Returns:
            _type_: _description_
        """
        self.log_msg('info', f'Assigning pump')
        
        # Function selecting the appropriate pump class
        if len(self.config_system['pump']['type']) == 0:
            self.log_msg('error', 'No pump defined!')
            self.log_msg('error', f'{self.config_system["pump"]}')
            return False
            
        if not 'ser' in self.config_system['pump'].keys():
            self.log_msg('error', 'No serial port connection for pump established!')
            self.log_msg('error', f'{self.config_system["pump"]}')
            return False

        if self.config_system['pump']['type'] == 'REGLO DIGITAL':
            self.log_msg('info', f'Assign REGLO DIGIAL pump on port {self.config_system["pump"]["ser"].portstr}')
            
            # Make sure that baudrate is correct
            ser = self.config_system['pump']['ser']
            ser.baudrate = self.config_system['pump']['baudrate']            
            pump = RegloDigitalController(ser, logger=self.logger)
            
            # Set flowrate and revolution direction as specfied in log file
            pump.info() # For unknown reasons the first command does not execute 
            pump.set_flowrate(self.config_system['pump']['Flowrate'])
            pump.set_revolution(self.config_system['pump']['Revolution'])
            
            return pump

    def assign_valve(self):
        """assign_valve _summary_

        Returns:
            _type_: _description_
        """        
    
        self.log_msg('info', 'Assigning valve.')

        #Function selecting the appropriate valve class
        if len(self.config_system['valve']['type']) == 0:
            self.log_msg('error', 'No valve defined!')
            self.log_msg('error', f'{self.config_system["valve"]}')
            return False
        
        if not 'ser' in self.config_system['valve'].keys():
            self.log_msg('error', 'No serial port connection for valve established!')
            self.log_msg('error', f'{self.config_system["valve"]}')
            return False

        if self.config_system['valve']['type'] == 'HAMILTON MVP':
            self.log_msg('info', f'Assign HAMILTON valve on port {self.config_system["valve"]["ser"].portstr}')

            # Make sure that baudrate is correct
            ser = self.config_system['valve']['ser']
            ser.baudrate = self.config_system['valve']['baudrate'] 
            return HamiltonMVPController(ser, logger=self.logger)        
  
  
    def assign_plate(self):
        """assign_plate _summary_

        Returns:
            _type_: _description_
        """        
        self.log_msg('info', 'Assigning plate robot.')

        #Function selecting the appropriate valve class
        if len(self.config_system['plate']['type']) == 0:
            self.log_msg('error', 'No plate robot defined!')
            self.log_msg('error', f'{self.config_system["plate"]}')
            return False
        
        if not 'ser' in self.config_system['plate'].keys():
            self.log_msg('error', 'No serial port connection for plate robot established!')
            self.log_msg('error', f'{self.config_system["plate"]}')
            return False

        if self.config_system['plate']['type'] == 'CNCRouter3018PRO':
            self.log_msg('info', f'Assign 3018 plate robot on port {self.config_system["plate"]["ser"].portstr}')
            
            # Make sure that baudrate is correct
            ser = self.config_system['plate']['ser']
            ser.baudrate = self.config_system['plate']['baudrate'] 
            return CNCRouter3018PRO(ser, logger=self.logger)     


# ---------------------------------------------------------------------------
# Flow sensor
# ---------------------------------------------------------------------------

class flowSensor():
    """ Base class for flow sensor.
    """

    def __init__(self):
        pass

    def _type(self):
        return self.__class__.__name__

    def start(self):
        """ Start measurment

        Raises:
            NotImplementedError: _description_
        """
        raise NotImplementedError('No START function defined for this class!')
    
    def stop(self):
        """ Stop measurment

        Raises:
            NotImplementedError: _description_
        """
        raise NotImplementedError('No STOP function defined for this class!')


class sensirion_csv(flowSensor):    
    """sensirion_csv 
    

    Args:
        flowSensor (_type_): _description_
    """
    def __init__(self, file_name, kernel_size, flow_min,logger=False):
        """__init__ _summary_

        Args:
            file_name (_type_): _description_
            kernel_size (_type_): _description_
            flow_min (_type_): _description_
            logger (bool, optional): _description_. Defaults to False.
        """
        # Initiate logger
        if isinstance(logger, type(None)):
            # Logs the name of the function
            self.logger = logging.getLogger('AUTOMATOR-SENSIRION-CSV')
            self.logger.setLevel(100)
        self.logger = logger

        # Initiate
        self.file_name_flow = file_name
        self.kernel_size = kernel_size # Kernel size of moving average 
        self.flow_min = flow_min # Minimum flow, below this value will be set to 0


    def start(self):
        """start _summary_
        """
        self.file_flow = open(self.file_name_flow, "rb")
        self.file_flow.seek(-2, os.SEEK_END)
        while self.file_flow.read(1) != b'\n':
            self.file_flow.seek(-2, os.SEEK_CUR) 


    def stop(self):
        """stop _summary_

        Returns:
            _type_: _description_
        """        
        flow_log =  [line.strip().decode( "utf-8" ) for line in self.file_flow.readlines()]

        flowreader = csv.reader(flow_log, delimiter=',', quotechar='"')
        data_raw = [data for data in flowreader]

        # Convert to float and remove , as separator for thousand
        data =[[float(x.replace(',','')) for x in row] for row in data_raw]
        
        if len(data) <= 1:
            self.logger.error('No time-course of flow measurements can be read. Is logging active?')
            return None
        else:
            # Convert to numpy and extract time and flow
            data_array = np.asarray(data)
            t_flow = data_array[:,1] - data_array[0,1]        # Set first time-point to 
            flow = data_array[:,2]
            
            # Moving average and signal integration
            kernel = np.ones(self.kernel_size) / self.kernel_size
            flow_convolved = np.convolve(flow, kernel, mode='same')
            flow_convolved[flow_convolved<self.flow_min] = 0
            volume_total = round(np.trapz(flow_convolved, t_flow/60)/1000,3)
            self.file_flow.close()
            return volume_total

# ---------------------------------------------------------------------------
# Plate controlller
# ---------------------------------------------------------------------------


class plateController():
    """ Base class for cnc plate controller.
    """

    def __init__(self):
        pass

    def _type(self):
        return self.__class__.__name__

    def move(self):
        '''Move valve '''


class CNCRouter3018PRO(plateController):     
    """ Control a CNC router 3018PRO with Gcode.

    Args:
        plateController (_type_): _description_
    """

    def __init__(self, ser, feed=500, logger=False):

        # Initiate logger
        if isinstance(logger, type(None)):
            # Logs the name of the function
            self.logger = logging.getLogger('AUTOMATOR-PLATE-CNCrouter')
            self.logger.setLevel(100)
        self.logger = logger

        # Initiate
        self.ser = ser
        self.feed = feed
        self.logger.info(f'CNCRouter3018PRO controller initiated.')
        
        # Set status report
        ser.flushInput()
        ser.write(('$10=2\n\r').encode('utf-8'))
        grbl_out = ser.readline().decode('utf-8')
        self.logger.info('PLATE: set Status report mask: ' + grbl_out)


    def zero_stage(self):
        """ Set current position to 0 for all axis. 
        """
        ser = self.ser
        ser.write(('G10 L20 P0 X0 Y0 Z0 \n').encode('utf-8'))
        grbl_out = ser.readline().decode('utf-8')
        self.logger.info('PLATE: Current position set to zero: '+grbl_out)
        

    def check_stage(self):
        """check_stage _summary_

        Returns:
            _type_: _description_
        """
        ser = self.ser
        ser.flushInput()
        ser.write(('?\n\r').encode('utf-8'))
        time.sleep(0.2)
        grbl_out = ser.readline().decode('utf-8')
        return grbl_out


    def move_stage(self, pos):
        """ Move stage to provided XY position in the dictionary.
        Will loop over provided values and move stage to coordinates.
        
        Args:
            pos (dict): contains new position as a dictionary, e.g.  {'X':5}

        """
        ser = self.ser
        for axis, coord in pos.items():
            
            if not axis in ('X','x','Y','y','Z','z'):
                self.log_msg('error', 'Position has to be X, Y or Z')
                continue
            
            ser.write(('G0 Z0 \n').encode('utf-8')) # Always move to Z=0 first.
            while not 'Idl' in self.check_stage() : #Wait until move is done before proceeding.
                self.logger.info(self.check_stage())
                time.sleep(0.5)

            ser.write(('G0 '+axis.upper()+str(coord)+' \n').encode('utf-8')) # Move to provided coordinates
            while not 'Idl' in self.check_stage() : #Wait until move is done before proceeding.
                time.sleep(0.5)

            grbl_out = ser.readline().decode('utf-8') # Wait for grbl response with carriage return
            self.logger.info('Moved to '+axis.upper()+'='+str(pos[axis]))
            self.logger.info('GRBL out:'+grbl_out)
    
    
    def jog_stage(self, jog_axis, jog_dist):
        """ Move stage with provided XYZ increment in the dictionary.
        
        Args:
            jog (dict): contains new position as a dictionary, e.g.  {'X':5}
        """
    
        ser = self.ser
        feed = self.feed
        ser.write(('$J=G91 G21 '+jog_axis.upper()+str(jog_dist)+'F'+str(feed)+' \n').encode('utf-8')) # Move code to GRBL, xy first
        while not 'Idl' in self.check_stage() : #Wait until move is done before proceeding.
                time.sleep(0.25)
        grbl_out = ser.readline().decode('utf-8') # Wait for grbl response with carriage return
        self.logger.info('GRBL out:' + grbl_out)
        self.logger.info('GRBL status:' + self.check_stage())
  
    
# ---------------------------------------------------------------------------
#  pumpControlller class: to control the pump
# ---------------------------------------------------------------------------
 
class pumpController():
    """ Base class for pump controller.
    """

    def __init__(self):
        pass

    def _type(self):
        return self.__class__.__name__

    def start(self):
        '''Start pump '''
        raise NotImplementedError('No START function defined for this class!')

    def stop(self):
        '''Stop pump '''
        raise NotImplementedError('No STOP function defined for this class!')


class RegloDigitalController(pumpController):
    """ Control a Reglo Digital peristaltic pump.

    Args:
        pumpController (_type_): _description_
    """

    def __init__(self, ser, logger=None):
        """__init__ _summary_

        Args:
            ser (_type_): _description_
            logger (_type_, optional): _description_. Defaults to None.
        """
        
        # Setting up logger
        if isinstance(logger, type(None)):
            logger = logging.getLogger('AUTOMATOR-PUMP-REGLO')
            logger.setLevel(100)
        self.logger = logger
        
        # Initiate
        self.ser = ser
        self.logger.info(f'RegloDigitalController initiated.')


    def _check_response(self, response):
        """ Checks reponse of pump and reports success

        Args:
            response (_type_): _description_

        Returns:
            _type_: _description_
        """
        if response == '*':
            status = 1
            self.logger.info('Response: %s', response)
            self.logger.info('Command successfully executed')

        else:
            status = 0
            self.logger.info('Response: %s', response)
            self.logger.info('Command execution failed')

        return status


    def _send_cmd(self, ser_cmd):
        """ Sends command to pump

        Args:
            ser_cmd (_type_): _description_
        """

        self.logger.info('Command send: %s', ser_cmd)
        self.ser.write(ser_cmd.encode('UTF-8'))
        self.ser.flush()
        response = self.ser.readline().decode('utf-8')

        # >>> Check for special responses

        # SET FLOW rate
        if ser_cmd.startswith('1f'):

            try:
                # Compare send and set flow rates
                flow_send = float(ser_cmd[2:6]) * 10**float(ser_cmd[6:8])
                flow_set = float(response)
                flow_diff = abs(100 * (flow_send - flow_set) / flow_send)

                # If difference is smaller than 1% all is good
                if flow_diff < 1:
                    response = '*'

                self.logger.info('Flow-rate SEND: %f', flow_send)
                self.logger.info('Flow-rate SET : %f', flow_set)
                self.logger.info('Difference    : %f', flow_diff)
            except:
                self.logger.error(f'Setting flow rate seems to have failed. {response}')

        # Check if response is good
        self._check_response(response)

    def info(self):
        """ Get infos from pump - expected response *
        """
        self.logger.info('PUMP: info')
        self._send_cmd('1#\r')

    def start(self):
        """ Start pump - expected response *
        """
        self.logger.info('PUMP: start')
        self._send_cmd('1H\r')


    def stop(self):
        """ Stop pump - expected response *
        """
        self.logger.info('PUMP: stop')
        self._send_cmd('1I\r')


    def set_revolution(self, rev):
        """ Set revolution clockwise (CW) or counter_clockwise (CCW) 

        Args:
            rev (_type_): _description_
        """        

        self.logger.info('PUMP: set revolution direction: %s', rev)
        if rev == 'CW':
            self._send_cmd('1J\r')
        elif rev == 'CCW':
            self._send_cmd('1K\r')
        else:
            self.logger.info('Revolution direction is either CW or CCW!')


    def set_flowrate(self, rate, exp=-2):
        """ Specify flowrate 'rate' in ml/min

        For the pump, flowrates are set in the format mmmmmee m:Mantisse, e:Exponent

        The optional argument 'exp' is this exponent, the specified 'rate'
        is converted to this format. For example, anput rate of 0.5 ml/min,
        with default exponent off -2 will be computer as 50; since
        0.5x10^-2 = 0.5 to 2

        Args:
            rate (_type_): _description_
            exp (int, optional): _description_. Defaults to -2.
        """        

        self.logger.info('PUMP: set flow-rate: %f ml/min', rate)

        ee = '{}'.format(exp)
        mmmmm = str(int(rate * 10**(-(exp)))).zfill(4)
        ser_cmd = '1f' + mmmmm + ee + '\r'
        self._send_cmd(ser_cmd)
        

# ---------------------------------------------------------------------------
#  valveController class: to control the valves
# ---------------------------------------------------------------------------
        
class valveController():
    """ Base class for valve controller.'
    """

    def __init__(self):
        pass

    def _type(self):
        return self.__class__.__name__

    def move(self):
        '''Move valve '''
        raise NotImplementedError('No move function defined for this class!')

class HamiltonMVPController(valveController):
    """HamiltonMVPController _summary_

    Args:
        valveController (_type_): _description_
    """    

    def __init__(self, ser, logger=False):

        # Setting up logger
        if isinstance(logger, type(None)):
            # Logs the name of the function
            logger = logging.getLogger(__name__)
            logger.setLevel(100)
        self.logger = logger

        # Initiate
        self.ser = ser
        self.valves_init(1)
        self.logger.info(f'HamiltonMVPController initiated.')

    def _send_cmd(self, ser_cmd):
        """_send_cmd _summary_

        Args:
            ser_cmd (_type_): _description_
        """        

        self.logger.info('VALVE: command send: %s', ser_cmd)
        try:
            self.ser.write(ser_cmd.encode('utf-8'))
        except (UnboundLocalError, AttributeError):
            self.logger.error('Could not execute serial command.')


    def valves_init(self, valve_id):
        """valves_init _summary_

        Args:
            valve_id (_type_): _description_
        """        

        self.logger.critical('Valve: initiate #  %s', valve_id)

        ''' Initialize a MVP valve for h factor commands '''
        ser_cmd = '/{}h30001R\r'.format(valve_id)  # Enable h-factor commands
        self.ser.write(ser_cmd.encode('utf-8'))
        ser_cmd = '/{}h20000R\r'.format(valve_id)  # Initialize valve
        self.ser.write(ser_cmd.encode('utf-8'))
        ser_cmd = '/{}h10001R\r'.format(valve_id)
        self.ser.write(ser_cmd.encode('utf-8'))

        # Set valve type: 8 way with 45 degrees
        ser_cmd = '/{}h21003R\r'.format(valve_id)
        self.ser.write(ser_cmd.encode('utf-8'))


    def move(self, valve_sel):
        """move _summary_

        Args:
            valve_sel (_type_): _description_
        """        

        self.logger.info(f'Move valve to buffer index {valve_sel}')

        # Move only valve 1
        if valve_sel >=1 & valve_sel <=8:
            valve_id = 1
            valve_pos = valve_sel
            ser_cmd = '/{}h2600{}R\r'.format(valve_id, valve_pos)
            self._send_cmd(ser_cmd)
            """
            self.logger.info(f' Connecting to valve {valve_id} on position {valve_pos}')
            
            # Enable h-factor commands
            try:
                
                self.logger.info(ser_cmd)
                self.ser.write(ser_cmd.encode('utf-8'))
                
            except (UnboundLocalError, AttributeError):
                self.logger.error('Could not move valve.')
            """
        # Move valve 1 to connect position, and valve 2
        elif valve_sel >=9 & valve_sel <=16:

            # Move valve 1
            valve_id = 1
            valve_pos = 8
            self.logger.info(f' Connecting to valve {valve_id} on position {valve_pos}')
            try:
                ser_cmd = '/{}h2600{}R\r'.format(valve_id, valve_pos)
                self.ser.write(ser_cmd.encode('utf-8'))
            except (UnboundLocalError, AttributeError):
                self.logger.error('Could not move valve.')

            # Move valve 2
            valve_id = 2
            valve_pos = valve_sel - 8
            self.logger.info(f' Connecting to valve {valve_id} on position {valve_pos}')
            try:
                ser_cmd = '/{}h2600{}R\r'.format(valve_id, valve_pos)
                self.ser.write(ser_cmd.encode('utf-8'))
            except (UnboundLocalError, AttributeError):
                self.logger.error('Could not move valve.')


