'''
autoFISH GUI
'''

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------
import PySimpleGUI as sg
import logging
import threading
from datetime import datetime
import pathlib

from autofish.automator import Robot
from autofish.imager import pycroManager, fileSync_write, fileSync_create, TTL_sync
from autofish.coordinator import Controller

# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------

sg.theme('DarkAmber')
NAME_SIZE = 23
microscope_options = ('pycromanager', 'TTL sync', 'file synce - create', 'file sync - write')


def name(name):
    dots = NAME_SIZE-len(name)-2
    return sg.Text(name + ' ' + '•'*dots, size=(NAME_SIZE, 1), justification='r', pad=(0, 0), font='Courier 10')


# Window for launch pad
def make_window_control():
    layout = [[sg.Text('Specify fluidics & acquisition system!')],
              [sg.Button('Specify Fluidics', key='-Window-Fluidics-')],
              [sg.Button('Specify Acquisition', key='-Window-Scope-'), sg.Combo(microscope_options, default_value=microscope_options[0], s=(15, 22), enable_events=True, readonly=True, key='-SCOPE_SYNC-')],
              [sg.HorizontalSeparator()],
              [sg.Button('Initiate controller', key='-INITIATE_CONTROL-', disabled=True)],
              [sg.HorizontalSeparator()],
              [sg.Button('RUN all ROUNDS!', key='-RUN_ALL_ROUNDS-', disabled=True),
               sg.Button('STOP sequential RUN', key='-STOP_SEQ-', disabled=True)],
              [sg.Text('Save path'),      sg.Text('                                 ', key='-OUTPUT_DIR_SAVE_IMGS-')],
              ]

    return sg.Window('Automator - automate sequential FISH', layout, location=(800, 600), finalize=True)


# Window for pycromanager
def make_window_pycromanager():
    layout = [[sg.Text('Choose config file:', size=(18, 1), key='-SPECIFY_CONFIG_MICROSCOPE-'),
               sg.FileBrowse(file_types=(("yaml config", 'microscope_config*.yaml'), ("yaml", '*.yaml')),  target='-CONFIG_SCOPE-', disabled=False),
               sg.InputText('specify-config-microscope', key='-CONFIG_SCOPE-'),
               sg.Button('Load config for microscope', key='-LOAD_CONFIG_MICROSCOPE-', disabled=True)],

              [sg.HorizontalSeparator()],
              [sg.Text('Chose position list:', size=(18, 1), key='-SPECIFY_POS_LIST-'),
               sg.FileBrowse(file_types=(("pos list", '*.pos'),),  target='-POS_LIST-', disabled=False),
               sg.InputText('specify-pos-list', key='-POS_LIST-'),
               sg.Button('Load position list', key='-LOAD_POS_LIST-', disabled=True)],

              [sg.HorizontalSeparator()],
              [sg.Text('Folder to save data:', size=(18, 1)),
               sg.FolderBrowse(target='-DIR_SAVE_IMGS-'),
               sg.InputText('folder-save-images', key='-DIR_SAVE_IMGS-', enable_events=True)],

              [sg.HorizontalSeparator()],
              [sg.Button('Initiate communication with micromanager', key='-OPEN_MICRO_MANAGER-', disabled=True),
               sg.Checkbox('Start headless', default=False, key='-MM_headless-')],
              [sg.Button('Create acqusition event', key='-CREATE_ACQUISITION_EVENT-')],

              [sg.HorizontalSeparator()],
              [sg.Button('Launch one acquisition', key='-LAUNCH_ACQUISITION-'),
               sg.InputText('test', key='-NAME-ACQUISITION-', enable_events=True)
               ],
              ]
    return sg.Window('Microscope - setup acquisition', layout, finalize=True)


# Window for acquisition synchronization via a text file with changing content
def make_window_TTL_sync():
    layout = [[sg.Text('Choose TTL config file:', key='-SPECIFY_TTL_CONFIG_FILE-'),
               sg.FileBrowse(file_types=(("config file", '*.json'),),  target='-TTL_CONFIG_FILE-', disabled=False),
               sg.InputText('specify-config-microscope', key='-TTL_CONFIG_FILE-')],
              [sg.HorizontalSeparator()],
              [sg.Button('Connect to SYNC box', key='-INIT_TTL_SYNC-')],
              ]
    return sg.Window('File-synchronization : write', layout, finalize=True)


# Window for acquisition synchronization via a text file with changing content
def make_window_file_sync_write():
    layout = [[sg.Text('Choose sync file:', key='-SPECIFY_SYNC_FILE_WRITE-'),
               sg.FileBrowse(file_types=(("sync file", '*.txt'),),  target='-SYNC_FILE_WRITE-', disabled=False),
               sg.InputText('specify-config-microscope', key='-SYNC_FILE_WRITE-')],
              [sg.HorizontalSeparator()],
              [sg.Button('Initiate sync file', key='-INIT_FILE_SYNC_WRITE-')],
              ]
    return sg.Window('File-synchronization : write', layout, finalize=True)


# Window for acquisition synchronization via a text file with changing content
def make_window_file_sync_create():
    layout = [[sg.Text('Folder for sync file:', size=(18, 1)),
               sg.FolderBrowse(target='-PATH_SYNC_FILE_CREATE-', initial_folder="C:\\Temp"),
               sg.InputText('folder-save-sync-file', key='-PATH_SYNC_FILE_CREATE-', enable_events=True)],
              [sg.Text('Name of sync file:', size=(18, 1)),
               sg.InputText('acquisition_start.txt', key='-NAME_SYNC_FILE_CREATE-')],
              [sg.HorizontalSeparator()],
              [sg.Button('Initiate sync file', key='-INIT_FILE_SYNC_CREATE-'),
               sg.InputText('', key='-SYNC_FILE_CREATE-', enable_events=True)],
              ]
    return sg.Window('File-synchronization : write', layout, finalize=True)

# Window for fluidics control
def make_window_fluidics():
    layout = [[sg.Text('Fluidics specification')],
              [sg.Input(key='-IN-', enable_events=True)],
              [sg.Text(size=(25, 1), k='-OUTPUT-')],
              [sg.Button('Erase'), sg.Button('Popup'), sg.Button('Exit')]]

    layout = [
        [sg.Text(' >> System configuration [hardware] <<')],
        [sg.Text('Choose config file: '),
         sg.FileBrowse(file_types=(("json config", 'system_config*.json'), ("json", '*.json')),  target='-CONFIG_SYSTEM-'),
         sg.InputText('specify-system-config-file', key='-CONFIG_SYSTEM-'),
         sg.Button('Initiate robot & open serial ports', key='-INITIATE_SYSTEM-', disabled=True)],

        [sg.HorizontalSeparator()], 
        [sg.Text(' >>  Zero pipette robot over well A1 <<')],
        [sg.Text('Jog distance [mm]'), sg.InputText(size=(4, None), key='-JOG_DIST-', default_text='10'),
         sg.Button('X-', key='-JOG_X--', disabled=True),
         sg.Button('X+', key='-JOG_X+-', disabled=True),
         sg.Button('Y-', key='-JOG_Y--', disabled=True),
         sg.Button('Y+', key='-JOG_Y+-', disabled=True),
         sg.Button('Z-', key='-JOG_Z--', disabled=True),
         sg.Button('Z+', key='-JOG_Z+-', disabled=True)],
        [sg.Button('Zero stage', key='-ZERO_STAGE-', disabled=True)],

        [sg.HorizontalSeparator()],
        [sg.Text(' >>  Experiment properties <<')],
        [sg.Text('Choose config file: '),
         sg.FileBrowse(file_types=(("yaml config", 'experiment_config*.yaml'), ("yaml", '*.yaml')),  target='-EXP_FILE-'),
         sg.InputText('specify-experiment-config-file', key='-EXP_FILE-'),
         sg.Button('Load experiment config', key='-LOAD_EXP_CONFIG-', disabled=True)],

        [sg.HorizontalSeparator()],
        [sg.Text(' >>  Prime / wash fluidics lines <<')],
        [sg.Text('Choose buffer: '),
         sg.Combo(['To-be-specified'], key='-BUFFER_LIST-'),
         sg.Button('Go to buffer', key='-SELECT_BUFFER-', disabled=True),
         sg.Button('Move to ZERO', key='-MOVE_ZERO-', disabled=True)],
        [sg.Text('Outlet valve: '),
         sg.Combo(['Not-available'], key='-OUTLET_VALVE_LIST-'),
         sg.Button('Select valve', key='-SELECT_OUTLET_VALVE-', disabled=True)],
        [sg.Text('Pump time [s]'),
         sg.InputText(size=(4, None), key='-PUMP_TIME-', default_text='30'),
         sg.Button('Start pump', key='-PUMP-', disabled=True)],

        [sg.HorizontalSeparator()],
        [sg.Text(' >>  Flow sensor <<')],
        [sg.Checkbox('Verify flow', default=False, key='-FLOW_verify-'),
         sg.Text('Expected flow [ml/min]'), sg.InputText(size=(4, None), key='-FLOW_expected-', default_text='0.45'),
         sg.Text('Tolerance'), sg.InputText(size=(4, None), key='-FLOW_tol-', default_text='0.25')],

        [sg.HorizontalSeparator()],
        [sg.Text(' >>  Run sequences <<')],
        [sg.Text('Choose sequence: '),
         sg.Combo(['To-be-specified'], key='-SEQ_LIST-'),
         sg.Button('RUN sequence', key='-RUN_SEQ-', disabled=True),
         sg.Button('STOP sequence', key='-STOP_SEQ-', disabled=False)],

        #[sg.HorizontalSeparator()],
        #[sg.Text(' Pippette robot status'),
        # sg.InputText('', key='-PLATE-STATUS-', readonly=True)],
        ]

    return sg.Window('Fluidics - setup fluidics runs', layout, finalize=True)


# Main function
def main():

    # >>> Start with control window open
    win_ctrl, win_fluidics, win_scope_pycro, win_sync_file_create, win_sync_file_write, win_sync_TTL = make_window_control(), None, None, None, None, None

    # >>> Initiate control objects
    R = None  # Fluidics robot
    M = None  # Microscope
    C = None  # Coordinator

    # >>> Logger
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt="%Y-%m-%d %H:%M:%S")

    now = datetime.now()
    data_string = now.strftime("%Y-%m-%d__%H-%M")
    f_log = f'fluidics__{data_string}.log'
    logger_stream = logging.getLogger('Automator-GUI-STREAM')  # Logs the name of the function
    logger_stream.setLevel(logging.DEBUG)  # DEBUG, INFO, ERROR, CRITICAL
    handler_stream = logging.StreamHandler()
    handler_stream.setFormatter(formatter)
    logger_stream.addHandler(handler_stream)

    logger = logging.getLogger('Automator-GUI')  # Logs the name of the function
    logger.setLevel(logging.DEBUG)  # DEBUG, INFO, ERROR, CRITICAL
    handler = logging.FileHandler(f_log, 'w')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # >>> Event Loop
    while True:

        #  Read event
        window, event, values = sg.read_all_windows(timeout=200)

        # Handle window closing events
        if event == sg.WIN_CLOSED or event == 'Exit':

            if window == win_ctrl:            # if closing control window, exit program
                window.close()
                try:
                    if (R is not None) and not R.status['demo']:
                        try:
                            R.pump.stop()
                        except:
                            logger.error('Could not stop pump.')
         
                        # Zero robot
                        if R.status['robot_zeroed']:    
                            R.plate.move_zero()
                        
                        # Close serial ports
                        R.close_serial_ports()

                    if (M is not None) and (M.__class__.__name__ == 'TTL_sync'):
                        try:
                            M.close_serial_port()
                        except:
                            logger.error('No serial port .')

                except (UnboundLocalError, AttributeError) as e:
                    logger_stream.error('Could not close serial connections')
                    logger.error('Could not close serial connections')
                    logger.info(e)
                    pass
                break

        # ===== UPDATES for different interfaces

        # > Control window
        if win_ctrl:
            if M and R:
                win_ctrl['-INITIATE_CONTROL-'].update(disabled=False)
            else:
                win_ctrl['-INITIATE_CONTROL-'].update(disabled=True)

            if C:
                win_ctrl['-RUN_ALL_ROUNDS-'].update(disabled=False)
            else:
                win_ctrl['-RUN_ALL_ROUNDS-'].update(disabled=True)

        # > Fluidics control
        if win_fluidics:

            if win_fluidics['-CONFIG_SYSTEM-'].get() == 'specify-system-config-file':
                win_fluidics['-INITIATE_SYSTEM-'].update(disabled=True)
            else:
                win_fluidics['-INITIATE_SYSTEM-'].update(disabled=False)

            if (win_fluidics['-EXP_FILE-'] == 'specify-experiment-config-file') or (R is None):
                win_fluidics['-LOAD_EXP_CONFIG-'].update(disabled=True)
            else:
                win_fluidics['-LOAD_EXP_CONFIG-'].update(disabled=False)

            # Zeroing robot is necessary to enable controls
            if R is not None:
                if R.status['ports_assigned']:
                    win_fluidics['-ZERO_STAGE-'].update(disabled=False)
                    win_fluidics['-LOAD_EXP_CONFIG-'].update(disabled=False)
                    win_fluidics['-INITIATE_SYSTEM-'].update(disabled=True)  # once ports are assigned, no more scan possible ... leads to crashes

                if R.status['robot_zeroed']:
                    win_fluidics['-JOG_Z+-'].update(disabled=True)
                    win_fluidics['-JOG_Z--'].update(disabled=True)
                    win_fluidics['-JOG_X+-'].update(disabled=True)
                    win_fluidics['-JOG_X--'].update(disabled=True)
                    win_fluidics['-JOG_Y+-'].update(disabled=True)
                    win_fluidics['-JOG_Y--'].update(disabled=True)
                    win_fluidics['-ZERO_STAGE-'].update(disabled=True)
                else:
                    win_fluidics['-JOG_Z+-'].update(disabled=False)
                    win_fluidics['-JOG_Z--'].update(disabled=False)
                    win_fluidics['-JOG_X+-'].update(disabled=False)
                    win_fluidics['-JOG_X--'].update(disabled=False)
                    win_fluidics['-JOG_Y+-'].update(disabled=False)
                    win_fluidics['-JOG_Y--'].update(disabled=False)

                if R.status['experiment_config'] and R.status['robot_zeroed']:
                    win_fluidics['-RUN_SEQ-'].update(disabled=False)
                    win_fluidics['-SELECT_BUFFER-'].update(disabled=False)
                    win_fluidics['-MOVE_ZERO-'].update(disabled=False)
                    if R.status['outlet_valve']: 
                        win_fluidics['-SELECT_OUTLET_VALVE-'].update(disabled=False)
                    else:
                        win_fluidics['-SELECT_OUTLET_VALVE-'].update(disabled=True)
                else:         
                    win_fluidics['-RUN_SEQ-'].update(disabled=True)
                    win_fluidics['-SELECT_BUFFER-'].update(disabled=True)
                    win_fluidics['-MOVE_ZERO-'].update(disabled=True)
                    win_fluidics['-SELECT_OUTLET_VALVE-'].update(disabled=True)

                # Pump: can be started only after buffer was selected
                if R.status['experiment_config'] and R.status['robot_zeroed'] and R.status['buffer_selected']:
                    win_fluidics['-PUMP-'].update(disabled=False)
                else:
                    win_fluidics['-PUMP-'].update(disabled=True)

                # Permit running a demo run if specified
                if R.status['demo'] and R.status['experiment_config']:
                    win_fluidics['-RUN_SEQ-'].update(disabled=False)

                # Disable verify flow is no sensor is specified
                if  R.sensor == None:
                    win_fluidics['-FLOW_verify-'].update(disabled=True)
                    

        # >> pycromanger control
        if win_scope_pycro:

            if win_scope_pycro['-CONFIG_SCOPE-'].get() == 'specify-config-microscope':
                win_scope_pycro['-LOAD_CONFIG_MICROSCOPE-'].update(disabled=True)
            else:
                win_scope_pycro['-LOAD_CONFIG_MICROSCOPE-'].update(disabled=False)

            if M:

                if win_scope_pycro['-POS_LIST-'].get() == 'specify-pos-list':
                    win_scope_pycro['-LOAD_POS_LIST-'].update(disabled=True)
                else:
                    win_scope_pycro['-LOAD_POS_LIST-'].update(disabled=False)   

                if M.status['config']:
                    win_scope_pycro['-OPEN_MICRO_MANAGER-'].update(disabled=False)
                else:
                    win_scope_pycro['-OPEN_MICRO_MANAGER-'].update(disabled=True)

                if M.status['config'] and M.status['micromanger_connect'] and M.status['positions']:
                    win_scope_pycro['-CREATE_ACQUISITION_EVENT-'].update(disabled=False)
                else:
                    win_scope_pycro['-CREATE_ACQUISITION_EVENT-'].update(disabled=True)

                if M.status['acquisition_event'] and not (win_scope_pycro['-DIR_SAVE_IMGS-'].get() == 'folder-save-images'):
                    win_scope_pycro['-LAUNCH_ACQUISITION-'].update(disabled=False)
                else:
                    win_scope_pycro['-LAUNCH_ACQUISITION-'].update(disabled=True)

        #  Handle events
        if event == '__TIMEOUT__':
            pass
        #    if win_fluidics:
        #        win_fluidics.Element('-PLATE-STATUS-').update(value='----')

        #        if (R is not None) and not R.status['demo']:
        #            if R.status['ports_assigned']:
        #                win_fluidics.Element('-PLATE-STATUS-').update(value=R.plate.check_stage())

        # ******************************************************************************************************
        # >> Main control interface
        # ******************************************************************************************************
        elif event == '-Window-Scope-':

            scope_sync = win_ctrl['-SCOPE_SYNC-'].get()

            if (scope_sync == 'pycromanager') and (not win_scope_pycro):
                win_scope_pycro = make_window_pycromanager()
            elif (scope_sync == 'file synce - create'):
                win_sync_file_create = make_window_file_sync_create()
            elif (scope_sync == 'file sync - write'):
                win_sync_file_write = make_window_file_sync_write()
            elif (scope_sync == 'TTL sync'):
                win_sync_TTL = make_window_TTL_sync()

        elif event == '-Window-Fluidics-' and not win_fluidics:
            win_fluidics = make_window_fluidics()

        elif event == 'Popup':
            sg.popup('This is a BLOCKING popup', 'all windows remain inactive while popup active')

        elif event == '-INITIATE_CONTROL-':
            C = Controller(Robot=R, Microscope=M, logger=logger, logger_short=logger_stream)

        elif event == '-RUN_ALL_ROUNDS-':
            C.run_all_rounds(dir_save=win_ctrl["-OUTPUT_DIR_SAVE_IMGS-"].get())
            win_fluidics['-SEQ_LIST-'].update(values=R.rounds_available)

        # ******************************************************************************************************
        # >> text file sync : write
        # ******************************************************************************************************
        elif event == '-INIT_FILE_SYNC_WRITE-':
            if not M:
                M = fileSync_write(logger=logger, logger_short=logger_stream)
            M.initiate_sync_file(values['-SYNC_FILE_WRITE-'])

        # ******************************************************************************************************
        # >> text file sync : write
        # ******************************************************************************************************
        elif event == '-INIT_FILE_SYNC_CREATE-':
            if not M:
                M = fileSync_create(logger=logger, logger_short=logger_stream)
            sync_file = M.initiate_sync_file(path_sync_file=values['-PATH_SYNC_FILE_CREATE-'],
                                             name_sync_file=values['-NAME_SYNC_FILE_CREATE-'],)
            if not isinstance(sync_file, pathlib.PurePath):
                sg.popup_error('Setting sync file did not work, likely the file already exists. Please delete. More infos in the log.')
            win_sync_file_create['-SYNC_FILE_CREATE-'].update(str(sync_file))

        # ******************************************************************************************************
        # >> TTL sync
        # ******************************************************************************************************
        elif event == '-INIT_TTL_SYNC-':
            if not M:
                M = TTL_sync(logger=logger, logger_short=logger_stream)
            TTL_sync_success = M.connect_serial_port(file_config_TTL=values['-TTL_CONFIG_FILE-'])
            print(TTL_sync_success)
            if TTL_sync_success:
                win_sync_TTL['-INIT_TTL_SYNC-'].update(disabled=True)

        # ******************************************************************************************************
        # >> pycroManager
        # ******************************************************************************************************        
        elif event == "-LOAD_CONFIG_MICROSCOPE-":
            if not M:
                M = pycroManager(logger=logger, logger_short=logger_stream)
            M.load_config_file(values['-CONFIG_SCOPE-'])

        elif event == "-LOAD_POS_LIST-":
            M.load_position_list(file_pos=values["-POS_LIST-"])

        elif event == "-OPEN_MICRO_MANAGER-":
            # mm_headless = win_scope_pycro["-MM_headless-"].get()
            mm_headless = values["-MM_headless-"]
            M.mm_connect(mm_headless)

        elif event == "-CREATE_ACQUISITION_EVENT-":
            M.create_acquisition_event()

        elif event == "-LAUNCH_ACQUISITION-":
            try:
                M.acquire_images(
                    dir_save=values["-DIR_SAVE_IMGS-"],
                    name_base=values["-NAME-ACQUISITION-"])
            except (UnboundLocalError, AttributeError) as e:
                logger_stream.error('Acquisition failed. More details in detailed log.')
                logger.error('Acquisition failed.')
                logger.error(e)

        elif event == '-DIR_SAVE_IMGS-':
            win_ctrl['-OUTPUT_DIR_SAVE_IMGS-'].update(values["-DIR_SAVE_IMGS-"])

        # ******************************************************************************************************
        # >> FLUIDICS system
        # ******************************************************************************************************
        elif event == '-INITIATE_SYSTEM-':
            logger_stream.info(f'Initiate Robot & open serial ports. More info in log {f_log}')

            try:
                R = Robot(values['-CONFIG_SYSTEM-'], logger=logger, logger_short=logger_stream)
                R.initiate_system()
                window['-INITIATE_SYSTEM-'].update(disabled=True)

            except (UnboundLocalError, AttributeError):
                logger_stream.error('Opening of serial ports failed.')
                logger.error('Opening of serial ports failed.')

        elif event == '-LOAD_EXP_CONFIG-':
            logger_stream.info('Load robot configuration. More infos in log.')
            try:
                R.load_config_experiment(values['-EXP_FILE-'])
                window['-BUFFER_LIST-'].update(values=R.buffer_names)
                window['-BUFFER_LIST-'].update(value=R.buffer_names[0])
                window['-SEQ_LIST-'].update(values=R.rounds_available)
                window['-SEQ_LIST-'].update(value=R.rounds_available[0])
                window['-OUTLET_VALVE_LIST-'].update(values=R.valve_out_settings['positions'])
                window['-OUTLET_VALVE_LIST-'].update(value=R.valve_out_settings['positions'][0])
                R.status['experiment_config'] = True

            except (FileNotFoundError, KeyError) as e:
                logger_stream.error('Please provide a valid config file to initiate robot.')
                logger.info('Please provide a valid config file to initiate robot.')
                logger.error(e)

        # >>>>> JOGGING COMMANDS
        elif event == '-JOG_X--':
            jog_dist = float(values['-JOG_DIST-'])
            try:
                R.plate.jog_stage('X-', jog_dist)
            except (UnboundLocalError, AttributeError) as e:
                logger_stream.info('Jog X- failed.')
                logger.info('Jog X- failed.')
                logger.error(e)

        elif event == '-JOG_X+-':
            jog_dist = float(values['-JOG_DIST-'])
            try:
                R.plate.jog_stage('X', jog_dist)
            except (UnboundLocalError, AttributeError) as e:
                logger_stream.info('Jog failed X+.') 
                logger.info('Jog failed X+.') 
                logger.error(e)

        elif event == '-JOG_Y--':               
            jog_dist = float(values['-JOG_DIST-'])
            try:
                R.plate.jog_stage('Y-', jog_dist)
            except (UnboundLocalError, AttributeError) as e:
                logger_stream.info('Jog failed. Y-')
                logger.info('Jog failed.')
                logger.error(e)

        elif event == '-JOG_Y+-':
            jog_dist = float(values['-JOG_DIST-'])
            try:
                R.plate.jog_stage('Y', jog_dist)
            except (UnboundLocalError, AttributeError) as e:
                logger_stream.info('Jog failed. Y+')
                logger.info('Jog failed. Y+')
                logger.error(e)       

        elif event == '-JOG_Z--':   
            jog_dist = float(values['-JOG_DIST-'])
            try:
                R.plate.jog_stage('Z-', jog_dist)
            except (UnboundLocalError, AttributeError) as e:
                logger_stream.info('Jog failed. Z-')
                logger.info('Jog failed. Z-')
                logger.error(e)

        elif event == '-JOG_Z+-':
            jog_dist = float(values['-JOG_DIST-'])
            try:
                R.plate.jog_stage('Z', jog_dist)
            except (UnboundLocalError, AttributeError) as e:
                logger_stream.info('Jog failed. Z+')
                logger.info('Jog failed. Z+')
                logger.error(e)  

        # >>>>> Zero stage and move to zero

        elif event == '-ZERO_STAGE-':
            try:
                R.plate.zero_stage()
                R.status['robot_zeroed'] = True

            except (UnboundLocalError, AttributeError) as e:
                logger_stream.error('Zero stage fail failed.')
                logger.error('Zero stage fail failed.')
                logger.error(e)

        elif event == '-MOVE_ZERO-':
            R.plate.move_zero()

        # >>>>> Priming/WASHING lines
        elif event == '-SELECT_BUFFER-':
            try:
                buffer_sel = values['-BUFFER_LIST-']
                R.select_buffer(buffer_sel)
                R.status['buffer_selected'] = True

            except (UnboundLocalError, AttributeError) as e:
                logger.error(f'Could not select buffer: {buffer_sel}')
                logger.error(e)

        elif event == '-PUMP-':
            try:
                pump_time = float(values['-PUMP_TIME-'])
                R.flow['verify'] = values['-FLOW_verify-']
                R.flow['expected'] = float(values['-FLOW_expected-'])
                R.flow['tolerance'] = float(values['-FLOW_tol-'])

                R.pump_run(pump_time)
                R.status['buffer_selected'] = False

            except (UnboundLocalError, AttributeError) as e:
                logger_stream.error(f'Could not activate pump for specified duration: {pump_time}')
                logger.error(e)

        # >>>>> Outlet valve
        elif event == '-SELECT_OUTLET_VALVE-':
            try:
                valve_out_id = values['-OUTLET_VALVE_LIST-']
                R.valve_out.move(valve_out_id)

            except (UnboundLocalError, AttributeError) as e:
                logger.error(f'Could not select outlet valve: {valve_out}')
                logger.error(e)


        # >>>>> Run single round
        elif event == '-RUN_SEQ-':
            try:
                round_id = values['-SEQ_LIST-']
                run_single_round_thread = threading.Thread(target=R.run_single_round,
                                                           args=(round_id,))
                run_single_round_thread.start()
                run_single_round_thread.join()  # Interpreter will wait until your process get completed or terminated
                window['-SEQ_LIST-'].update(values=R.rounds_available)

                if len(R.rounds_available) > 0:
                    window['-SEQ_LIST-'].update(value=R.rounds_available[0])

            except (UnboundLocalError, AttributeError) as e:
                logger_stream.error(f'Could not run round: {round_id}')
                logger.error(f'Could not run round: {round_id}')
                logger.error(e)

        elif event == '-STOP_SEQ-':
            try:
                round_id = values['-SEQ_LIST-']
                R.stop.set()
                if not run_single_round_thread.is_alive():
                    logger.info('Robot stopped')
            except (UnboundLocalError, AttributeError) as e:
                logger_stream.error(f'Could not STOP round: {round_id}')
                logger.error(f'Could not STOP round: {round_id}')
                logger.error(e)

    window.close()


if __name__ == '__main__':
    main()
