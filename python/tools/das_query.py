import json
import os
import logging
import subprocess
import tempfile

logger = logging.getLogger(__name__)


def get_files_from_das(datasets, nanoAODs, redirector, year, processes=None):
    '''
    make file lists from DAS identifiers in datasets.json

    Args:
    datasets (str): location of datasets.json
    '''

    logger.info("Starting das queries.")

    if not os.path.exists(datasets):
        logger.critical(f"Path {datasets} does not exist.")

    else:
        with open(datasets) as f:
            dsets = json.load(f)[year]

        fdict = {}

        selected_processes = list(dsets) if processes is None else processes
        missing = set(selected_processes) - set(dsets)
        if missing:
            raise KeyError(
                f"Processes {sorted(missing)} are not configured for {year}."
            )

        # looping through selected datasets (DATA, MC)
        for k in selected_processes:
            fdict[k] = []

            # loop through sub datasets
            for d in dsets[k]["names"]:
                command = ["dasgoclient", "-query", f"file dataset={d}"]
                logger.debug("Running %s", command)
                result = subprocess.run(
                    command,
                    check=False,
                    text=True,
                    capture_output=True,
                )
                if result.returncode != 0:
                    raise RuntimeError(
                        f"DAS query failed for {d}: {result.stderr.strip()}"
                    )
                fdict[k] += [
                    redirector + line.strip()
                    for line in result.stdout.splitlines()
                    if line.strip()
                ]

            if not fdict[k]:
                raise RuntimeError(
                    f"DAS returned no files for selected process {k} in "
                    f"{year}. Refusing to create an empty manifest."
                )

        output_dir = os.path.dirname(nanoAODs) or "."
        os.makedirs(output_dir, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(
            prefix=".nanoAODs.", suffix=".json", dir=output_dir
        )
        try:
            with os.fdopen(descriptor, "w") as output:
                json.dump(fdict, output, indent=4)
            os.replace(temporary, nanoAODs)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    logger.info(f"File lists saved in {nanoAODs}")

    return
