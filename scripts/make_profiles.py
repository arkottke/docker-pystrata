"""
Create a set of examples profiles
"""

import dill
import pystrata

from scipy.stats import lognorm

from pathlib import Path

outpath = Path("../data/profiles")

if not outpath.exists():
    outpath.mkdir(parents=True)

# Simple model for velocity varations
ln_std = 0.3
uncert = lognorm(ln_std)

# Model of aleatory variability
var_velocity = pystrata.variation.DepthDependToroVelVariation.generic_model("USGS C")
var_count = 60
var_soiltypes = pystrata.variation.SpidVariation(
    -0.5, std_mod_reduc=0.15, std_damping=0.30
)

for name, frac in (("lower", 0.05), ("middle", 0.50), ("upper", 0.95)):
    profile = pystrata.site.Profile(
        [
            pystrata.site.Layer(
                pystrata.site.DarendeliSoilType(
                    18.0, plas_index=0, ocr=1, stress_mean=100
                ),
                10,
                400 * uncert.ppf(frac),
            ),
            pystrata.site.Layer(
                pystrata.site.DarendeliSoilType(
                    18.0, plas_index=0, ocr=1, stress_mean=200
                ),
                10,
                450 * uncert.ppf(frac),
            ),
            pystrata.site.Layer(
                pystrata.site.DarendeliSoilType(
                    18.0, plas_index=0, ocr=1, stress_mean=400
                ),
                30,
                600 * uncert.ppf(frac),
            ),
            pystrata.site.Layer(
                pystrata.site.SoilType("Rock", 24.0, None, 0.01), 0, 1200
            ),
        ]
    )

    realizations = list(
        pystrata.variation.iter_varied_profiles(
            profile, var_count, var_velocity=var_velocity, var_soiltypes=var_soiltypes
        )
    )

    name = f"{name}.pkl"
    with (outpath / name).open("wb") as fp:
        dill.dump(realizations, fp)
