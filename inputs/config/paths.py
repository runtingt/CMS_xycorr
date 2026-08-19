import os
import sys

def get_paths(args):

    add_path = f'{args.version}/{args.year}'

    home_path = os.path.expanduser("~")
    eos_path = home_path.replace('afs/cern.ch', 'eos')
    uid = os.getuid()

    pu_jsons = {
        "2022_Summer22": "/cvmfs/cms-griddata.cern.ch/cat/metadata/LUM/Run3-22CDSep23-Summer22-NanoAODv12/latest/puWeights.json.gz",
        "2022_Summer22EE": "/cvmfs/cms-griddata.cern.ch/cat/metadata/LUM/Run3-22EFGSep23-Summer22EE-NanoAODv12/latest/puWeights.json.gz",
        "2023_Summer23": "/cvmfs/cms-griddata.cern.ch/cat/metadata/LUM/Run3-23CSep23-Summer23-NanoAODv12/latest/puWeights.json.gz",
        "2023_Summer23BPix": "/cvmfs/cms-griddata.cern.ch/cat/metadata/LUM/Run3-23DSep23-Summer23BPix-NanoAODv12/latest/puWeights.json.gz",
        "2024_Summer24": "/cvmfs/cms-griddata.cern.ch/cat/metadata/LUM/Run3-24CDEReprocessingFGHIPrompt-Summer24-NanoAODv15/latest/puWeights_BCDEFGHI.json.gz"
    }

    paths = {
        'datasets':f'inputs/config/datasets.json',
        'redirector': 'root://cms-xrd-global.cern.ch//',
        'nanoAODs': f'inputs/nanoAODs/{args.year}.json',
        'plot_dir': f"results/plots/{add_path}/",
        'corr_dir': f"results/corrections/{add_path}/",
        'hist_dir': f"results/hists/{add_path}/",
        'condor_dir': f"results/condor/{add_path}/",
        'pu_json': pu_jsons[args.year],
        'snap_dir': f"{eos_path}/CMS_xycorr/snapshots/{add_path}/",
        'proxy_path': f'{home_path}/proxy/x509up_u{uid}'
    }

    if not os.path.exists(paths["proxy_path"]):
        continue_input = input(
            f"The proxy was not found in {paths['proxy_path']}. "
            "Problems may occur when running the ntuple production steps. "
            "Continue anyway? (y/n)"
        )
        if continue_input != 'y':
            print("Break!")
            sys.exit(1)


    golden_jsons = {
        "2022_Summer22": "/eos/user/c/cmsdqm/www/CAF/certification/Collisions22/Cert_Collisions2022_355100_362760_Golden.json",
        "2022_Summer22EE": "/eos/user/c/cmsdqm/www/CAF/certification/Collisions22/Cert_Collisions2022_355100_362760_Golden.json",
        "2023_Summer23": "/eos/user/c/cmsdqm/www/CAF/certification/Collisions23/Cert_Collisions2023_366442_370790_Golden.json",
        "2023_Summer23BPix": "/eos/user/c/cmsdqm/www/CAF/certification/Collisions23/Cert_Collisions2023_366442_370790_Golden.json",
        "2024_Summer24": "/eos/user/c/cmsdqm/www/CAF/certification/Collisions24/Cert_Collisions2024_378981_386951_Golden.json"
    }

    try:
        assert args.year in golden_jsons.keys(), f"year must be in {list(golden_jsons.keys())}!"
    except AssertionError as e:
        print(e, "If you are adding a new era, please make sure to adapt the configs.")
        sys.exit(1)

    for key in paths.keys():
        if '_dir' in key:
            os.makedirs(paths[key], exist_ok=True)

    paths['golden_json'] = golden_jsons[args.year]

    os.makedirs(paths['nanoAODs'].replace(paths['nanoAODs'].split('/')[-1], ''), exist_ok=True)

    return paths
