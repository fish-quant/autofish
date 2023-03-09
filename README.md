![GitHub](https://img.shields.io/github/license/fish-quant/autofish)
[![Python 3.7](https://img.shields.io/badge/python-3.7-blue.svg)](https://www.python.org/downloads/release/python-370/)

# Automator

Python library to control an automated fluidics system and perform microscope acquisition for iterative FISH experiments.

See dedicated documentation [**here**](https://github.com/fish-quant/autofish/blob/master/docs/autofish_manual.pdf) for how to install and use this package.

**TESTED FOR WIN 10 only**: micromanager and most microscope controls work only under Windows.

![fluidics-system](docs/fluidics-overview.png)

## Getting started

### Installation

1. Download latest version of miniconda from [**here**](https://docs.conda.io/en/latest/miniconda.html) (can also be Python 3.X).
2. Open Anaconda terminal and create dedicated environment: `conda create --name autofish python=3.9`
3. Activate environment: `conda activate autofish`
4. Pip install `pip install -i https://test.pypi.org/simple/ autofish`

### Starting autofish

1. Open Anaconda terminal and activate environment: `conda activate autofish`
2. Start user interface with command `autofish`

### Building the Fluidics system

See dedicated documentation [**here**](https://github.com/fish-quant/autofish/blob/master/docs/fluidics_construction.pdf) for how to build the fluidics system.


## Reporting a problem/suggestion

If you encounter a problem or you have a suggestion, please file an [**issue**](https://github.com/fish-quant/autofish/issues).
