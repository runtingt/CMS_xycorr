from array import array
import json
import math

import correctionlib
import numpy as np
import pytest
import ROOT

from python.correction.convert2json import (
    formula_expressions,
    formula_object,
    make_correction_with_formula,
)
from python.correction.correction_extractor import (
    _get_root_object,
    fit_profile,
)


PARAMETERS = [
    0.03, 0.2, -0.02, -0.4,
    0.004, 0.12, -0.00036,
    0.005, 0.15, -0.0004875,
]


def evaluate_formula(expression, met_pt, met_phi, npv):
    formula = ROOT.TFormula("formula_test", expression)
    assert formula.IsValid()
    for index, value in enumerate(PARAMETERS):
        formula.SetParameter(index, value)
    return formula.EvalPar(array("d", [met_pt, met_phi, npv]))


def components(pt, phi):
    return pt * math.cos(phi), pt * math.sin(phi)


@pytest.mark.parametrize("npv", [10.0, 35.0, 70.0])
@pytest.mark.parametrize("met_pt,met_phi", [(30.0, 0.2), (100.0, -2.0)])
def test_component_variations_use_npv(npv, met_pt, met_phi):
    expressions = formula_expressions()
    values = {
        key: evaluate_formula(expression, met_pt, met_phi, npv)
        for key, expression in expressions.items()
    }
    nominal_x, nominal_y = components(values["pt"], values["phi"])
    sigma_x = math.sqrt(
        (npv * PARAMETERS[4])**2 + PARAMETERS[5]**2
        + 2 * npv * PARAMETERS[6]
    )
    sigma_y = math.sqrt(
        (npv * PARAMETERS[7])**2 + PARAMETERS[8]**2
        + 2 * npv * PARAMETERS[9]
    )

    x_up = components(values["pt_stat_xup"], values["phi_stat_xup"])
    x_dn = components(values["pt_stat_xdn"], values["phi_stat_xdn"])
    y_up = components(values["pt_stat_yup"], values["phi_stat_yup"])
    y_dn = components(values["pt_stat_ydn"], values["phi_stat_ydn"])

    assert x_up == pytest.approx((nominal_x + sigma_x, nominal_y))
    assert x_dn == pytest.approx((nominal_x - sigma_x, nominal_y))
    assert y_up == pytest.approx((nominal_x, nominal_y + sigma_y))
    assert y_dn == pytest.approx((nominal_x, nominal_y - sigma_y))


def make_toy_profile(name, size, seed):
    rng = np.random.default_rng(seed)
    profile = ROOT.TProfile(name, "", 50, 0.0, 100.0)
    x = rng.uniform(5.0, 80.0, size)
    y = 0.07 * x - 0.4 + rng.normal(0.0, 8.0, size)
    for x_value, y_value in zip(x, y):
        profile.Fill(float(x_value), float(y_value))
    return profile


def test_profile_fit_and_statistical_scaling():
    small, _ = fit_profile(make_toy_profile("small", 20_000, 3), "fit_small")
    large, _ = fit_profile(make_toy_profile("large", 80_000, 4), "fit_large")

    assert small["m"] == pytest.approx(0.07, abs=0.006)
    assert small["c"] == pytest.approx(-0.4, abs=0.3)
    assert small["fit_status"] == 0
    assert small["ndf"] > 0
    assert large["m_stat"] / small["m_stat"] == pytest.approx(0.5, rel=0.25)


def test_failed_fit_is_rejected():
    empty = ROOT.TProfile("empty", "", 50, 0.0, 100.0)
    with pytest.raises(RuntimeError, match="failed|degrees of freedom"):
        fit_profile(empty, "fit_empty")


def test_missing_profile_is_reported(tmp_path):
    path = tmp_path / "missing.root"
    root_file = ROOT.TFile(str(path), "RECREATE")
    ROOT.TH2D("present", "", 2, 0, 2, 2, 0, 2).Write()
    root_file.Close()
    root_file = ROOT.TFile.Open(str(path))
    with pytest.raises(RuntimeError, match="missing_profile"):
        _get_root_object(root_file, "missing_profile", "TProfile")
    root_file.Close()


def test_invalid_covariance_is_rejected():
    invalid = {
        "m": 0.03,
        "c": 0.2,
        "m_stat": 0.004,
        "c_stat": 0.12,
        "covariance": 1.0,
    }
    with pytest.raises(ValueError, match="positive semidefinite"):
        formula_object(invalid, invalid, formula_expressions()["pt"])


def test_parametric_bootstrap_matches_prediction_error():
    predictions = []
    reported = []
    npv = 35.0
    for replica in range(24):
        params, _ = fit_profile(
            make_toy_profile(f"bootstrap_{replica}", 4_000, replica + 100),
            f"fit_bootstrap_{replica}",
        )
        predictions.append(params["m"] * npv + params["c"])
        reported.append(
            math.sqrt(
                npv**2 * params["m_stat"]**2
                + params["c_stat"]**2
                + 2 * npv * params["covariance"]
            )
        )
    empirical = np.std(predictions, ddof=1)
    assert empirical / np.mean(reported) == pytest.approx(1.0, rel=0.35)


def test_correctionlib_round_trip_preserves_public_keys(tmp_path):
    year = "toy"
    correction_dir = tmp_path / "v1" / year
    correction_dir.mkdir(parents=True)
    axis = {
        "m": 0.03,
        "m_stat": 0.004,
        "c": 0.2,
        "c_stat": 0.12,
        "covariance": -0.00036,
        "correlation": -0.75,
    }
    payload = {
        "PuppiMET": {
            "PV_npvsGood": {
                "_x": {"nom": axis},
                "_y": {"nom": {**axis, "m": -0.02, "c": -0.4}},
            }
        }
    }
    with (correction_dir / "DATA.json").open("w") as output:
        json.dump(payload, output)

    make_correction_with_formula(
        str(correction_dir) + "/", year, ["DATA"], ["PuppiMET"]
    )
    schema = tmp_path / "v1" / "schemaV2_toy.json"
    correction = correctionlib.CorrectionSet.from_file(str(schema))[
        "met_xy_corrections"
    ]
    for key in [
        "pt", "phi", "pt_stat_xup", "pt_stat_xdn",
        "pt_stat_yup", "pt_stat_ydn", "phi_stat_xup",
        "phi_stat_xdn", "phi_stat_yup", "phi_stat_ydn",
    ]:
        assert math.isfinite(
            correction.evaluate(key, "PuppiMET", "DATA", 30.0, 0.2, 35.0)
        )
    with pytest.raises(Exception):
        correction.evaluate("pt_stat_eigen", "PuppiMET", "DATA", 30.0, 0.2, 35.0)
