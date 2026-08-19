import os
import shutil
import logging
import glob
logger = logging.getLogger(__name__)


def setup_job(condor_dir, dtmc, year, met):
    logger.info("Setting up the job script")
    # setup condor job script
    path = os.getcwd()
    job_script = f"#!/bin/bash \n"\
        f"export X509_USER_PROXY=$2 \n"\
        "voms-proxy-info -all \n"\
        "voms-proxy-info -all -file $2 \n"\
        f"cd {path} \n"\
        f"source env.sh \n"\
        f"python get_xy_corrs.py -S --condor $1 --process {dtmc} --year {year} --met {met} --debug"

    log_dir = f'{condor_dir}{dtmc}/logs/'

    # first remove directory with old logs
    if os.path.exists(log_dir):
        remove = input("Remove old log files? (y/n)")
        if remove:
            shutil.rmtree(log_dir)

    # then create new
    os.makedirs(log_dir, exist_ok=True)

    with open(f'{condor_dir}{dtmc}/job.sh', 'w') as job:
        job.write(job_script)

    return


def setup_condor_lxplus(njobs, condor_dir, dtmc, proxy_path):

    logger.info("Setting up the submit file.")

    # setup condor submit file
    submit_script = f"""executable = ./job.sh
arguments = $(Process) $(Proxy_path)

# output/error/log files
output = logs/job_$(Cluster)_$(Process).out
error = logs/job_$(Cluster)_$(Process).err
log = logs/job_$(Cluster)_$(Process).log

# job requirements
universe = vanilla
+JobFlavour = "microcentury"
RequestCPUs = 1

Proxy_path = {proxy_path}

queue {njobs}"""
    
    path_submit = f'{condor_dir}{dtmc}/submit.sub'
    logger.info(f"Saving submit file in {path_submit}.")

    with open(path_submit, 'w') as submit:
        submit.write(submit_script)

    run_script = f"cd {condor_dir}{dtmc}/ && condor_submit submit.sub && cd ../../../../.."

    logger.info(f"Run script for {njobs} via: \n{run_script}")
    return
