import configargparse
import nucleotide
import position
import pysam
import bed
import sys

desc = "Call SNVs on collapsed BAMs containing adapter sequence information"
parser = configargparse.ArgParser(description=desc)
parser.add(
    "-c", "--config",
    required=False,
    is_config_file=True,
    help="An optional configuration file for any of the input arguments."
    )
parser.add(
    "-i", "--input",
    required=True,
    type=str,
    help="An input bam file for reading generated from collapse.py and bwa.py"
    )
parser.add(
    "-o", "--output",
    required=True,
    type=str,
    help="A pair of empty fastq files for writing"
    )
parser.add(
    "-as", "--adapter_sequence",
    type=str,
    required=True,
    help="The randomized adapter sequence flanked in input fastq files described using IUPAC bases"
    )
parser.add(
    "-ap", "--adapter_position",
    type=str,
    required=True,
    help="The positions in the adapter sequence to include in distance calculations, 0 for no, 1 for yes"
    )
parser.add(
    "-mm", "--max_mismatch",
    type=int,
    required=True,
    help="The maximum number of mismatches allowed between the expected and actual adapter sequences",
    )
parser.add(
    "-r", "--reference",
    required=True,
    type=str,
    help="A genome reference file"
    )
parser.add_argument(
    "-tb", "--target_bed",
    required=False,
    help="Restrict SNV discovery to positions/regions in input bed file"
    )
parser.add_argument(
    "-abct", "--alt_base_count_threshold",
    default=5,
    required=True,
    type=int,
    help="The minimum number of alternative bases to identify separately in the positive and negative read collections"
    )
parser.add_argument(
    "-sbt", "--strand_bias_threshold",
    default=0.2,
    required=True,
    type=float,
    help=""
    )
parser.add_argument(
    "-vaft", "--variant_allele_fraction_threshold", 
    default=0.01,
    required=True,
    type=float,
    help=""
    )
parser.add_argument(
    "-mrpu", "--min_reads_per_uid",
    default=2,
    required=True,
    type=int,
    help=""
    )


def main(args=None):

    if args == None:
        args = parser.parse_args()

    bamfile = pysam.AlignmentFile(args.input, 'rb');
    fastafile = pysam.FastaFile(args.reference);
    targetbed = None
    if not args.target_bed == None:
        targetbed = bed.BedOpen(args.target_bed, 'r');
    else:
        sys.exit("You need to specify a targetbed")

    posCollection = position.PosCollectionCreate(bamfile, fastafile, filter_overlapping_reads = True, target_bed = targetbed, min_reads_per_uid = args.min_reads_per_uid);

    output = None;
    if not args.output == "-":
        output = open(args.output, 'w');

    # if args.mode == 'validation':
    #     for pos in posCollection:
    #         if pos.coords2() in targetbed:
    #             is_variant = pos.is_variant( \
    #                 adapter_sequence = args.adapter_sequence, \
    #                 max_mismatch = args.max_mismatch, \
    #                 alt_base_count_threshold = args.alt_base_count_threshold, \
    #                 strand_bias_threshold = args.strand_bias_threshold, \
    #                 variant_allele_fraction_threshold = args.variant_allele_fraction_threshold );

    #             if args.output == "-":
    #                 print(str(pos));
    #             else:
    #                 output.write(str(pos));
    #                 output.write('\n');

    # elif args.mode == 'discovery':

    ref_adapter = ''.join([args.adapter_sequence, args.adapter_sequence])
    ref_indexes = list(''.join([args.adapter_position, args.adapter_position]))
    ref_indexes = [ i for i in range(len(ref_indexes)) if ref_indexes[i] == "1" ]

    counts = {}

    for pos in posCollection:

        if pos.coords2() in targetbed:

            pos.calc_base_stats( \
                min_reads_per_uid = args.min_reads_per_uid
                )

            print str(pos)

        # if pos.coords2() in targetbed:

        #     if args.output == "-":
        #         print(str(pos));

        #     else:
        #         output.write(str(pos));
        #         output.write('\n');


    # else:

    #     for pos in posCollection:

    #         is_variant = pos.is_variant( \
    #             adapter_sequence = args.adapter_sequence, \
    #             max_mismatch = args.max_mismatch, \
    #             alt_base_count_threshold = args.alt_base_count_threshold, \
    #             strand_bias_threshold = args.strand_bias_threshold, \
    #             variant_allele_fraction_threshold = args.variant_allele_fraction_threshold );

    #         if is_variant or pos.coords() in bedfile:

    #             if args.output == "-":
    #                 print(str(pos));
    #             else:
    #                 output.write(str(pos));
    #                 output.write('\n');
    
    if not args.output == "-":
        output.close();

if __name__ == '__main__':
    main()
