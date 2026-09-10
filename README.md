# Repo for XY corrections
The xy corrections are ad-hoc corrections aiming at the reduction of a phi modulation in the missing transverse momentum at the CMS experiment.
Such modulations indicate the presence of a bias in the measurement of the missing transverse momentum in one physical direction of the experiment.
Possible sources of such biases are:
- anisotropic detector response
- inactive calorimeter cells/tracking regions
- misalignment
- displacement of the beam spot

The resulting bias is observed to be roughly linear in the number of primary vertices. Consequently, the effect can be corrected without deeper understanding of the underlying reason by measuring the dependence of the mean missing transverse momentum in x or y direction on the number of primary vertices. The values are then corrected by shifting the means back to zero.

In this framework, the Z->mumu phase space property of no intrinsic missing transverse momentum is leveraged to find out the aforementioned dependence.
The correction procedure can be roughly categorized into five steps:
1. preparations
2. histograms
3. fits
4. conversion to json scheme
5. validation

## Multi-year workflow

The recommended interface for production is the Snakemake workflow. For each
era and process it submits the missing NanoAOD snapshots as ProcIds in one
HTCondor cluster, then runs histogramming, fitting, JSON conversion, and
validation when every expected snapshot is present. Completed snapshots are
not resubmitted when an array is retried.

Bootstrap the repository-local workflow environment once:

```bash
workflow/bootstrap
```

Create a VOMS proxy, then run the example Run 3 campaign end to end:

```bash
voms-proxy-init --voms cms --valid 192:00 -rfc
workflow/run --campaign workflow/campaigns/run3.yaml
```

For execution, the launcher validates the current proxy and stages a private,
atomic copy at `~/proxy/x509up_u<uid>`. It resolves this to its canonical
absolute AFS path before passing it to HTCondor, so a proxy under
login-node-local `/tmp` is not used directly.

Useful read-only views are:

```bash
workflow/run --campaign workflow/campaigns/run3.yaml --dry-run
workflow/run --campaign workflow/campaigns/run3.yaml --summary
```

Campaign YAML files select eras, processes, MET types, output versions, local
threads, Condor resources, and per-era overrides. A repeated invocation resumes
from verified outputs. Generated results remain under `results/`, while
snapshots remain in the EOS location configured by the analysis.

The individual commands below remain available for development and debugging.

## 1. Preparations

The preparations include the steps from data and simulation files in the NANOAOD data format to flat ntuples which include only the necessary information, i.e. missing transverse momentum as well as the number of good reconstructed primary vertices, and the pileup correction.
In the framework, this step consists of three sub-steps, that are:
a) Configuration of the setup
b) Collecting the data files
c) Running the ntuple production

### a) Configuration of the setup

Running `. env.sh` loads the non-interactive LCG 107 analysis environment and,
when present, the repository-local workflow virtual environment. Proxy checks
are performed by `workflow/run`, so sourcing the environment is safe inside
batch jobs. In the `inputs/config` directory, you can add new eras. Please be
sure to use a consistent nomenclature and add all necessary information, i.e.
datasets, golden JSON, and labels.

### b) Collecting the data files

Now you can run the main file using the preparation option:

`python3 get_xy_corrs.py -Y 2022_Summer22 --prep`

This will query the files of the datasets in the `inputs/config/datasets.json` file and write the file lists to `inputs/nanoAODs/{year}.json`, which will be of use in the next step.

### c) Running the ntuple production

The ntuple production takes the files in `inputs/nanoAODs/{year}.json`, filters out the data events fulfilling the golden lumi json, and applies a selection to the Z->mumu phase space to both data and simulation. The standard version will construct condor jobs and print how to start the jobs. You can also run locally by providing the option `-j 8` for 8 parallel processes:

`python3 get_xy_corrs.py -Y 2022_Summer22 -S`

The snapshots are automatically saved in your EOS userspace. You can change that in the corresponding entry in `inputs/config/paths.py`.

## 2. Histograms

The flat ntuples produced in the previous step are used to create 2d histograms of the x or y component of the missing transverse momentum against the number of reconstructed good primary vertices. These histograms are then saved to a root directory determined in `inputs/config/paths.py`.
The arguments needed are:

`python3 get_xy_corrs.py -Y 2022_Summer22 -H -j 8`,

where once again the option `-j 8` uses multithreading techniques, now not using the multiprocessing tool in python but rather the ROOT internal method, speeding up the histogramming process considerably.
Before the histogram production step, the files created in the previous step are checked for corruption. You will be prompted whether you wish to delete the corrupted files. The statistics for the calculation should suffice even if many files are corrupted. If all files are broken, you can check the logs in `results/condor/{version}/{year}/{dtmc}/logs/`. If you are sure, the files are not corrupted, e.g. if you run the histogramming step a second time, you can skip the snapshot check by adding `--skip_check`.

## 3. Fits

The fits are done on directly filled weighted profiles of each MET component
against the number of good primary vertices. The profile-bin means and their
statistical errors are used in a linear fit over `10 <= PV_npvsGood <= 70`:

`python3 get_xy_corrs.py -Y 2022_Summer22 -C`

The results and plots of the fits are written to the directory specified in the
`inputs/config/paths.py` file. The slope-intercept covariance gives the
uncertainty in the fitted component at a given number of vertices:

```text
sigma(N)^2 = N^2 Var(m) + Var(c) + 2 N Cov(m,c)
```

Correctionlib exposes two statistical nuisances. The `stat_xup/dn` pt and phi
keys form one correlated x-component variation; the corresponding `stat_yup/dn`
keys form the y-component variation.

## 4. Conversion to json scheme

The last step is the conversion to the json pog integration scheme. It can be started with the following command:

`python3 get_xy_corrs.py -Y 2022_Summer22 --convert`

## 5. Validation

A closure test is performed by comparing the phi modulation of the missing transverse momentum component before and after correction, taking into account systematic variations:

`python3 get_xy_corrs.py -Y 2022_Summer22 --validate -j 8`

The results should show an almost flat MET phi distribution after correction.
Validation also writes corrected x/y profiles versus NPV and residual linear-fit
diagnostics for the nominal, statistical, and MC pileup-weight variations.


## Further options

The types of missing transverse momentum that are investigated can be controlled with the option `--met MET,PuppiMET`. They must be defined in the snapshot process. NB that for v15 there is no `MET` field in the NANOAOD, so use `--met PuppiMET` instead.

The type of pileup can be investigated with the option `--pileup PV_npvsGood`.

A version name can be given to the currently used correction via `-V v0`.

Debug output can be printed by adding `--debug`.

The correction can be performed only on data or MC with the option
`--processes MC,DATA`.


## Troubleshooting

If you encounter a crash like

```bash
python3 get_xy_corrs.py -Y 2024_Summer24 --prep
2026-08-19 12:03:52,876 - INFO - Main script started for 2024_Summer24, MET,PuppiMET,CaloMET,ChsMET,DeepMETResolutionTune,DeepMETResponseTune,RawMET,RawPuppiMET,TkMET, and DATA,MC.
2026-08-19 12:03:52,876 - INFO - Starting das queries.
Python path configuration:
  PYTHONHOME = '/cvmfs/sft.cern.ch/lcg/releases/Python/3.9.12-9a1bc/x86_64-el9-gcc11-opt'
  PYTHONPATH = (not set)
  program name = '/usr/bin/python3'
  isolated = 0
  environment = 1
  user site = 1
  import site = 1
  sys._base_executable = '/usr/bin/python3'
  sys.base_prefix = '/cvmfs/sft.cern.ch/lcg/releases/Python/3.9.12-9a1bc/x86_64-el9-gcc11-opt'
  sys.base_exec_prefix = '/cvmfs/sft.cern.ch/lcg/releases/Python/3.9.12-9a1bc/x86_64-el9-gcc11-opt'
  sys.platlibdir = 'lib64'
  sys.executable = '/usr/bin/python3'
  sys.prefix = '/cvmfs/sft.cern.ch/lcg/releases/Python/3.9.12-9a1bc/x86_64-el9-gcc11-opt'
  sys.exec_prefix = '/cvmfs/sft.cern.ch/lcg/releases/Python/3.9.12-9a1bc/x86_64-el9-gcc11-opt'
  sys.path = [
    '/cvmfs/sft.cern.ch/lcg/releases/Python/3.9.12-9a1bc/x86_64-el9-gcc11-opt/lib64/python39.zip',
    '/cvmfs/sft.cern.ch/lcg/releases/Python/3.9.12-9a1bc/x86_64-el9-gcc11-opt/lib64/python3.9',
    '/cvmfs/sft.cern.ch/lcg/releases/Python/3.9.12-9a1bc/x86_64-el9-gcc11-opt/lib64/python3.9/lib-dynload',
  ]
Fatal Python error: init_fs_encoding: failed to get the Python codec of the filesystem encoding
Python runtime state: core initialized
ModuleNotFoundError: No module named 'encodings'
```

then try

```bash
env -u PYTHONHOME python3 get_xy_corrs.py -Y 2024_Summer24 --prep
```
