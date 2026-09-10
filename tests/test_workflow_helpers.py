import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from python.correction import histograms
from python.correction.snapshot_maker import snapshot_quantities
from python.tools import das_query
from workflow.scripts import (
    condor_snapshot_batch,
    stage_proxy,
)


REPO = Path(__file__).resolve().parents[1]


def test_campaign_uses_one_aggregate_2024_era():
    campaign = yaml.safe_load(
        (REPO / "workflow/campaigns/run3.yaml").read_text()
    )
    datasets = json.loads(
        (REPO / "inputs/config/datasets.json").read_text()
    )

    assert [era for era in campaign["eras"] if era.startswith("2024_")] == [
        "2024_Summer24"
    ]
    assert [era for era in datasets if era.startswith("2024_")] == [
        "2024_Summer24"
    ]
    assert "merges" not in campaign


def test_proxy_is_atomically_staged_with_private_permissions(tmp_path):
    source = tmp_path / "local_proxy"
    destination = tmp_path / "shared" / "x509up_u123"
    source.write_bytes(b"first proxy")

    assert stage_proxy.stage_proxy(source, destination) == destination.resolve()
    assert destination.read_bytes() == b"first proxy"
    assert destination.stat().st_mode & 0o777 == 0o600
    assert destination.parent.stat().st_mode & 0o777 == 0o700

    source.write_bytes(b"renewed proxy")
    stage_proxy.stage_proxy(source, destination)
    assert destination.read_bytes() == b"renewed proxy"


def test_snapshot_quantities_does_not_mutate_inputs():
    pileups = ["PV_npvsGood"]
    quantities = snapshot_quantities(pileups, ["PuppiMET"])
    assert pileups == ["PV_npvsGood"]
    assert quantities == [
        "PV_npvsGood", "puWeight", "puWeightUp", "puWeightDn",
        "mass_Z", "PuppiMET_x", "PuppiMET_y",
    ]


def test_das_discovery_respects_selected_processes(tmp_path, monkeypatch):
    datasets = tmp_path / "datasets.json"
    manifest = tmp_path / "manifest.json"
    datasets.write_text(json.dumps({
        "era": {
            "DATA": {"names": ["/data"]},
            "MC": {"names": ["/mc"]},
        }
    }))
    queries = []

    def fake_run(command, **kwargs):
        queries.append(command)
        return SimpleNamespace(
            returncode=0,
            stdout="/store/mc.root\n",
            stderr="",
        )

    monkeypatch.setattr(das_query.subprocess, "run", fake_run)
    das_query.get_files_from_das(
        str(datasets), str(manifest), "root://redirector/", "era", ["MC"]
    )
    assert json.loads(manifest.read_text()) == {
        "MC": ["root://redirector//store/mc.root"]
    }
    assert queries == [["dasgoclient", "-query", "file dataset=/mc"]]


def test_das_discovery_rejects_empty_selected_process(tmp_path, monkeypatch):
    datasets = tmp_path / "datasets.json"
    manifest = tmp_path / "manifest.json"
    datasets.write_text(json.dumps({
        "era": {"MC": {"names": ["/empty"]}}
    }))
    monkeypatch.setattr(
        das_query.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0, stdout="", stderr=""
        ),
    )

    with pytest.raises(RuntimeError, match="no files.*MC"):
        das_query.get_files_from_das(
            str(datasets), str(manifest), "root://redirector/", "era", ["MC"]
        )
    assert not manifest.exists()


def test_condor_snapshot_array_queues_only_missing_indices(tmp_path):
    proxy = tmp_path / "proxy"
    proxy.write_text("proxy")
    proxy_link = tmp_path / "proxy-link"
    proxy_link.symlink_to(proxy)
    jobscript = tmp_path / "job.sh"
    jobscript.write_text("#!/bin/bash\ntrue\n")
    log_dir = tmp_path / "logs"
    log_dir.mkdir()

    description = condor_snapshot_batch.build_submit_description(
        job_script=jobscript,
        log_dir=log_dir,
        event_log=log_dir / "cluster.log",
        proxy=proxy_link,
        indices=[1, 4, 7],
        cpus=1,
        memory_mb=3000,
        disk_mb=4000,
        job_flavour="workday",
        max_materialize=25,
        batch_name="xycorr_test",
    )
    assert "request_memory = 3000MB" in description
    assert "request_disk = 4000MB" in description
    assert '+JobFlavour = "workday"' in description
    assert f"x509userproxy = {proxy.resolve()}" in description
    assert "max_materialize = 25" in description
    assert "queue snapshot_index from (\n1\n4\n7\n)" in description
    assert description.count("queue snapshot_index") == 1


def test_snapshot_batch_skips_completed_files(tmp_path):
    snapshot_dir = tmp_path / "snapshots"
    snapshot_dir.mkdir()
    (snapshot_dir / "file_0.root").write_bytes(b"complete")
    (snapshot_dir / "file_2.root").write_bytes(b"complete")
    (snapshot_dir / "file_3.root").touch()

    assert condor_snapshot_batch.missing_indices(snapshot_dir, 4) == [1, 3]


def test_snapshot_batch_retry_submits_only_missing_files(tmp_path, monkeypatch):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"MC": ["a.root", "b.root", "c.root"]}))
    snapshot_dir = tmp_path / "snapshots"
    snapshot_dir.mkdir()
    (snapshot_dir / "file_0.root").write_bytes(b"complete")
    (snapshot_dir / "file_2.root").write_bytes(b"complete")
    proxy = tmp_path / "proxy"
    proxy.write_text("proxy")
    state = tmp_path / "state" / "batch.json"
    marker = tmp_path / "snapshots.done"
    log_dir = tmp_path / "logs"

    args = SimpleNamespace(
        manifest=str(manifest),
        process="MC",
        snapshot_dir=str(snapshot_dir),
        marker=str(marker),
        state=str(state),
        log_dir=str(log_dir),
        repo=str(REPO),
        proxy=str(proxy),
        version="v2",
        era="2024_Summer24",
        mets="PuppiMET",
        pileup="PV_npvsGood",
        cpus=1,
        memory_mb=2000,
        disk_mb=2000,
        job_flavour="microcentury",
        max_materialize=20,
        latency_wait=0,
        poll_interval=0,
        scheduler_timeout=120,
    )

    def fake_run(command, **kwargs):
        assert command[0] == "condor_submit"
        return SimpleNamespace(returncode=0, stdout="123.0 - 123.0\n")

    def fake_wait(cluster_id, poll_interval, scheduler_timeout):
        assert cluster_id == "123"
        (snapshot_dir / "file_1.root").write_bytes(b"complete")

    monkeypatch.setattr(condor_snapshot_batch.subprocess, "run", fake_run)
    monkeypatch.setattr(condor_snapshot_batch, "wait_for_cluster", fake_wait)
    condor_snapshot_batch.run(args)

    submit_file = state.parent / "v2_2024_Summer24_MC.sub"
    assert "queue snapshot_index from (\n1\n)" in submit_file.read_text()
    assert json.loads(marker.read_text()) == {"expected_snapshots": 3}
    assert not state.exists()


def test_condor_cluster_id_parsing():
    assert condor_snapshot_batch.parse_cluster_id(
        "12345.0 - 12345.17\n"
    ) == "12345"


def test_condor_monitor_tolerates_initial_visibility_race(monkeypatch):
    statuses = iter([
        ("unknown", None),
        ("active", None),
        ("unknown", None),
        ("finished", None),
    ])
    monkeypatch.setattr(
        condor_snapshot_batch, "cluster_status", lambda cluster_id: next(statuses)
    )
    monkeypatch.setattr(condor_snapshot_batch.time, "sleep", lambda seconds: None)

    condor_snapshot_batch.wait_for_cluster(
        "12345", poll_interval=0, scheduler_timeout=120
    )


def test_condor_monitor_reports_held_jobs(monkeypatch):
    monkeypatch.setattr(
        condor_snapshot_batch,
        "cluster_status",
        lambda cluster_id: ("held", "2, 5"),
    )

    with pytest.raises(RuntimeError, match="held ProcIds.*2, 5"):
        condor_snapshot_batch.wait_for_cluster(
            "12345", poll_interval=0, scheduler_timeout=120
        )


def test_histogram_jobs_configure_root_threads(monkeypatch):
    calls = []
    fake_root = SimpleNamespace(
        IsImplicitMTEnabled=lambda: False,
        EnableImplicitMT=lambda jobs: calls.append(jobs),
    )
    monkeypatch.setattr(histograms, "ROOT", fake_root)
    histograms._enable_implicit_mt(6)
    assert calls == [6]
