import ROOT
import os
import logging

logger = logging.getLogger(__name__)


def plot_2dim(
        h,
        axis=["",""],
        outfile="dummy.pdf",
        xrange = [0,100],
        yrange = [-100,100],
        lumi = '2022, 13.6 TeV',
        drawoption='COLZ',
        lines = False,
        results = ["", ""],
        profile = None,
    ):
    c = ROOT.TCanvas("c", '', 800, 600)
    ROOT.gROOT.SetBatch(1)
    ROOT.gPad.SetGrid()

    h.SetStats(0)
    h.GetXaxis().SetRangeUser(xrange[0], xrange[1])
    h.GetYaxis().SetRangeUser(yrange[0], yrange[1])

    h.GetXaxis().SetLabelSize(0.04)
    h.GetXaxis().SetTitleOffset(1.05)
    h.GetXaxis().SetTitleSize(0.045)
    h.GetXaxis().SetTitle(axis[0])

    h.GetYaxis().SetLabelSize(0.04)
    h.GetYaxis().SetTitle(axis[1])
    h.GetYaxis().SetTitleOffset(1.05)
    h.GetYaxis().SetTitleSize(0.045)

    c.SetRightMargin(0.12)
    ROOT.TGaxis.SetMaxDigits(3)

    h.Draw(drawoption)
    h.SetTitle('')

    cmsTex=ROOT.TLatex()
    cmsTex.SetTextFont(42)
    cmsTex.SetTextSize(0.025)
    cmsTex.SetNDC()
    cmsTex.SetTextSize(0.04)
    cmsTex.DrawLatex(0.11,0.915,'#bf{CMS} #it{Preliminary}')
    cmsTex.SetTextAlign(31)
    cmsTex.DrawLatex(0.88, 0.915, lumi)

    cmsTex.SetTextSize(0.02)
    stats = ROOT.TPaveText(0.33, 0.82, 0.86, 0.88, "br ARC NDC")
    stats.SetFillColorAlpha(ROOT.kGray, 0.8)
    stats.AddText(fr"Fit result: {results[0]} ({results[2]}) \times NPV + {results[1]} ({results[3]})")
    stats.GetListOfLines().Last().SetTextColor(ROOT.kRed)
    stats.Draw("SAME")

    if lines:
        prof = profile if profile is not None else h.ProfileX("prof", 0, 200)
        prof.SetLineWidth(2)
        prof.SetLineColor(ROOT.kBlack)
        prof.Draw("same")
        color = [9, 9, 0]
        for i, line in enumerate(lines):
            line.Draw("same")
            line.SetLineWidth(2)
            line.SetLineColor(ROOT.kRed - color[i])

    path = outfile.replace(outfile.split('/')[-1], '')
    os.makedirs(path, exist_ok=True)

    c.SaveAs(outfile+'.png')
    c.SaveAs(outfile+'.pdf')    

    return


def plot_ratio(
        h_base,
        hists,
        labels=["", ""],
        dsetlabel="",
        colors=[ROOT.kGray+2, ROOT.kBlack, ROOT.kRed, ROOT.kBlue],
        axis=["", ""],
        title="", 
        outfile="dummy.pdf", 
        text=['','',''], 
        xrange=[60, 120],
        ratiorange = [0.8, 1.2],
        lumi = '5.05 fb^{-1} (2022, 13.6 TeV)'
    ):
    c = ROOT.TCanvas("c", title, 800, 700)
    ROOT.gROOT.SetBatch(1)

    # Split canvas
    pad1 = ROOT.TPad("pad1", "pad1", 0,0.3,1,1)
    pad1.SetBottomMargin(0.03)
    pad1.SetLeftMargin(0.1)

    # Upper pad
    pad1.Draw()
    pad1.cd()

    # legend
    legend = ROOT.TLegend(0.65, 0.65, 0.88, 0.82)
    legend.SetBorderSize(0)
    legend.AddEntry(h_base, labels[0])

    # xaxis
    xaxis = h_base.GetXaxis()
    xaxis.SetRangeUser(xrange[0], xrange[1])
    xaxis.SetLabelSize(0)

    # yaxis
    yaxis = h_base.GetYaxis()
    h_base_max = h_base.GetBinContent(h_base.GetMaximumBin())
    yaxis.SetRangeUser(0.0, 1.5 * h_base_max)
    yaxis.SetTitle(axis[1])
    yaxis.SetTitleSize(0.065)
    yaxis.SetTitleOffset(0.7)
    yaxis.SetLabelSize(0.05)
    yaxis.SetMaxDigits(3)

    # draw base histogram
    h_base.SetStats(0)
    h_base.SetLineWidth(2)
    h_base.SetLineColor(colors[0])
    h_base.SetTitle('')
    h_base.Draw()

    ratios = []

    # alternative histograms:
    for i, h in enumerate(hists):
        h.SetLineWidth(2)
        h.SetStats(0)
        h.SetLineColor(colors[1+i])
        h.SetTitle('')
        h.GetXaxis().SetRangeUser(xrange[0], xrange[1])
        legend.AddEntry(h, labels[1+i])

        h.Draw("same")

        h_c = h.Clone()

        # ratio properties
        h_c.Divide(h_base)
        
        # xaxis
        xaxis = h_c.GetXaxis()
        xaxis.SetLabelSize(0.12)
        xaxis.SetTickSize(0.08)
        xaxis.SetTitleSize(0.15)
        xaxis.SetTitleOffset(0.9)
        xaxis.SetTitle(axis[0])

        # yaxis
        yaxis = h_c.GetYaxis()
        yaxis.SetTitleSize(0.15)
        yaxis.SetLabelSize(0.12)
        yaxis.SetNdivisions(502)
        yaxis.SetRangeUser(0.5, 1.5)
        yaxis.SetTitleOffset(0.3)
        yaxis.SetTitle('ratio')

        ratios.append(h_c)

    legend.Draw("same")

    # canvas description
    cmsTex=ROOT.TLatex()
    cmsTex.SetTextFont(42)
    cmsTex.SetNDC()
    cmsTex.SetTextSize(0.045)
    cmsTex.DrawLatex(0.13,0.83,'#bf{CMS} #it{Preliminary}')
    cmsTex.SetTextSize(0.036)
    cmsTex.DrawLatex(0.65, 0.83, dsetlabel)
    cmsTex.SetTextSize(0.045)
    cmsTex.SetTextAlign(31)
    cmsTex.DrawLatex(0.9, 0.913, lumi)


    # lower pad
    c.cd()
    pad2 = ROOT.TPad("pad2", "pad2", 0,0,1,0.3)
    pad2.SetTopMargin(.035)
    pad2.SetBottomMargin(.3)
    pad2.Draw()
    pad2.cd()

    for h in ratios:
        h.Draw("same")

    line = ROOT.TLine(xrange[0], 1, xrange[1], 1)
    line.SetLineWidth(2)
    line.Draw("same")

    c.SaveAs(outfile)    
    c.SaveAs(outfile.split(".pdf")[0]+".png")

    return 


def plot_profile_closure(
    profile,
    outfile,
    axis=("NPV", "MET component (GeV)"),
    lumi="",
    dsetlabel="",
):
    """Plot a corrected MET-component profile and its residual linear fit."""
    canvas = ROOT.TCanvas("closure_canvas", "", 800, 600)
    ROOT.gROOT.SetBatch(1)
    ROOT.gPad.SetGrid()

    profile.SetStats(0)
    profile.SetTitle("")
    profile.SetLineWidth(2)
    profile.SetMarkerStyle(20)
    profile.SetMarkerSize(0.7)
    profile.GetXaxis().SetRangeUser(0, 100)
    profile.GetXaxis().SetTitle(axis[0])
    profile.GetYaxis().SetTitle(axis[1])

    fit = ROOT.TF1(f"closure_plot_{profile.GetName()}", "[0]*x+[1]", 10, 70)
    result = profile.Fit(fit, "Q0RS", "", 10, 70)
    if int(result) != 0:
        raise RuntimeError(
            f"Closure fit failed for {profile.GetName()} with status {int(result)}."
        )
    profile.Draw("E1")
    fit.SetLineColor(ROOT.kRed)
    fit.Draw("same")

    zero = ROOT.TLine(0, 0, 100, 0)
    zero.SetLineStyle(2)
    zero.Draw("same")

    label = ROOT.TLatex()
    label.SetNDC()
    label.SetTextFont(42)
    label.SetTextSize(0.04)
    label.DrawLatex(0.11, 0.915, '#bf{CMS} #it{Preliminary}')
    label.SetTextAlign(31)
    label.DrawLatex(0.88, 0.915, lumi)
    label.SetTextAlign(11)
    label.SetTextSize(0.03)
    label.DrawLatex(0.14, 0.84, dsetlabel)
    label.DrawLatex(
        0.14,
        0.79,
        (
            f"slope = {fit.GetParameter(0):+.3g} #pm "
            f"{fit.GetParError(0):.2g} GeV/vertex"
        ),
    )

    os.makedirs(os.path.dirname(outfile), exist_ok=True)
    canvas.SaveAs(outfile + '.png')
    canvas.SaveAs(outfile + '.pdf')
