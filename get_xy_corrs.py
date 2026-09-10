# general packages
import ROOT
import json
import logging

# correction steps
from python.correction.snapshot_maker import make_snapshot
from python.correction.histograms import check_snapshots, make_hists
from python.correction.correction_extractor import get_corrections
from python.correction.convert2json import make_correction_with_formula
from python.correction.validate import validate_json, make_validation_plots

# python inputs
from inputs.config.paths import get_paths
from inputs.config.binning import get_bins
from inputs.config.labels import get_labels

# tools
from python.tools.parsers import parse_arguments
from python.tools.logger_setup import setup_logger
from python.tools.das_query import get_files_from_das

ROOT.gROOT.SetBatch(1)


def main():

    # get inputs
    args = parse_arguments()
    path_dict = get_paths(args)
    hbins = get_bins()
    mets = args.met.split(',')
    pileups = args.pileup.split(',')
    datamc = args.processes.split(',')
    lumilabels, axislabels, dsetlabel = get_labels(args.year)

    # setup logger
    setup_logger('main.log', args.debug)
    logger = logging.getLogger(__name__)

    logger.info(
        "Main script started for "
        f"{args.year}, {args.met}, and {args.processes}."
    )

    # Preparation: getting files from DAS
    if args.prep:
        get_files_from_das(
            path_dict['datasets'],
            path_dict['nanoAODs'],
            path_dict['redirector'],
            args.year,
            datamc,
        )

    # step 1: make flat ntuples with necessary information
    if args.snapshot:
        make_snapshot(
            path_dict['nanoAODs'],
            path_dict['golden_json'], 
            path_dict['pu_json'],
            mets, 
            pileups,
            path_dict['snap_dir'],
            args.jobs,
            args.condor, path_dict['condor_dir'],
            datamc,
            args.year,
            path_dict['proxy_path']
        )

    # step 2: make 2d histograms met xy vs pileup
    if args.hists:
        # first check whether files are fine
        if not args.skip_check:
            check_snapshots(path_dict['snap_dir'], datamc)

        # then produce histograms
        make_hists(
            path_dict['snap_dir'],
            path_dict['hist_dir'],
            hbins,
            args.jobs,
            mets,
            pileups,
            datamc
        )

    # step 3: fit linear functions to 2d histograms
    if args.corr:
        get_corrections(
            path_dict['hist_dir'],
            hbins,
            path_dict['corr_dir'],
            path_dict['plot_dir'],
            mets,
            pileups,
            lumilabels,
            axislabels,
            datamc
        )

    # make correction lib schema v2
    if args.convert:
        make_correction_with_formula(
            path_dict['corr_dir'],
            args.year,
            datamc,
            mets
        )

    # closure
    if args.validate:
        validate_json(
            path_dict['snap_dir'],
            path_dict['corr_dir'],
            path_dict['hist_dir'],
            datamc,
            args.year,
            hbins,
            mets,
            args.jobs,
        )
        make_validation_plots(
            path_dict['hist_dir'],
            path_dict['plot_dir'],
            path_dict['corr_dir'],
            hbins,
            axislabels,
            lumilabels,
            dsetlabel,
            datamc,
            args.year,
            mets
        )

if __name__=='__main__':
    main()
