def get_labels(year):

    lumilabels = {
        '2022_Summer22': {
            'DATA': '8.0fb^{-1} (13.6 TeV)',
            'MC': '(13.6 TeV)',
        },
        '2022_Summer22EE': {
            'DATA': '26.7fb^{-1} (13.6 TeV)',
            'MC': '(13.6 TeV)',
        },
        '2023_Summer23': {
            'DATA': '17.6fb^{-1} (13.6 TeV)',
            'MC': '(13.6 TeV)',
        },
        '2023_Summer23BPix': {
            'DATA': '9.5fb^{-1} (13.6 TeV)',
            'MC': '(13.6 TeV)',
        },
        '2024_Summer24': {
            'DATA': '109.82fb^{-1} (13.6 TeV)',
            'MC': '(13.6 TeV)',
        },
    }

    datasetlabels = {
        '2022_Summer22': '2022 preEE',
        '2022_Summer22EE': '2022 postEE',
        '2023_Summer23': '2023 preBPix',
        '2023_Summer23BPix': '2023 postBPix',
        '2024_Summer24': '2024',
    }

    axislabels = {
        f"MET_pt": "MET (GeV)",
        f"MET_phi": "#phi (MET)",
        f"PuppiMET_pt": "PuppiMET (GeV)",
        f"PuppiMET_phi": "#phi (PuppiMET)",
        f"CaloMET_pt": "CaloMET (GeV)",
        f"CaloMET_phi": "#phi (CaloMET)",
        f"ChsMET_pt": "ChsMET (GeV)",
        f"ChsMET_phi": "#phi (ChsMET)",
        f"DeepMETResolutionTune_pt": "DeepMETResolutionTune (GeV)",
        f"DeepMETResolutionTune_phi": "#phi (DeepMETResolutionTune)",
        f"DeepMETResponseTune_pt": "DeepMETResponseTune (GeV)",
        f"DeepMETResponseTune_phi": "#phi (DeepMETResponseTune)",
        f"RawMET_pt": "RawMET (GeV)",
        f"RawMET_phi": "#phi (RawMET)",
        f"RawPuppiMET_pt": "RawPuppiMET (GeV)",
        f"RawPuppiMET_phi": "#phi (RawPuppiMET)",
        f"TkMET_pt": "TkMET (GeV)",
        f"TkMET_phi": "#phi (TkMET)",
        "pileup": "Number of good reconstructed PVs"
    }

    return lumilabels[year], axislabels, datasetlabels[year]
