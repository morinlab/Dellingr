#!/usr/bin/env python

"""
Resumes a previously terminated analysis. Only works for analysis generated using Dellingr version 0.9 and above
"""

import argparse
import os
import sys
import multiprocessing

try:
    import DellingrPipeline
except ImportError:
    from Dellingr import DellingrPipeline


def isValidDir(dir, parser):
    """
    Checks to ensure that the specified directory exists

    :param dir: A string containing a filepath to the directory
    :param parser: An argparse.ArgumentParser()object, or equivelent
    :return: dir: The same string
    :raises: parser.error: If the specified directory does not exist
    """

    if not os.path.isdir(dir):
        raise parser.error("Unable to locate directory %s" % dir)
    else:
        return dir

def getArgs(stdin):

    parser = argparse.ArgumentParser(description="Resumes analysis of a previously terminated Pipeline")
    parser.add_argument("-d", "--dellingr_dir", type=lambda x: isValidDir(x, parser), required=True, help="An existing output directory for Dellingr analysis")
    parser.add_argument("-j", "--jobs", metavar="INT", default=1, type=int, help="Number of samples to process in parallel")
    parser.add_argument("--cleanup", action="store_true", help="Once a sample is processed, remove intermediate files")
    if stdin is None:
        return parser.parse_args()
    else:
        return parser.parse_args(stdin)


def main(args=None, sysStdin=None):
    if args is None:
        args = getArgs(sysStdin)

    args = vars(args)
    args["dellingr_dir"] = os.path.abspath(args["dellingr_dir"])
    # Assuming that the directory the user provided is actually a "dellingr_analysis_directory", we need to figure out what samples are in it
    # Since each directory corresponds to a different sample, obtain a list of all subdirectories
    samples = list(os.path.join(args["dellingr_dir"], x) for x in os.listdir(path = args["dellingr_dir"]) if os.path.isdir(os.path.join(args["dellingr_dir"], x)))

    # To actually check that this is a "dellingr_analysis_directory", check for the required config files for each sample
    validSamples = {}
    requiredConfigs = ["bwa_task.ini", "collapse_task.ini", "call_task.ini"]
    for sample in samples:
        validSample = True
        for config in requiredConfigs:
            configPath = os.path.join(sample, "config", config)
            if not os.path.exists(configPath):
                validSample = False
                break

        if validSample:
            sampleName = os.path.basename(sample)
            validSamples[sampleName] = sample

    # If no valid samples were found, then this is not a valid analysis directory
    if len(validSamples) == 0:
         sys.stderr.write("ERROR: Unable to find any valid sample directories in \"%s\". Check that this a directory was created by \"run_dellingr\", and that configuration completed sucessfully." % args["dellingr_dir"] + os.linesep)

    # If multiple samples are to be processed in parallel
    if args["jobs"] == 0:
        threads = None
    else:
        threads = min(len(validSamples), args["jobs"], os.cpu_count())
    if threads > 1 or threads is None:
        # Convert the dictionary which contains the sample arguments into a list of tuples, for multithreading use
        # In addition, to keep the command line status messages semi-reasonable, normalize for sample name length
        maxLength = max(len(x) for x in validSamples.keys())
        multithreadArgs = list((x.ljust(maxLength, " "), y, args["cleanup"]) for x, y in validSamples.items())

        processPool = multiprocessing.Pool(processes=threads)
        try:
            # Run the jobs
            processPool.imap_unordered(DellingrPipeline.runPipelineMultithread, multithreadArgs)
            processPool.close()
            processPool.join()
        except Exception as e:
            sys.stderr.write("Error occured while processing sample. Terminating workers..." + os.linesep)
            processPool.terminate()
            raise e
    # Obtain the sample name, and re-run this sample
    for sampleName, sPath in validSamples.items():
        DellingrPipeline.runPipeline(sampleName, sPath, args["cleanup"])


if __name__ == "__main__":
    main()
