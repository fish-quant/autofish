# Typical seqFISH experiment

This describes the typical workflow to setup a sequential FISH exeriment. 
The first round contains a DAPI stain. 
Only for this round the DAPI image is acquired.
Imaging settings are defined after the first round, since here cells can be seen.
From here on, the rest of the experiment is automated. 

## Preparation

1. Samples
2. Fluidics system
    - Define experimental settings in config file.
    - Start fluidics flow sensor and start logging into file.
    - Start autoFISH and initiate (read config files, zero robot)
    - Prime lines and check flow (replace tubing if necessary)
    - Hardware (easy to forget)
        - Temperature control (both objective and chamber)
        - Vacuum pump

## Actual experiment

1. Run first round (including DAPI)
2. Setup acquisition 
    - Include DAPI channel
    - Save position list
    - Acquire images
3. Setup imaging
    - Adjust microscope config file: channels and z-stacks
    - Open pycromanager module in autoFISH
        - Load config files (position, micrscope)
        - Specify folder to save images
        - Perform test acquisition
4. Start automated runs
    - Initiate controller
    - Launch all runs

## Once done

1. Clean system
2. Turn off hardware
3. Detach tubing from peristaltic pump