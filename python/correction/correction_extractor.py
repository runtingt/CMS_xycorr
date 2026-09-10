import ROOT
import python.tools.plot as plot
import json
import logging
import math


logger = logging.getLogger(__name__)

FIT_MIN = 10.0
FIT_MAX = 70.0


def _get_root_object(root_file, name, expected_class):
    obj = root_file.Get(name)
    if not obj:
        raise RuntimeError(
            f"Required ROOT object '{name}' is missing from "
            f"{root_file.GetName()}. Regenerate the histogram stage."
        )
    if not obj.InheritsFrom(expected_class):
        raise TypeError(
            f"ROOT object '{name}' in {root_file.GetName()} is a "
            f"{obj.ClassName()}, expected {expected_class}."
        )
    obj.SetDirectory(ROOT.nullptr)
    return obj


def fit_profile(profile, function_name="pol1"):
    """Fit a MET-component profile and return parameters and diagnostics."""
    function = ROOT.TF1(function_name, "[0]*x+[1]", FIT_MIN, FIT_MAX)
    fit_result = profile.Fit(function, "Q0RS", "", FIT_MIN, FIT_MAX)
    status = int(fit_result)
    result = fit_result.Get()
    if status != 0 or not result or not result.IsValid():
        raise RuntimeError(
            f"Fit of {profile.GetName()} failed with status {status}."
        )

    m = function.GetParameter(0)
    c = function.GetParameter(1)
    m_stat = function.GetParError(0)
    c_stat = function.GetParError(1)
    covariance = fit_result.CovMatrix(0, 1)
    correlation = fit_result.Correlation(0, 1)
    chi2 = function.GetChisquare()
    ndf = function.GetNDF()
    if ndf <= 0:
        raise RuntimeError(
            f"Fit of {profile.GetName()} has no degrees of freedom."
        )
    values = [
        m, c, m_stat, c_stat, covariance, correlation, chi2, float(ndf)
    ]
    if not all(math.isfinite(value) for value in values):
        raise RuntimeError(f"Fit of {profile.GetName()} returned non-finite values.")

    determinant = m_stat**2 * c_stat**2 - covariance**2
    tolerance = 1e-10 * max(
        m_stat**2 * c_stat**2, covariance**2, 1e-30
    )
    if m_stat < 0 or c_stat < 0 or determinant < -tolerance:
        raise RuntimeError(
            f"Fit covariance for {profile.GetName()} is not positive semidefinite."
        )

    probability = ROOT.TMath.Prob(chi2, ndf)
    if probability < 0.01:
        logger.warning(
            "Poor linear-fit probability for %s: chi2/ndf=%.2f/%d (p=%.3g).",
            profile.GetName(), chi2, ndf, probability,
        )

    parameters = {
        "m": m,
        "m_stat": m_stat,
        "c": c,
        "c_stat": c_stat,
        "covariance": covariance,
        "correlation": correlation,
        "fit_status": status,
        "chi2": chi2,
        "ndf": ndf,
        "fit_probability": probability,
    }
    return parameters, function


def get_corrections(
    hist_dir, hbins, corr_dir, plot_dir, mets, pileups, 
    lumilabel, axislabels, datamc
):
    """
    function to get xy corrections and plot results

    hist_dir (str): Directory of histograms.
    hbins (dict): Dictionary with histogram binnings.
    corr_dir (str): Directory for correction jsons.
    plot_dir (str): Directory for plots.
    mets (list): List of mets.
    pileups (list): List of pileups.
    lumilabel (dict): Dictionary for lumi label position and text.
    axislabels (dict): Dictionary for axis labels.
    datamc (list): List of datasets to process (data / mc).
    """

    corr_dict = {}
    for dtmc in datamc:
        for met in mets:
            corr_dict[met] = {}
            for pu in pileups:
                corr_dict[met][pu] = {}
                for xy in ['_x', '_y']:
                    corr_dict[met][pu][xy] = {}

                    if dtmc == 'DATA':
                        variations = {
                            'nom': '_puweight',
                        }

                    else:
                        variations = {
                            'nom': '_puweight',
                            'pu_dn': '_puweightDn',
                            'pu_up': '_puweightUp'
                        }

                    tf = ROOT.TFile.Open(hist_dir+dtmc+'.root', "READ")
                    if not tf or tf.IsZombie():
                        raise OSError(f"Could not open {hist_dir+dtmc+'.root'}")

                    for variation, suffix in variations.items():
                        histogram_name = f'{pu}_{met}{xy}{suffix}'
                        h = _get_root_object(tf, histogram_name, "TH2")
                        profile = _get_root_object(
                            tf, f'{histogram_name}_profile', "TProfile"
                        )

                        fit_name = (
                            f"fit_{dtmc}_{met}_{pu}_{xy}_{variation}"
                            .replace("-", "_")
                        )
                        parameters, f1 = fit_profile(profile, fit_name)
                        corr_dict[met][pu][xy][variation] = parameters

                        stat_unc = (
                            "sqrt(x*x*[2]*[2] + [3]*[3] "
                            "+ 2*x*[4])"
                        )

                        f1_up = ROOT.TF1(
                            fit_name+"_up", f"[0]*x+[1] + {stat_unc}",
                            -10, 110,
                        )
                        f1_up.SetParameter(0, f1.GetParameter(0))
                        f1_up.SetParameter(1, f1.GetParameter(1))
                        f1_up.SetParameter(2, f1.GetParError(0))
                        f1_up.SetParameter(3, f1.GetParError(1))
                        f1_up.SetParameter(4, parameters["covariance"])
                        f1_dn = ROOT.TF1(
                            fit_name+"_dn", f"[0]*x+[1] - {stat_unc}",
                            -10, 110,
                        )
                        f1_dn.SetParameter(0, f1.GetParameter(0))
                        f1_dn.SetParameter(1, f1.GetParameter(1))
                        f1_dn.SetParameter(2, f1.GetParError(0))
                        f1_dn.SetParameter(3, f1.GetParError(1))
                        f1_dn.SetParameter(4, parameters["covariance"])

                        # if variation == "nom":
                        # plot fit results
                        plot.plot_2dim(
                            h,
                            axis=[axislabels['pileup'], (met+xy+'} (GeV)').replace('_', '_{')],
                            outfile=f"{plot_dir}{met}/{dtmc+xy}_{variation}",
                            xrange=[0,100],
                            yrange=[hbins['met'][0], hbins['met'][1]],
                            lumi=lumilabel[dtmc],
                            lines=[f1_up, f1_dn, f1],
                            profile=profile,
                            results=[
                                round(corr_dict[met][pu][xy][variation]["m"],3),
                                round(corr_dict[met][pu][xy][variation]["c"],3),
                                round(corr_dict[met][pu][xy][variation]["m_stat"],3),
                                round(corr_dict[met][pu][xy][variation]["c_stat"],3),
                            ]
                        )

                    tf.Close()

        with open(f"{corr_dir+dtmc}.json", "w") as f:
            json.dump(corr_dict, f, indent=4)
            
    return
