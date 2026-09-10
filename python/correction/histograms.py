import ROOT
import os
import logging
from glob import glob

logger = logging.getLogger(__name__)


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


def check_snapshots(snap_dir, datamc):
    '''
    Check whether produced snapshots are usable.

    Args:
    snap_dir (str): Directory of snapshots.
    datamc (list): List of dataset types (e.g., 'DATA', 'MC').
    '''
    logger.info(f"Checking snapshots in {snap_dir} for {datamc}")

    zombies = []
    notrees = []
    noevents = []

    all_files = 0

    for dtmc in datamc:
        files = f'{snap_dir}{dtmc}/*.root'

        files = glob(files)
        all_files += len(files)

        for f in files:
            try:
                f_tmp = ROOT.TFile.Open(f)

                if f_tmp.IsZombie():
                    logger.debug(f"File {f} is a Zombie.")
                    zombies.append(f)

                else:
                    tree = f_tmp.Get("Events")
                    if not tree:
                        logger.debug(
                            f"File {f} does not contain tree 'Events'."
                        )
                        notrees.append(f)
                    
                    else:
                        if tree.GetEntries() == 0:
                            logger.debug(
                            f"File {f} does not contain any events."
                        )
                            noevents.append(f)

            except OSError:
                logger.debug(f"File {f} can not be opened.")
                zombies.append(f)

    logger.debug(
        f"The following files are zombies: {zombies}\n"
        f"The following files have no tree 'Events': {notrees}\n"
        f"The following files have zero entries: {noevents}\n"
    )

    failed_files = zombies + notrees + noevents
    ok_files = all_files - len(failed_files)

    logger.info(
        f"{len(zombies)} files are zombies. "
        f"{len(notrees)} files have no tree 'Events'. "
        f"{len(noevents)} files have zero entries. "
        f"{ok_files} files are fine."
    )

    if len(failed_files)>0:

        do_delete = (input(
            "Would you like to delete the corrupted files? (y/n)")=='y'
        )

        if do_delete:
            logger.info("Deleting selected files.")
            for f in failed_files:
                os.remove(f)

        else:
            logger.info(
                "Not deleting corrupted files. "
                "There may be problems in the subsequent steps."
            )

    return


def make_hists(
    snap_dir, hist_dir, hbins, jobs, mets, pileups, datamc
):
    """
    function to make 2d histograms for xy correction

    snap_dir (str): Directory of snapshots.
    hist_dir (str): Output directory for histograms.
    hbins (dict): Dictionary with histogram binnings.
    jobs (int): Number of threads for parallel processing.
    mets (list): List of mets to process.
    pileups (list): List of pileup quantities to process.
    datamc (list): List of datasets to process (data / mc).
    """

    _enable_implicit_mt(jobs)

    for dtmc in datamc:
        n = max(jobs, 1)
        logger.info(
            f"Starting histogram production for {dtmc} with {n} threads."
        )

        hists = {}

        rdf = ROOT.RDataFrame("Events", f"{snap_dir}/{dtmc}/file_*.root")

        for met in mets:
            met_vars = [met+'_x', met+'_y']

            for pu in pileups:

                for variation in ["", "Up", "Dn"]:      
                    # definition of 2d histograms met_xy vs npv
                    for var in met_vars:
                        h = rdf.Histo2D(
                            (
                                f'{pu}_{var}_puweight{variation}', 
                                '', 
                                hbins['pileup'][2], 
                                hbins['pileup'][0], 
                                hbins['pileup'][1], 
                                hbins['met'][2], 
                                hbins['met'][0], 
                                hbins['met'][1]
                            ),
                            pu, var,
                            "puWeight"+variation
                        )
                        hists[f'{pu}_{var}_puweight{variation}'] = h

                        profile_name = (
                            f'{pu}_{var}_puweight{variation}_profile'
                        )
                        profile = rdf.Profile1D(
                            (
                                profile_name,
                                '',
                                hbins['pileup'][2],
                                hbins['pileup'][0],
                                hbins['pileup'][1],
                            ),
                            pu,
                            var,
                            "puWeight"+variation,
                        )
                        hists[profile_name] = profile

        rfile = hist_dir+dtmc+'.root'
        hfile = ROOT.TFile(rfile, "recreate")
        for var in hists.keys():
            hists[var].Write()
        hfile.Close()

        logger.info(
            f"Histogram production finished for {dtmc}. Saved in {rfile}"
        )

    return
