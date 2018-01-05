#! /usr/bin/env python

import argparse
import os
import pysam
import sys
import sortedcontainers
from pyfaidx import Fasta
import time
from FisherExact import fisher_exact
from configobj import ConfigObj

class Position:
    """
    Stores the allele counts and associated characteristics at this position
    """

    def __init__(self, refBase):
        self.ref = refBase
        self.alleles = []
        self.qualities = []
        self.famSizes = []
        self.posParent = []
        self.mapStrand = []
        self.distToEnd = []
        self.mismatchNum = []
        self.mappingQual = []
        self.alt = False
        self.altAlleles = set()
        self.readNum = []

    def add(self, base, qual, size, posParent, mapStrand, dist, mapQual, readNum):
        self.alleles.append(base)
        self.qualities.append(qual)
        self.famSizes.append(size)
        self.posParent.append(posParent)
        self.mapStrand.append(mapStrand)
        self.distToEnd.append(dist)
        self.mappingQual.append(mapQual)
        self.readNum.append(readNum)

        if self.ref != base:
            self.alt = True
            if base not in self.altAlleles:
                self.altAlleles.add(base)
            return True
        else:
            return False

    def addMismatchNum(self, misMatchNum):
        self.mismatchNum.append(misMatchNum)

    def processVariant(self, refWindow, nearbyVariants, nWindow):
        self.refWindow = refWindow
        self.nearbyVar = nearbyVariants
        self.nWindow = nWindow  # How many positions were examined to find nearby variants?

    def summarizeVariant(self, strongMoleculeThreshold=3, minDepth=0, minAltDepth=0):
        """
        Summarize the statistics of this position
        :return:
        """

        self.baseCounts = { "DPN":  [0, 0, 0, 0],
                            "DpN":  [0, 0, 0, 0],
                            "DPn":  [0, 0, 0, 0],
                            "Dpn":  [0, 0, 0, 0],
                            "SN" :  [0, 0, 0, 0],
                            "SP" :  [0, 0, 0, 0],
                            "Sp" :  [0, 0, 0, 0],
                            "Sn" :  [0, 0, 0, 0]
                            }
        self.strandCounts = [0.0, 0.0, 0.0, 0.0]
        self.posMolec = [0, 0, 0, 0]
        self.negMolec = [0, 0, 0, 0]

        baseToIndex = {"A": 0, "C": 1, "G": 2, "T": 3}
        refIndex = baseToIndex[self.ref]
        pMapStrand = [0, 0, 0, 0]
        nMapStrand = [0, 0, 0, 0]

        depth = 0.0
        # What is the maximum quality of the alternate allele?
        self.maxAltQual = 0

        # We need to identify and flag reads that are in duplex
        # Count the number of times each read number "A counter that is unique to each read, generated by collapse" occurs
        # If it occurs once, the read is a singleton. If it occurs twice, it is a duplex
        # That said, we also need to handle the case whereby clipoverlap was NOT run on the input BAM file. A read pair
        # will have the same number
        # To deal with this, create a dictionary which will store both the read, the parental strand, and index
        readOrigin = {}

        # Since the characteristics of each read is in order (i.e. index 0 corresponds to the first read that overlaps
        # this position for every list, cycle through all stored attributes
        for base, qual, fSize, posParent, map, distToEnd, mismatchNum, mapQual, readID \
                in zip(self.alleles, self.qualities, self.famSizes, self.posParent, self.mapStrand, self.distToEnd, self.mismatchNum, self.mappingQual, self.readNum):

            try:
                baseIndex = baseToIndex[base]
            except KeyError:  # i.e. There is an odd base here. Probably an "N". In this case, ignore it
                continue

            if base != self.ref and qual > self.maxAltQual:
                self.maxAltQual = qual
            # What type of read is this, in terms of parental strand
            if posParent:
                if fSize >= strongMoleculeThreshold:
                    pType = "P"
                else:
                    pType = "p"
                self.posMolec[baseIndex] += 1
            else:
                if fSize >= strongMoleculeThreshold:
                    pType = "N"
                else:
                    pType = "n"
                self.negMolec[baseIndex] += 1

            # Calculate Strand bias info
            if map == "S":  # This base is a consensus from both the strand mapped to the (+) and (-) strand
                pMapStrand[baseIndex] += 1
                nMapStrand[baseIndex] += 1
            elif map== "F":
                pMapStrand[baseIndex] += 1
            else:
                nMapStrand[baseIndex] += 1

            # Check to see if there is another read that is the duplex mate of this read
            key = readID + ":" + str(baseIndex)
            if key in readOrigin:
                readOrigin[key] = readOrigin[key] + pType
            else:
                readOrigin[key] = pType
                self.strandCounts[baseIndex] += 1
                # Total molecule count (for VAF)
                depth += 1

        # Generate a count of each parental molecule at this position
        for name, pStrand in readOrigin.items():
            baseIndex = int(name.split(":")[1])
            if pStrand == "N":
                self.baseCounts["SN"][baseIndex] += 1
            elif pStrand == "P":
                self.baseCounts["SP"][baseIndex] += 1
            elif pStrand == "n":
                self.baseCounts["Sn"][baseIndex] += 1
            elif pStrand == "p":
                self.baseCounts["Sp"][baseIndex] += 1
            elif pStrand == "PN" or pStrand == "NP":
                self.baseCounts["DPN"][baseIndex] += 1
            elif pStrand == "Pn" or pStrand == "nP":
                self.baseCounts["DPn"][baseIndex] += 1
            elif pStrand == "pN" or pStrand == "Np":
                self.baseCounts["DpN"][baseIndex] += 1
            elif pStrand == "pn" or pStrand == "np":
                self.baseCounts["Dpn"][baseIndex] += 1
            else:
                raise TypeError("It seems the developer messed up. You should send him an angry e-mail! (Mention this message please)")

        # Calculate strand bias
        self.strandBias = []
        for index in range(0, 4):
            if pMapStrand[index] + nMapStrand[index] == 0:
                self.strandBias.append(1.0)
            else:
                self.strandBias.append(fisher_exact(
                [[pMapStrand[refIndex], nMapStrand[refIndex]], [pMapStrand[index], nMapStrand[refIndex]]]))

        self.vafs = []
        for index in range(0,4):
            # baseCount = 0.0
            # for molecType in self.baseCounts.values():
            #     baseCount += molecType[index]
            self.vafs.append(self.strandCounts[index]/depth)

        # Does this variant fail basic filters?
        altCount = sum(self.strandCounts[x] for x in range(0,4) if x != refIndex)
        if depth < minDepth:
            return False
        elif altCount < minAltDepth:
            return False

        # Pass filters
        return True


class PileupManager:
    """
    Generates a custom pileup using family characteristics
    """
    def __init__(self, inBAM, refGenome, homopolymerWindow=5, noiseWindow=150, pileupWindow = 1000):
        self._inFile=pysam.AlignmentFile(inBAM)
        self._refGenome = Fasta(refGenome, read_ahead=20000)
        self._candidateIndels = []
        self.pileup = {}
        self._clipOverlap = False
        self.candidateVar = {}
        self._homopolymerWindow = homopolymerWindow
        self._noiseWindow = noiseWindow
        # The number of positions to store before collapsing previous positions
        # Reduce this number to lower memory footprint, but be warned that, if this falls below the length of a read,
        # Some positions may not be tallied correctly
        self._pileupWindow = pileupWindow

    def __writeVcfHeader(self, file):
        """
        Prints a VCF header to the specified file

        :param file: A file object, open to writing
        """

        header = ["##fileformat=VCFv4.3",
                  "##reference=" + self._refGenome.filename]

        # Add the contig information
        for contig, features in self._refGenome.faidx.index.items():
            line = "##contig=<ID=" + contig + ",length=" + str(len(features)) + ">"
            header.append(line)

        # Add the info field info
        header.append('##INFO=<ID=DPN,Number=R,Type=Integer,Description="Duplex Support with Strong Positive and Strong Negative Consensus">')
        header.append('##INFO=<ID=DPn,Number=R,Type=Integer,Description="Duplex Support with Strong Positive and Weak Negative Consensus">')
        header.append('##INFO=<ID=DpN,Number=R,Type=Integer,Description="Duplex Support with Weak Positive and Strong Negative Consensus">')
        header.append('##INFO=<ID=Dpn,Number=R,Type=Integer,Description="Duplex Support with Weak Positive and Weak Negative Consensus">')
        header.append('##INFO=<ID=SP,Number=R,Type=Integer,Description="Singleton Support with Strong Positive Consensus">')
        header.append('##INFO=<ID=Sp,Number=R,Type=Integer,Description="Singleton Support with Weak Positive Consensus">')
        header.append('##INFO=<ID=SN,Number=R,Type=Integer,Description="Singleton Support with Strong Negative Consensus">')
        header.append('##INFO=<ID=MC,Number=R,Type=Integer,Description="Total Molecule counts for Each Allele">')
        header.append('##INFO=<ID=STP,Number=R,Type=Float,Description="Probability of Strand Bias during sequencing for each Allele">')
        header.append('##INFO=<ID=PC,Number=R,Type=Integer,Description="Positive Strand Molecule Counts">')
        header.append('##INFO=<ID=NC,Number=R,Type=Integer,Description="Negative Strand Molecule Counts">')
        header.append('##INFO=<ID=VAF,Number=R,Type=Float,Description="Variant allele fraction of alternate allele(s) at this locus">')

        header.append("\t".join(["#CHROM", "POS", "ID", "REF", "ALT", "QUAL", "FILTER", "INFO\n"]))
        file.write(os.linesep.join(header))

    def writeVariants(self, outfile, minMolecules=3, minAltMolecules=2):

        moleculeTypes = ("DPN", "DPn", "DpN", "Dpn", "SP", "Sp", "SN", "Sn")
        with open(outfile, "w") as o:
            self.__writeVcfHeader(o)

            for chrom in self.candidateVar:
                for position, stats in self.candidateVar[chrom].items():

                    if stats.ref == "N":
                        continue  # Don't process positions where the reference base is an "N". TODO: Implement this elsewhere

                    try:
                        passFilter = stats.summarizeVariant(minMolecules, minAltMolecules)

                        if not passFilter:
                            continue
                    except ZeroDivisionError:  # This will be thrown if the "depth" at this position is 0
                        # This will occur if all the bases which map to a position are "N"s
                        continue

                    # Does this variant meet the basic filter requirements?

                    # Generate the info column
                    infoCol = []
                    for molecule in moleculeTypes:
                        x = molecule + "=" + ",".join(str(x) for x in stats.baseCounts[molecule])
                        infoCol.append(x)

                    infoCol.append("MC=" + ",".join(str(x) for x in stats.strandCounts))  # Parental Strand counts
                    infoCol.append("STP=" + ",".join(str(x) for x in stats.strandBias))  # Strand bias
                    infoCol.append("PC=" + ",".join(str(x) for x in stats.posMolec))
                    infoCol.append("NC=" + ",".join(str(x) for x in stats.negMolec))
                    infoCol.append("VAF=" + ",".join(str(x) for x in stats.vafs))  # VAF


                    # Add 1 to the position, to compensate for the fact that pysam uses 0-based indexing, while VCF files use 1-based
                    outLine = "\t".join([chrom, str(position + 1), ".", ",".join(stats.altAlleles), stats.ref, str(stats.maxAltQual), ".", ";".join(infoCol)])
                    o.write(outLine + os.linesep)


    def cigarToTuple(self, cigarTuples):
        """
        Converts a pysam-style cigar tuples into a regular tuple, where 1 operator = 1 base

        Ignores soft-clipping, and flags a
        :param cigarTuples: A list of tuples
        :return: A tuple listing expanded cigar operators, as well as a boolean indicating if there is an INDEL in this read
        """

        cigarList = []
        hasIndel = False
        for cigarElement in cigarTuples:
            cigOp = cigarElement[0]
            # Ignore soft-clipped bases
            if cigOp == 4:
                continue
            # If there is an insertion or deletion in this read, indicate that
            if cigOp == 1 or cigOp == 2:
                hasIndel = True
            cigarList.extend([cigOp] * cigarElement[1])

        return tuple(cigarList), hasIndel

    def generatePileup(self, windowBuffer = 200):

        def processWindow(pos, coordinate):

            # Ignore non-variant positions
            if pos.alt:

                # If there is a variant, we need to obtain some general characteristics to be used for filtering
                # First, store the sequence of the surrounding bases. This will be used to identify errors
                # due to homopolymers
                homoWindow = []
                windowPos = coordinate - refStart # Where, relative to the reference window, are we located?
                for j in range(windowPos - self._homopolymerWindow, windowPos + self._homopolymerWindow):
                    if windowPos == j:  # i.e. We are at the position we are currently examining, flag it so we have a reference point
                        homoWindow.append("M")  # It's me!
                    else:
                        homoWindow.append(refWindow[j])

                # Next, examine how "noisy" the neighbouring region is (i.e. how many candidiate variants there are)
                # Flag all nearby candidate variants. To avoid flagging the same variant twice, add this
                # candidate variant position to all variants behind it, and vise-versa
                if chrom not in self.candidateVar:
                    self.candidateVar[chrom] = sortedcontainers.SortedDict()

                nearbyVar = []
                for j in self.candidateVar[chrom].irange(coordinate - self._noiseWindow):
                    self.candidateVar[chrom][j].nearbyVar.append(pos)
                    nearbyVar.append(self.candidateVar[chrom][j])

                # Finally, save all these stats we have just generated inside the variant, to be examined during
                # filtering
                pos.processVariant(homoWindow, nearbyVar, self._noiseWindow)
                self.candidateVar[chrom][coordinate] = pos


        # Print status messages
        printPrefix = "PRODUSE-CALL\t"
        sys.stderr.write("\t".join([printPrefix, time.strftime('%X'), "Starting...\n"]))
        sys.stderr.write("\t".join([printPrefix, time.strftime('%X'), "Finding Candidate Variants\n"]))
        readsProcessed = 0
        lastPos = -1
        chrom = None

        refWindow = ""
        refStart = 0
        refEnd = 0
        refName = None

        for read in self._inFile:

            # Prior tp adding each base in this read onto the pileup, we need to analyze the current read,
            # and obtain general characteristics (family size, mapping quality etc)

            # Print out status messages
            readsProcessed += 1
            if readsProcessed % 100000 == 0:
                sys.stderr.write("\t".join([printPrefix, time.strftime('%X'), "Reads Processed: %s\n" % readsProcessed]))

            # Ignore unmapped reads
            if read.is_unmapped:
                continue

            # Ignore reads without a cigar string, as they are malformed or empty
            if not read.cigartuples:
                continue

            # Have we advanced positions? If so, we may need to change the loaded reference window, and process
            # positions which no more reads will be mapped to
            if read.reference_name != refName or read.reference_start != lastPos:

                # Sanity check that the input BAM is sorted
                if read.reference_name == refName and read.reference_start < lastPos:
                    sys.stderr.write("ERROR: The input BAM file does not appear to be sorted\n")
                    exit(1)

                # Process positions at which no more reads are expected to map to (assuming the input is actually sorted)
                # We do this to drastically reduce the memory footprint of the pileup, since we don't care about non-variant
                # positions very much
                try:
                    if read.reference_name != refName and chrom is not None:

                        # If we have switched chromosomes, process all variants stored on the previous chromosome
                        posToProcess = self.pileup[chrom].keys()
                        for coordinate in posToProcess:
                            processWindow(self.pileup[chrom][coordinate], coordinate)
                        del self.pileup[chrom]

                    # Otherwise, check to see if previous positions fall outside the buffer window. If so, process them
                    elif chrom is not None:

                        posToProcess = tuple(self.pileup[chrom].irange(minimum=None, maximum=read.reference_start - self._pileupWindow))
                        for coordinate in posToProcess:
                            processWindow(self.pileup[chrom][coordinate], coordinate)
                        for coordinate in posToProcess:
                            del self.pileup[chrom][coordinate]
                except KeyError:  # i.e. All reads which mapped to this contig or previous positions failed QC. There are no positions to process
                    pass


                # Load the current reference window and it's position
                # If we have switched contigs, or moved outside the window that is currently buffered,
                # we need to re-buffer the reference
                readWindowStart = read.reference_start - windowBuffer
                if readWindowStart < 0:
                    readWindowStart = 0
                readWindowEnd = read.reference_end + windowBuffer  #TODO: Don't estimate soft-clipping, but instead calculate it

                if read.reference_name != refName or readWindowStart < refStart or readWindowEnd > refEnd:
                    # To reduce the number of times this needs to be performed, obtain a pretty large buffer
                    refStart = readWindowStart - self._pileupWindow - self._homopolymerWindow
                    if refStart < 0:
                        refStart = 0
                    refEnd = readWindowStart + 5000
                    refName = read.reference_name
                    refWindow = self._refGenome[refName][refStart:refEnd].seq

                lastPos = read.reference_start

            # Is this read valid? Check the naming scheme of the read, and identify each feature stored in the name
            try:
                nameElements = read.query_name.split(":")
                # Barcode is element 1. This is no longer needed, so ignore it
                # Parental strand is element 2.
                assert nameElements[1] == "+" or nameElements[1] == "-"
                rPosParent = nameElements[1] == "+"
                # Family size is element 3
                rFSize = int(nameElements[2])
                # Counter is 4. This is used to identify duplexes
                counter = nameElements[3]

            except (TypeError, IndexError, AssertionError):
                sys.stderr.write("ERROR: The names of the reads in this BAM file are not consistent with those generated by ProDuSe Collapse\n")
                sys.stderr.write("We expected something line \'TAATGCATCTTGATTTGGTTGCGAGTTGCAAT:+:207:0\', and instead saw %s\n" % (read.query_name))
                exit(1)

            # Obtain generic read characteristics
            # If clipoverlap was run on this BAM file, the originating strand of each base will be stored in a tag
            if self._clipOverlap:
                try:  # Just in case this read does not contain that tag
                    rMapStrand = read.get_tag("os")
                    self._clipOverlap = True
                except KeyError:  # i.e. The required tag is not present. Either these reads do not overlap at all, or clipoverlap was never run on the input BAM file
                    if read.is_reverse:
                        rMapStrand = ["R"] * len(read.positions)
                    else:
                        rMapStrand = ["F"] * len(read.positions)

            else: # As clipoverlap was not run on the input BAM file, use the mapping strand of the read to indicate which strand each base maps to
                if read.is_reverse:
                    rMapStrand = ["R"] * len(read.positions)
                else:
                    rMapStrand = ["F"] * len(read.positions)

            rMappingQual = read.mapping_quality

            # COnvert the cigar to a more user-friendly format
            rCigar, rHasIndel = self.cigarToTuple(read.cigartuples)

            # Does this read support an INDEL?
            if rHasIndel:
                continue  # TODO: Handle this case

            # If clipoverlap was performed on each read, we need to pull out the tag which indicates what base originated
            # from which read (in the case of clipoverlap)

            # Next, map all bases on this read to the reference
            # Ignoring soft-clipped bases
            chrom = read.reference_name

            # If this is the first read we are processing from this chromosome, we need to create the dictionary which
            # will store all bases on this chromosome
            if chrom not in self.pileup:
                self.pileup[chrom] = sortedcontainers.SortedDict()

            # All positions covered by this read
            positions = []

            # The number of variants supported by this read
            numMismatch = 0

            # Iterate through all bases
            for position, base, cigar, qual, mapStrand in zip(read.positions, read.query_alignment_sequence, rCigar, read.query_alignment_qualities, rMapStrand):

                # If this position has not been covered before, we need to generate a new pileup at this position
                if position not in self.pileup[chrom]:
                    refBase = refWindow[position - refStart]
                    self.pileup[chrom][position] = Position(refBase)

                distFromEnd = min(position - read.reference_start, read.reference_end - position)
                isAlt = self.pileup[chrom][position].add(base, qual, rFSize, rPosParent, mapStrand, distFromEnd, rMappingQual, counter)

                # Check to see if this position now has evidence of a variant
                if isAlt:
                    numMismatch += 1
                positions.append(self.pileup[chrom][position])

            # Store the number of total mismatches for this read at each variant
            for pos in positions:
                pos.addMismatchNum(numMismatch)

        # Now that we have finished processing all reads in the input file, process all remaining positions
        posToProcess = self.pileup[chrom].keys()
        for coordinate in posToProcess:
            processWindow(self.pileup[chrom][coordinate], coordinate)

        sys.stderr.write("\t".join(["PRODUSE-CALL\t", time.strftime('%X'), "Reads Processed: " + str(readsProcessed) + "\n"]))
        sys.stderr.write(
            "\t".join(["PRODUSE-CALL\t", time.strftime('%X'), "Variant Calling Complete\n"]))


def isValidFile(file, parser):
    """
    Checks to ensure a specified file exists, and throws an error if it does not
    :param file: A string containing a filepath
    :param parser: An argparse.argumentparser() object
    :return: The variable "file", if the file exists
    :raises: parser.error() if the file does not exist
    """
    if os.path.exists(file):
        return file
    else:
        raise parser.error("Unable to locate %s. Please ensure the file exists, and try again" % file)


def validateArgs(args):
    """
    Checks that the specified set of arguments are valid
    :param args: A dictionary listing {argument: parameter}
    :return: A dictionary listing {argument: parameter} that have been validated
    """

    # Convert the dictionary into a list, to allow the arguments to be re-parsed
    listArgs = []
    for argument, parameter in args.items():

        if parameter is None or parameter is False or parameter == "None" or parameter == "False":
            continue
        # Something was provided as an argument
        listArgs.append("--" + argument)

        # If the parameter is a boolean, ignore it, as this will be reset once the arguments are re-parsed
        if parameter == "True":
            continue
        # If the parameter is a list, we need to add each element seperately
        if isinstance(parameter, list):
            for p in parameter:
                listArgs.append(str(p))
        else:
            listArgs.append(str(parameter))

    # Reparse the sanitized arguments
    # List requirements here
    parser = argparse.ArgumentParser(description="Identifies and calls variants")
    parser.add_argument("-c", "--config", metavar="INI", type=lambda x: isValidFile(x, parser),
                        help="An optional configuration file which can provide one or more arguments")
    parser.add_argument("-i", "--input", metavar="BAM", required=True, type=lambda x: isValidFile(x, parser),
                        help="Input post-collapse or post-clipoverlap BAM file")
    parser.add_argument("-o", "--output", metavar="VCF", required=True, help="Output VCF file")
    parser.add_argument("-r", "--reference", metavar="FASTA", required=True, type=lambda x: isValidFile(x, parser),
                        help="Reference Genome, in FASTA format")
    parser.add_argument("--min_depth", metavar="INT", type=int, default=3,
                        help="Minimum overall depth required to call a variant")
    parser.add_argument("--min_alt_molecules", metavar="INT", type=int, default=2,
                        help="Minimum number of molecules supporting an alternate allele required to call a variant")
    validatedArgs = parser.parse_args(listArgs)
    return vars(validatedArgs)


parser = argparse.ArgumentParser(description="Identifies and calls variants")
parser.add_argument("-c", "--config", metavar="INI", type=lambda x: isValidFile(x, parser), help="An optional configuration file which can provide one or more arguments")
parser.add_argument("-i", "--input", metavar="BAM", type=lambda x: isValidFile(x, parser), help="Input post-collapse or post-clipoverlap BAM file")
parser.add_argument("-o", "--output", metavar="VCF", help="Output VCF file")
parser.add_argument("-r", "--reference", metavar="FASTA", type=lambda x: isValidFile(x, parser), help="Reference Genome, in FASTA format")
parser.add_argument("--min_depth", metavar="INT", type=int, help="Minimum overall depth required to call a variant")
parser.add_argument("--min_alt_molecules", metavar="INT", type=int, help="Minimum number of molecules supporting an alternate allele required to call a variant")


def main(args=None, sysStdin=None):
    if args is None:
        if sysStdin is None:
            args = parser.parse_args()
        else:
            args = parser.parse_args(sysStdin)
        args = vars(args)

    # If a config file was specified, parse the arguments from
    if args["config"] is not None:
        config = ConfigObj(args["config"])
        try:
            for argument, parameter in config["call"].items():
                if argument in args and not args[argument]:  # Aka this argument is used by call, and a parameter was not provided at the command line
                    args[argument] = parameter
        except KeyError:  # i.e. there is no section named "call" in the config file
            sys.stderr.write(
                "ERROR: Unable to locate a section named \'call\' in the config file \'%s\'\n" % (args["config"]))
            exit(1)

    args = validateArgs(args)
    pileup = PileupManager(args["input"], args["reference"])

    # Find candidate variants
    pileup.generatePileup()
    pileup.writeVariants(args["output"], args["min_depth"], args["min_alt_molecules"])


if __name__ == "__main__":
    main()