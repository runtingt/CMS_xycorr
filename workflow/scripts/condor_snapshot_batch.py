#!/usr/bin/env python3
"""Submit and monitor one HTCondor snapshot array for an era/process pair."""

import argparse
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import time


def selected_files(manifest, process):
    with Path(manifest).open() as source:
        contents = json.load(source)
    if process not in contents:
        raise RuntimeError(f"{manifest} does not contain process {process}.")
    files = contents[process]
    if not isinstance(files, list) or not files:
        raise RuntimeError(
            f"{manifest} contains no input files for selected process {process}."
        )
    return files


def snapshot_path(snapshot_dir, index):
    return Path(snapshot_dir) / f"file_{index}.root"


def missing_indices(snapshot_dir, count):
    missing = []
    for index in range(count):
        path = snapshot_path(snapshot_dir, index)
        if not path.is_file() or path.stat().st_size == 0:
            missing.append(index)
    return missing


def build_submit_description(
    *, job_script, log_dir, event_log, proxy, indices, cpus, memory_mb,
    disk_mb, job_flavour, max_materialize, batch_name,
):
    if not indices:
        raise ValueError("Cannot submit an empty snapshot array.")
    index_rows = "\n".join(str(index) for index in indices)
    return f"""universe = vanilla
executable = /bin/bash
arguments = {Path(job_script).resolve()} $(snapshot_index)
initialdir = {Path.cwd().resolve()}
output = {Path(log_dir).resolve()}/index_$(snapshot_index)_$(Cluster)_$(Process).out
error = {Path(log_dir).resolve()}/index_$(snapshot_index)_$(Cluster)_$(Process).err
log = {Path(event_log).resolve()}
request_cpus = {int(cpus)}
request_memory = {int(memory_mb)}MB
request_disk = {int(disk_mb)}MB
+JobFlavour = \"{job_flavour}\"
batch_name = {batch_name}
getenv = True
should_transfer_files = NO
use_x509userproxy = True
x509userproxy = {Path(proxy).resolve(strict=True)}
max_materialize = {int(max_materialize)}
max_idle = {int(max_materialize)}
queue snapshot_index from (
{index_rows}
)
"""


def parse_cluster_id(output):
    match = re.search(r"(\d+)\.\d+", output)
    if not match:
        raise RuntimeError(f"Could not parse condor_submit output: {output!r}")
    return match.group(1)


def query_condor(command):
    result = subprocess.run(
        command,
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"{' '.join(command)} failed: {result.stderr.strip()}"
        )
    return [line.split() for line in result.stdout.splitlines() if line.strip()]


def cluster_status(cluster_id):
    queued = query_condor(
        ["condor_q", cluster_id, "-af", "ProcId", "JobStatus"]
    )
    if queued:
        held = [row[0] for row in queued if len(row) > 1 and row[1] == "5"]
        if held:
            preview = ", ".join(held[:10])
            return "held", preview
        return "active", None

    history = query_condor(
        [
            "condor_history", cluster_id, "-limit", "1", "-af",
            "ProcId", "JobStatus", "ExitCode",
        ]
    )
    if history:
        return "finished", None
    return "unknown", None


def wait_for_cluster(
    cluster_id, poll_interval=20, scheduler_timeout=120,
):
    unknown_since = time.monotonic()
    while True:
        status, detail = cluster_status(cluster_id)
        if status == "finished":
            return
        if status == "held":
            raise RuntimeError(
                f"Cluster {cluster_id} has held ProcIds ({detail}). "
                "Inspect them with condor_q -hold."
            )
        if status == "active":
            unknown_since = None
        elif unknown_since is None:
            unknown_since = time.monotonic()
        elif time.monotonic() - unknown_since >= scheduler_timeout:
            raise RuntimeError(
                f"Cluster {cluster_id} was visible in neither condor_q nor "
                f"condor_history for {scheduler_timeout} seconds."
            )
        time.sleep(poll_interval)


def wait_for_outputs(snapshot_dir, count, latency_wait):
    deadline = time.monotonic() + latency_wait
    missing = missing_indices(snapshot_dir, count)
    while missing and time.monotonic() < deadline:
        time.sleep(min(5, latency_wait))
        missing = missing_indices(snapshot_dir, count)
    return missing


def write_atomic_json(path, contents):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(json.dumps(contents, indent=2) + "\n")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def write_job_script(path, args):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "python3", "get_xy_corrs.py", "--snapshot",
        "--version", args.version,
        "--year", args.era,
        "--processes", args.process,
        "--met", args.mets,
        "--pileup", args.pileup,
        "--condor", '"$1"',
    ]
    quoted_command = " ".join(
        value if value == '"$1"' else shlex.quote(value)
        for value in command
    )
    path.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        f"cd {shlex.quote(str(Path(args.repo).resolve()))}\n"
        "source env.sh\n"
        f"{quoted_command}\n"
    )
    path.chmod(0o755)


def run(args):
    inputs = selected_files(args.manifest, args.process)
    count = len(inputs)
    snapshot_dir = Path(args.snapshot_dir)
    marker = Path(args.marker)
    state = Path(args.state)
    log_dir = Path(args.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    missing = missing_indices(snapshot_dir, count)
    if not missing:
        write_atomic_json(marker, {"expected_snapshots": count})
        state.unlink(missing_ok=True)
        return

    if state.is_file():
        previous = json.loads(state.read_text())
        cluster_id = str(previous["cluster_id"])
        wait_for_cluster(
            cluster_id, args.poll_interval, args.scheduler_timeout
        )
        missing = wait_for_outputs(snapshot_dir, count, args.latency_wait)
        state.unlink(missing_ok=True)
        if not missing:
            write_atomic_json(marker, {"expected_snapshots": count})
            return

    work_dir = state.parent
    work_dir.mkdir(parents=True, exist_ok=True)
    job_script = work_dir / f"{args.version}_{args.era}_{args.process}.sh"
    submit_file = work_dir / f"{args.version}_{args.era}_{args.process}.sub"
    event_log = log_dir / "cluster.log"
    write_job_script(job_script, args)
    submit_file.write_text(build_submit_description(
        job_script=job_script,
        log_dir=log_dir,
        event_log=event_log,
        proxy=args.proxy,
        indices=missing,
        cpus=args.cpus,
        memory_mb=args.memory_mb,
        disk_mb=args.disk_mb,
        job_flavour=args.job_flavour,
        max_materialize=args.max_materialize,
        batch_name=f"xycorr_{args.version}_{args.era}_{args.process}",
    ))
    result = subprocess.run(
        ["condor_submit", "-terse", str(submit_file)],
        check=True,
        text=True,
        capture_output=True,
    )
    cluster_id = parse_cluster_id(result.stdout)
    write_atomic_json(state, {
        "cluster_id": cluster_id,
        "event_log": str(event_log.resolve()),
        "indices": missing,
    })
    wait_for_cluster(cluster_id, args.poll_interval, args.scheduler_timeout)

    missing = wait_for_outputs(snapshot_dir, count, args.latency_wait)
    state.unlink(missing_ok=True)
    if missing:
        preview = ", ".join(map(str, missing[:10]))
        raise RuntimeError(
            f"Cluster {cluster_id} finished without {len(missing)} expected "
            f"snapshots (first indices: {preview}). Rerun to retry only those files."
        )
    write_atomic_json(marker, {"expected_snapshots": count})


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--era", required=True)
    parser.add_argument("--process", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--mets", required=True)
    parser.add_argument("--pileup", required=True)
    parser.add_argument("--snapshot-dir", required=True)
    parser.add_argument("--marker", required=True)
    parser.add_argument("--state", required=True)
    parser.add_argument("--log-dir", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--proxy", required=True)
    parser.add_argument("--cpus", type=int, required=True)
    parser.add_argument("--memory-mb", type=int, required=True)
    parser.add_argument("--disk-mb", type=int, required=True)
    parser.add_argument("--job-flavour", required=True)
    parser.add_argument("--max-materialize", type=int, required=True)
    parser.add_argument("--latency-wait", type=int, default=90)
    parser.add_argument("--poll-interval", type=int, default=20)
    parser.add_argument("--scheduler-timeout", type=int, default=120)
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
