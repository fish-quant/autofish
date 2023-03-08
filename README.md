# Automator

Python library to control an automated fluidics system and perform microscope acquisition for iterative FISH experiments.

See dedicated documentation [**here**](https://github.com/muellerflorian/automator/blob/master/docs/automator_manual.pdf) for how to install and use this package.

__TESTED FOR WIN 10 only__: micromanager and most microscope controls work only under Windows.

## Getting started

### Installation

1. Download latest version of miniconda from [**here**](https://docs.conda.io/en/latest/miniconda.html) (can also be Python 3.X).
2. Open Anaconda terminal and create dedicated environment: `conda create --name autofish python=3.7`
3. Activate environment: `conda activate autofish`
4. Pip install `pip install -i https://test.pypi.org/simple/ autofish==0.0.1`

### Starting autofish

1. Open Anaconda terminal and activate environment: `conda activate autofish`
2. Start user interface with command `autofish`

### Building the Fluidics system

See dedicated documentation [**here**](https://github.com/muellerflorian/automator/blob/master/docs/fluidics__construction.pdf) for how to build the fluidics system.

## Some references

### Serial port communication

https://pythonhosted.org/pyserial/
https://github.com/pyserial/pyserial

### Tools to work with serial ports

- Fee serial port monitor (be careful to download the free version): https://www.com-port-monitoring.com/
