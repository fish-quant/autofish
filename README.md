# Automator

Python library to control an automated fluidics system and perform microscope acquisition for iterative FISH experiments.

See dedicated documentation [**here**](https://github.com/fish-quant/autofish/blob/master/docs/automator_manual.pdf) for how to install and use this package.

**TESTED FOR WIN 10 only**: micromanager and most microscope controls work only under Windows.

![fluidics-system](docs/fluidics-overview.png)

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

See dedicated documentation [**here**](https://github.com/fish-quant/autofish/blob/master/docs/fluidics__construction.pdf) for how to build the fluidics system.