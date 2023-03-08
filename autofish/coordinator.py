import logging

class Controller():

    def __init__(self, Robot, Microscope,logger=None, logger_short=None):
        
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

        # Assign control object for fluidic robot and microscope control
        self.R = Robot
        self.M = Microscope
        
        
    # Function to handle both logging calls and different logging types
    def log_msg(self,type,msg,msg_short=''):
        
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
   
        
        
    # Function to run ALL rounds (in order listed )
    def run_all_rounds(self, dir_save):
    
        while len(self.R.rounds_available) > 0:
            round_id = self.R.rounds_available[0]
            
            # >> Perform fluidics
            self.log_msg('info', f'Running next ROUND {round_id}')
            self.R.run_single_round(round_id)

            # ToDo: check that fluidics run worked out
            
            # Acquire images
            if self.R.status['launch_acquisition']:
                
                # Acquisition with file sync
                if (self.M.__class__.__name__) == 'fileSync':
                    self.M.acquire_images()
                    
                # Acquisition with pycromanager
                elif (self.M.__class__.__name__) == 'pycroManager':

                    # This should help to repeat acquisitions in case of a crash    
                    acquisition_needed = True    

                    while acquisition_needed:
                        try:
                            self.M.acquire_images(
                                dir_save = dir_save,
                                name_base= f'{round_id}')
                            acquisition_needed = False
                            
                        except Exception as e:
                            self.log_msg('error',f'Problems during acquisition ({e}).')
                            
                            # Ask user if acquisition should be repeated
                            self.log_msg('info', f'WAITING FOR USER INPUT ... type "again" to repeat acquisition')
                            usr_input = input('WAITING FOR USER INPUT ... type "again" to repeat acquisition, otherwise run will continue.\n')  
                            if usr_input == 'again':
                                acquisition_needed = True
                            else:
                                acquisition_needed = False
                    
            # ToDo: check that acquisition worked out
            # ToDo: create thread also for imaging (or combined wiht fluidics)
           