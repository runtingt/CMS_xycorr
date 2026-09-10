import ROOT
import json
import correctionlib.schemav2 as cs
import correctionlib
import logging
import math

logger = logging.getLogger(__name__)

correctionlib.register_pyroot_binding()


def formula_expressions():
    # Expression for pt correction
    pt_x = "(x * cos(y) - ([0] * z + [1]))"
    pt_y = "(x * sin(y) - ([2] * z + [3]))"

    sigma_pt_x = "sqrt("\
            "pow(z * [4], 2) + "\
            f"pow([5], 2) +"\
            "2 * z * [6])"
    sigma_pt_y = "sqrt("\
            "pow(z * [7], 2) + "\
            f"pow([8], 2) +"\
            "2 * z * [9])"

    pt_x_up = f"{pt_x} + {sigma_pt_x}"
    pt_x_dn = f"{pt_x} - {sigma_pt_x}"

    pt_y_up = f"{pt_y} + {sigma_pt_y}"
    pt_y_dn = f"{pt_y} - {sigma_pt_y}"

    pt_expression = (f"sqrt(pow({pt_x},2) + pow({pt_y},2))")
    phi_expression = (f"atan2({pt_y}, {pt_x})")

    pt_expression_xup = (f"sqrt(pow({pt_x_up},2) + pow({pt_y},2))")
    phi_expression_xup = (f"atan2({pt_y}, {pt_x_up})")
    pt_expression_xdn = (f"sqrt(pow({pt_x_dn},2) + pow({pt_y},2))")
    phi_expression_xdn = (f"atan2({pt_y}, {pt_x_dn})")

    pt_expression_yup = (f"sqrt(pow({pt_x},2) + pow({pt_y_up},2))")
    phi_expression_yup = (f"atan2({pt_y_up}, {pt_x})")
    pt_expression_ydn = (f"sqrt(pow({pt_x},2) + pow({pt_y_dn},2))")
    phi_expression_ydn = (f"atan2({pt_y_dn}, {pt_x})")


    expressions = {
        "pt": pt_expression,
        "phi": phi_expression,
        "pt_stat_xup": pt_expression_xup,
        "pt_stat_xdn": pt_expression_xdn,
        "pt_stat_yup": pt_expression_yup,
        "pt_stat_ydn": pt_expression_ydn,
        "phi_stat_xup": phi_expression_xup,
        "phi_stat_xdn": phi_expression_xdn,
        "phi_stat_yup": phi_expression_yup,
        "phi_stat_ydn": phi_expression_ydn,
    }

    return expressions


def formula_object(paramsx, paramsy, expr):
    # last layer of correctionlib object

    for component, parameters in (("x", paramsx), ("y", paramsy)):
        required = ("m", "c", "m_stat", "c_stat", "covariance")
        values = [parameters[key] for key in required]
        if not all(math.isfinite(value) for value in values):
            raise ValueError(
                f"The {component} fit contains non-finite parameters."
            )
        if parameters["m_stat"] < 0 or parameters["c_stat"] < 0:
            raise ValueError(
                f"The {component} fit contains a negative uncertainty."
            )
        determinant = (
            parameters["m_stat"]**2 * parameters["c_stat"]**2
            - parameters["covariance"]**2
        )
        tolerance = 1e-10 * max(
            parameters["m_stat"]**2 * parameters["c_stat"]**2,
            parameters["covariance"]**2,
            1e-30,
        )
        if determinant < -tolerance:
            raise ValueError(
                f"The {component} fit covariance is not positive semidefinite."
            )

    formula = cs.Formula(
        nodetype="formula",
        expression=expr,
        parameters=[
            paramsx["m"],
            paramsx["c"],
            paramsy["m"],
            paramsy["c"],
            paramsx["m_stat"],
            paramsx["c_stat"],
            paramsx["covariance"],
            paramsy["m_stat"],
            paramsy["c_stat"],
            paramsy["covariance"]
        ],
        parser='TFormula',
        variables=["met_pt", "met_phi", "npvGood"],
    )

    return formula


def make_correction_with_formula(corr_dir, year, datamc, mets):
    """
    Create a correctionlib json file with corrections.
    
    Args:
        comb_dict (dict): output dictionary from previous step
        corr_dir (str): correction directory
        year (str): year
    """

    logger.info("Setting up clib file.")

    h = 'met_xy_corrections'
    description = 'Apply MET xy corrections to PuppiMET or MET'

    # define different formulae
    expressions = formula_expressions()

    # Loop over the categories to fill the correction content
    dtmc_content = []
    for dtmc in datamc:

        # Load corresponding correction file
        with open(f'{corr_dir}{dtmc}.json', 'r') as f:
            tmp_dict = json.load(f)

        met_content = []
        for met in mets:

            # get correction for met type
            params = tmp_dict[met]['PV_npvsGood'] #hard coded for now. Might use different pileups in the future

            content = []
            for exp in expressions:

                # get different statistical variations of met pt and phi

                formula = formula_object(
                    params["_x"]["nom"],
                    params["_y"]["nom"],
                    expressions[exp]
                )
                content.append({"key": exp, "value": formula})

                # for mc get also pileupweight variations (w/o stat)
                if (not 'stat' in exp) and (dtmc=='MC'):

                    for vrt in ['pu_up', 'pu_dn']:
                        formula = formula_object(
                            params["_x"][vrt],
                            params["_y"][vrt],
                            expressions[exp]
                        )
                        content.append({"key": f'{exp}_{vrt}', "value": formula})


            # Build the epoch content
            met_content.append(
                {"key": met, "value": cs.Category(
                    nodetype="category",
                    input='pt_phi',
                    content=content
                )}
            )

        # Build the dtmc content with the variation category
        dtmc_content.append(
            {"key": dtmc, "value": cs.Category(
                nodetype="category",
                input='met_type',
                content=met_content
            )}
        )


    # Define the correction using correctionlib schema
    correction = cs.Correction(
        name=h,
        description=description,
        version=1,
        inputs=[
            cs.Variable(name='pt_phi', type='string'),     # variable / variation
            cs.Variable(name='met_type', type='string'),     # MET type (MET or PuppiMET)
            cs.Variable(name='dtmc', type='string'),     # DATA or MC
            cs.Variable(name='met_pt', type='real'),     # met_pt (x)
            cs.Variable(name='met_phi', type='real'),    # met_phi (y)
            cs.Variable(name='npvGood', type='real')     # npvGood (z)
        ],
        output=cs.Variable(name='pt_corr', type='real'), # Corrected pt
        data=cs.Category(
            nodetype="category",
            input='dtmc',
            content=dtmc_content
        )
    )

    cset = cs.CorrectionSet(
        schema_version=2,
        corrections=[correction],
        description="Description"
    )

    path = corr_dir.replace(f'{year}/', f'schemaV2_{year}.json')

    with open(path, 'w') as fout:
        if hasattr(cset, "model_dump_json"):
            serialized = cset.model_dump_json(exclude_unset=True, indent=4)
        else:
            serialized = cset.json(exclude_unset=True, indent=4)
        fout.write(serialized)

    logger.info(f'Saved clib file in {path}')

    return
