import ROOT
import json
import itertools
import logging

import python.tools.plot as plot

logger = logging.getLogger(__name__)
_correction_set_ids = itertools.count()


def _enable_implicit_mt(jobs):
    if jobs <= 1:
        return
    if not ROOT.IsImplicitMTEnabled():
        ROOT.EnableImplicitMT(jobs)
    elif ROOT.GetThreadPoolSize() != jobs:
        logger.warning(
            "ROOT implicit MT is already configured with %d threads; "
            "requested %d.", ROOT.GetThreadPoolSize(), jobs,
        )


def validate_json(
    snap_dir, corr_dir, hist_dir, datamc, year, bin_dict, mets, jobs=1
):
    """
    Create histograms for closure validation.

    Args:
        snap_dir (str): path to snapshots.
        corr_dir (str): path to corrections.
        hist_dir (str): path where histograms are saved.
        datamc (list): DATA or MC to investigate.
        year (str): name of the year.
        bin_dict (dict): bining configuration.
        mets (list): met types to validate.
    """
    logger.info("Starting validation of correction.")
    _enable_implicit_mt(jobs)

    # define variations for later
    variations = ['', '_stat_xup', '_stat_xdn', '_stat_yup', '_stat_ydn']

    variables = ['pt', 'phi']

    # Load this once per validation invocation.  A unique C++ symbol avoids
    # interpreter redeclaration errors when validation is called repeatedly in
    # one Python process.
    schemav2_json = corr_dir.replace(f'{year}/', f'schemaV2_{year}.json')
    correction_set_symbol = f'cs_xy_{next(_correction_set_ids)}'
    ROOT.gROOT.ProcessLine(
        f'auto {correction_set_symbol} = '
        'correction::CorrectionSet::from_file('
        f'{json.dumps(schemav2_json)})->at("met_xy_corrections");'
    )

    for dtmc in datamc:

        # in MC also define pileup variations
        if dtmc=='MC':
            pu_variations = ['_pu_up', '_pu_dn']
        else:
            pu_variations = []
        
        # setup of dataframe
        rdf = ROOT.RDataFrame("Events", f"{snap_dir}{dtmc}/file_*.root")

        # loop over different met types, calculate correction and histograms
        for met in mets:

            # obtain met pt and phi from x, y components
            rdf = rdf.Define(f'{met}_phi', f'atan2({met}_y, {met}_x)')
            rdf = rdf.Define(f'{met}_pt', f'sqrt({met}_y*{met}_y + {met}_x*{met}_x)')
        
            # correct pt and phi for different variations
            for var in variables:
                
                # statistical variations for both data and mc
                for vrt in variations+pu_variations:

                    rdf = rdf.Define(
                        f'{met}_{var}_corr{vrt}', 
                        f'{correction_set_symbol}->evaluate({{\
                            "{var}{vrt}", "{met}", "{dtmc}", \
                            {met}_pt, {met}_phi, static_cast<float>(PV_npvsGood)\
                        }})'
                    )

            for vrt in variations+pu_variations:
                rdf = rdf.Define(
                    f'{met}_x_corr{vrt}',
                    f'{met}_pt_corr{vrt} * cos({met}_phi_corr{vrt})',
                )
                rdf = rdf.Define(
                    f'{met}_y_corr{vrt}',
                    f'{met}_pt_corr{vrt} * sin({met}_phi_corr{vrt})',
                )

        # create histograms for defined variables
        hist_results = []
        profile_results = []
        save_variations = ['_corr'+v for v in variations+pu_variations] + ['']
        pileup_bins = bin_dict['pileup']
        
        for vrt in save_variations:
            for met in mets:
                for var in variables:

                    logger.debug(f'Making histogram: {met}_{var}{vrt}')

                    bins = bin_dict[var]
                    hist_results.append(
                        rdf.Histo1D(
                            (f'{met}_{var}{vrt}', '', bins[2], bins[0], bins[1]),
                            f'{met}_{var}{vrt}',
                            "puWeight"
                        )
                    )

            if vrt:
                for met in mets:
                    for component in ['x', 'y']:
                        profile_name = f'{met}_{component}_vs_npv{vrt}'
                        profile_results.append(
                            rdf.Profile1D(
                                (
                                    profile_name,
                                    '',
                                    pileup_bins[2],
                                    pileup_bins[0],
                                    pileup_bins[1],
                                ),
                                'PV_npvsGood',
                                f'{met}_{component}{vrt}',
                                'puWeight',
                            )
                        )

        # Keep all actions lazy until they have been booked.  The first
        # GetValue() then evaluates every histogram and profile in one event
        # loop; cloning afterwards preserves the previous ownership semantics.
        hists = [result.GetValue().Clone() for result in hist_results]
        profiles = [result.GetValue().Clone() for result in profile_results]

        # save histograms
        rfile = f'{hist_dir}validation_{dtmc}.root'

        with ROOT.TFile(rfile, 'recreate') as f:
            for h in hists + profiles:
                h.Write()

        for profile in profiles:
            function = ROOT.TF1(
                f"closure_{profile.GetName()}", "[0]*x+[1]", 10, 70
            )
            fit_result = profile.Fit(function, "Q0RS", "", 10, 70)
            status = int(fit_result)
            if status != 0:
                logger.warning(
                    "Closure fit failed for %s with status %d.",
                    profile.GetName(), status,
                )
                continue
            logger.info(
                "Closure %s: slope=%+.5g +/- %.3g, intercept=%+.5g "
                "+/- %.3g, chi2/ndf=%.2f/%d",
                profile.GetName(), function.GetParameter(0),
                function.GetParError(0), function.GetParameter(1),
                function.GetParError(1), function.GetChisquare(),
                function.GetNDF(),
            )

        logger.info(f"{dtmc} histograms successfully saved at {rfile}.")

    return


def make_validation_plots(
    hist_dir, plot_dir, corr_dir, hbins, axislabels, lumilabel, dsetlabel,
    datamc, year, mets
):
    """
    Create MC vs Mc or Data vs Data plot before vs after xy correction.

    Args:
    snap_dir (str): Path to snapshot directory.
    plot_dir (str): Path to plot directory.
    corr_dir (str): Path to correction directory.
    hbins (dict): Dictionary with histogram binning information.
    axislabels (dict): Improved axis labels.
    lumilabel (dict): Labels for lumi in the corresponding epoch.
    dsetlabel (str): Label for dataset.
    """
    logger.info("Starting validation")

    variations = [
        ['', '_stat_xup', '_stat_xdn'],
        ['', '_stat_yup', '_stat_ydn']
    ]

    for dtmc in datamc:

        # in MC also define pileup variations
        if dtmc=='MC':
            pu_variations = [['', '_pu_up', '_pu_dn']]
        else:
            pu_variations = []

        # load histograms
        rfile = f'{hist_dir}validation_{dtmc}.root'
        tf = ROOT.TFile(rfile, 'read')

        for met in mets:

            for var in ['pt', 'phi']:
            
                h = tf.Get(f"{met}_{var}")

                for vrt in variations+pu_variations:

                    hists = []
                    labels = ['uncorrected']
                    for v in vrt:
                        hists.append(tf.Get(f"{met}_{var}_corr{v}"))
                        labels.append(f"corrected {v.replace('_', '')}")

                    print(labels)

                    basedir = f"{plot_dir}{met}/"
                    vrtname = vrt[1].replace('up', '').replace('_', '')

                    outfile = f"{basedir}{dtmc}_{var}_{vrtname}.pdf"

                    plot.plot_ratio(
                        h,
                        hists,
                        labels=labels,
                        dsetlabel=f'{dsetlabel} - {dtmc}',
                        axis=[axislabels[met+'_'+var], "# Events"],
                        outfile=outfile, 
                        text=['','',''], 
                        xrange=[hbins[var][0], hbins[var][1]],
                        ratiorange = [0.8, 1.2],
                        lumi = lumilabel[dtmc]
                    )

            profile_variations = [
                '_corr'+v for v in variations[0] + variations[1]
            ]
            if dtmc == 'MC':
                profile_variations += ['_corr_pu_up', '_corr_pu_dn']
            for component in ['x', 'y']:
                for vrt in dict.fromkeys(profile_variations):
                    profile = tf.Get(f'{met}_{component}_vs_npv{vrt}')
                    if not profile:
                        raise RuntimeError(
                            f"Missing closure profile {met}_{component}_vs_npv{vrt} "
                            f"in {rfile}."
                        )
                    plot.plot_profile_closure(
                        profile,
                        outfile=(
                            f"{plot_dir}{met}/{dtmc}_{component}_vs_npv{vrt}"
                        ),
                        axis=[axislabels['pileup'], f'{met}_{component} (GeV)'],
                        lumi=lumilabel[dtmc],
                        dsetlabel=f'{dsetlabel} - {dtmc}',
                    )

        tf.Close()

    return
