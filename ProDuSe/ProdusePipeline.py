#! /usr/bin/env python

import argparse
import os
import subprocess
# import glob
import sys

cwd = os.path.abspath(".") + os.sep
scriptLoc = os.path.abspath(os.path.dirname(__file__)) + os.sep
# stitcherDefault = glob.glob(scriptLoc + os.sep + "Pisces*" + os.sep + "redist" + os.sep + "Stitcher.exe")[0]

parser = argparse.ArgumentParser(description="Runs all stages of the ProDuce pipeline on the provided samples")
parser.add_argument("-sc", "--sampleconfig", required=True, type=lambda x: isValidFile(x), help="Sample Configuration File")
parser.add_argument("-c", "--produceconfig", required=True, type=lambda x: isValidFile(x), help="Produce Configuration File")
parser.add_argument("-r", "--refgenome", required=True, type=lambda x: isValidFile(x), help="Reference genome, in FASTA format")
parser.add_argument("-d", "--outdir", default=cwd, help="Output directory [Default: %(default)s]")
parser.add_argument("-e", "--scriptdir", default=scriptLoc, help="Directory containing Produce Scripts [Default: %(default)s]")
parser.add_argument("-x", "--stitcherpath", required=True, help="Path to Stitcher.exe [Default: %(default)s]")
parser.add_argument("-t", "--threads", default=1, type=int, help="Number of threads to use while running BWA [Default: %(default)s]")
parser.add_argument("-v", "--vaf", default=0.05, type=float, help="Variant Allele Fraction (VAF) threshold used in variant filtering [Default: %(default)s]")


def isValidFile(file):

	if os.path.exists(file):
		return file
	else:
		print("ERROR: Unable to locate " + file)
		print("Please ensure the file exists")
		exit()


def createLogFile(args, logFile="ProDuSe_Task.log"):
	"""
		Creates a log file in the cwd specifying the arguments that ProDuSe was run with

		Input:
			args: A namespace object listing ProDuSe arguments
	"""

	logString = ["python", sys.argv[0]]

	# Add each argument to the logString
	for argument, parameter in vars(args).items():
		logString.extend(["--" + argument, parameter])

	with open(logFile, "w") as o:
		for item in logString:
			o.write(str(item) + " ")
		o.write("\n")


def runConfig(sConfig, pConfig, refGenome, outDir, scriptDir):

	scriptPath = scriptDir + os.sep + "configure_produse.py"
	if not os.path.exists(scriptPath):
		print("ERROR: Unable to locate configure_produce.py in " + scriptDir + os.sep)
		print("Please ensure the script exists")
		exit(1)

	configArgs = ["python", scriptPath, "-o", outDir + os.sep, "-c", pConfig, "-sc", sConfig, "-r", refGenome]
	subprocess.check_call(configArgs)


def getSampleList(outDir):

	# Generates a list of samples by listing all directoies created in 'produce_analysis_directory'
	if not os.path.exists(outDir + os.sep + "produse_analysis_directory" + os.sep):
		print("ERROR: configure_produce.py did not complete sucessfully")
		exit(1)

	sampleList = next(os.walk(outDir + os.sep + "produse_analysis_directory" + os.sep))[1]
	return sampleList


def processSample(sample, sampleDir, scriptDir, threads, stitcherPath, vaf):

	def runTrim(sampleDir, scriptDir):

		scriptPath = scriptDir + os.sep + "trim.py"
		trimConfig = sampleDir + os.sep + "config" + os.sep + "trim_task.ini"

		if not os.path.exists(scriptPath):
			print("ERROR: Unable to locate \'trim.py\'' in " + scriptDir)
			print("Please ensure the script exists")
			exit(1)
		elif not os.path.exists(trimConfig):
			print("ERROR: Unable to locate \'trim_task.ini\' in " + sampleDir)
			print("Ensure that \'configure_produce.py\' completed successfully")
			exit(1)

		trimArgs = ["python", scriptPath, "-c", trimConfig]
		subprocess.check_call(trimArgs)

	def runBWA(config, scriptDir, threads):

		scriptPath = scriptDir + os.sep + "bwa.py"
		if not os.path.exists(scriptPath):
			print("ERROR: Unable to locate \'bwa.py\'' in " + scriptDir)
			print("Please ensure the script exists")
			exit(1)
		elif not os.path.exists(config):
			print("ERROR: Unable to locate " + config)
			print("Ensure that \'configure_produce.py\' completed successfully")
			exit(1)

		bwaArgs = ["python", scriptPath, "-c", config, "-t", str(threads)]
		subprocess.check_call(bwaArgs)

	def runCollapse(sampleDir, scriptDir):

		scriptPath = scriptDir + os.sep + "collapse.py"
		collapseConfig = sampleDir + os.sep + "config" + os.sep + "collapse_task.ini"

		if not os.path.exists(scriptPath):
			print("ERROR: Unable to locate \'collapse.py\'' in " + scriptDir)
			print("Please ensure the script exists")
			exit(1)
		elif not os.path.exists(collapseConfig):
			print("ERROR: Unable to locate \'collapse_task.ini\' in " + sampleDir)
			print("Ensure that \'configure_produce.py\' completed successfully")
			exit(1)

		collapseArgs = ["python", scriptPath, "-c", collapseConfig]
		subprocess.check_call(collapseArgs)

	def runStitcher(sampleDir, stitcherPath):

		if not os.path.exists(stitcherPath):
			print("ERROR: Unable to locate " + stitcherPath)
			print("Please ensure the executable exists")
			exit(1)

		bamFile = sampleDir + os.sep + "data" + os.sep + "collapse.bam"
		outDir = sampleDir + os.sep + "data" + os.sep

		stitcherArgs = ["mono", stitcherPath, "--Bam", bamFile, "--OutFolder=" + outDir]
		subprocess.check_call(stitcherArgs)

	def runSort(bamFile):

		outFile = bamFile.replace(".bam", ".sorted.bam")
		samtoolsArgs = ["samtools", "sort", "-o", outFile, bamFile]
		subprocess.check_call(samtoolsArgs)
		return outFile

	def runSplitMerge(outName, bamFile, scriptDir):

		scriptPath = scriptDir + os.sep + "splitmerge.pl"
		if not os.path.exists(scriptPath):
			print("ERROR: Unable to locate \'splitmerge.pl\' in " + scriptDir)
			print("Please ensure the script exists")

		preSMViewArgs = ["samtools", "view", "-h", bamFile]
		postSMViewArgs = ["samtools", "view", "-b"]

		with open(outName, "w") as o:
			preSMView = subprocess.Popen(preSMViewArgs, stdout=subprocess.PIPE)
			exSM = subprocess.Popen(scriptPath, stdin=preSMView.stdout, stdout=subprocess.PIPE)

			subprocess.check_call(postSMViewArgs, stdin=exSM.stdout, stdout=o)

	def runSNV(config, sampleDir, scriptDir):

		scriptPath = scriptDir + os.sep + "snv.py"
		snvArgs = ["python", scriptPath, "-c", config]
		subprocess.check_call(snvArgs)

	def runFilter(scriptDir, vaf, vcfFile):

		scriptPath = scriptDir + os.sep + "filter_produse.pl"
		filterArgs = ["perl", scriptPath, str(vaf)]
		outFile = sampleDir + os.sep + "results" + os.sep + "variants.filtered.vcf"

		with open(vcfFile) as f, open(outFile, "w") as o:
			subprocess.Popen(filterArgs, stdin=f, stdout=o)

	runTrim(sampleDir, scriptDir)
	print(sample + ": Trimming Complete")

	trimBwaConfig = sampleDir + os.sep + "config" + os.sep + "trim_bwa_task.ini"
	runBWA(trimBwaConfig, scriptDir, threads)
	print(sample + ": Mapping Complete")

	runCollapse(sampleDir, scriptDir)
	print(sample + ": Collapsing Complete")

	collapseBwaConfig = sampleDir + os.sep + "config" + os.sep + "collapse_bwa_task.ini"
	runBWA(collapseBwaConfig, scriptDir, threads)
	print(sample + ": Mapping Complete")

	runStitcher(sampleDir, stitcherPath)
	print(sample + ": Stitcher Complete")

	sortedStitchBAM = runSort(sampleDir + os.sep + "data" + os.sep + "collapse.stitched.bam")

	splitMergeName = sampleDir + os.sep + "results" + os.sep + "SplitMerge.bam"
	runSplitMerge(splitMergeName, sortedStitchBAM, scriptDir)
	print(sample + ": SplitMerge Complete")

	print(sample + ": Calling SNVs...")
	runSort(splitMergeName)
	snvConfig = sampleDir + os.sep + "config" + os.sep + "snv_task.ini"
	runSNV(snvConfig, sampleDir, scriptDir)
	print(sample + ": SNV Calling Complete")

	vcfFile = sampleDir + os.sep + "results" + os.sep + "variants.vcf"
	runFilter(scriptDir, vaf, vcfFile)
	print(sample + ": Filtering Complete")

	print(sample + ": ProDuSe Complete. Output in " + sampleDir + os.sep + "results" + os.sep)


def main(args=None):

	if args is None:
		args = parser.parse_args()

	if not os.path.isfile(args.stitcherpath):

		print("ERROR: Unable to locate Stitcher.exe in " + os.path.dirname(args.stitcherpath))
		exit(1)

	createLogFile(args, args.outdir + os.sep + "ProDuSe_Task.log")
	runConfig(args.sampleconfig, args.produceconfig, args.refgenome, args.outdir, args.scriptdir)
	sampleList = getSampleList(args.outdir)

	for sample in sampleList:

		print("Processing sample " + sample)
		sampleDir = args.outdir + os.sep + "produse_analysis_directory" + os.sep + sample
		processSample(sample, sampleDir, args.scriptdir, args.threads, args.stitcherpath, args.vaf)

	print("ProDuSe Complete. All samples processed")


if __name__ == "__main__":

	print("")
	main()
