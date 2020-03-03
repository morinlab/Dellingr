[![Build Status](https://travis-ci.org/morinlab/Dellingr.svg?branch=master)](https://travis-ci.org/morinlab/Dellingr)

# Dellingr
An error supression and variant calling pipeline for Second-Generation sequencing data

## Description

See the full wiki page for more information: http://produse.readthedocs.io/en/latest/

## Installation 

### Dependencies

You will need to install the following before installing Dellingr:

* `python>=3.5`
* `bwa>=0.7.0`
* `samtools>=1.3.1`

Dellingr will check these dependencies prior to running the pipeline

To install the Dellingr package run the following command:

### Install using the Python Package Index (PyPI)
```bash
pip install Dellingr
```

### Install from Github
```bash
git clone https://github.com/morinlab/Dellingr.git
cd Dellingr
python setup.py install
```
All required python dependencies will be installed during this step

## Running Dellingr

### The Analysis Pipeline: Very Quick Start

You can view more detailed instructions on the [wiki](http://produse.readthedocs.io/en/latest/)

All parameters required to run ProDuSe can be viewed using the following:
```bash
    dellingr run_dellingr -h
```

Alternatively, if you wish to run Dellingr without installing it, you can run `DellingrPipeline.py` manually in a similar manner:
```bash
    /path/to/Dellingr/DellingrPipeline.py -h
```

While these parameters can be specified individually, they can also be provided using a configuration file

To run the analysis pipeline you simply need to run the following command:
```bash
    dellingr run_dellingr
    -c /path/to/github/clone/etc/dellingr_config.ini
```

Alternatively:
```bash
    /path/to/Dellingr/DellingrPipeline.py 
    -c /path/to/github/clone/etc/dellingr_config.ini
```

This will run the entire Dellingr pipeline on all samples specified in the sample_config.ini file, which can be found in 
etc/sample_config.ini

Results will be located in the following directory:

```bash
ls ./dellingr_analysis_directory
```

### Helper Scripts

The Dellingr package is comprised of several stages to aid in the analysis of duplex sequencing data.

These stages can be be viewed by running the following:

```bash
dellingr -h
```

#### dellingr adapter_predict

If you need to confirm the expected adapter sequence of a sample you should run the following command:

```bash
dellingr adapter_predict -i input1.fastq input2.fastq
```

This tool will print a predicted adapter sequence based off of ACGT abundances at each position. It uses these observed abundances and finds the closest expected abundance for an IUPAC unambiguous or ambiguous base.

#### External links
[The Morin Laboratory at SFU](https://morinlab.github.io/team/)
