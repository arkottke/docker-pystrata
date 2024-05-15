import sys
import os
import pystrata
import dill

import numpy as np

from pathlib import Path


if len(sys.argv) > 1:
    name_profile, name_motion = sys.argv[1:]
else:
    name_profile = os.environ["PROFILE"]
    name_motion = os.environ["MOTION"]

print(f"Running analysis for profile '{name_profile}' and motion '{name_motion}'")


def load_motion(fpath):
    """Create motion from dill dictionary."""
    with fpath.open("rb") as fp:
        d = dill.load(fp)

    return pystrata.motion.RvtMotion(
        d["freqs"], d["fourier_amps"], duration=d["duration"]
    )


# Load the motions. One or many
motions = dict()
path_motions = Path("motions")
if "*" in name_motion:
    motions = {
        fpath.name: load_motion(fpath) for fpath in path_motions.glob(name_motion)
    }
else:
    motions[name_motion] = load_motion(path_motions / name_motion)


# Load the profiles
path_profiles = Path("profiles")
with (path_profiles / name_profile).open("rb") as fp:
    profiles = dill.load(fp)

# Configure the output
calc = pystrata.propagation.EquivalentLinearCalculator()
freqs = np.logspace(-1, 2, num=500)

outputs = pystrata.output.OutputCollection(
    [
        pystrata.output.ResponseSpectrumOutput(
            # Frequency
            freqs,
            # Location of the output
            pystrata.output.OutputLocation("outcrop", index=0),
            # Damping
            0.05,
        ),
        pystrata.output.ResponseSpectrumRatioOutput(
            # Frequency
            freqs,
            # Location in (denominator),
            pystrata.output.OutputLocation("outcrop", index=-1),
            # Location out (numerator)
            pystrata.output.OutputLocation("outcrop", index=0),
            # Damping
            0.05,
        ),
        pystrata.output.InitialVelProfile(),
        pystrata.output.MaxAccelProfile(),
    ]
)

# Do the calculation
for name_motion, motion in motions.items():
    print(f"Running motion: {name_motion}")
    # Clear all of the outputs
    outputs.reset()

    for i, p in enumerate(profiles):
        p = p.auto_discretize()
        name = (name_motion, name_profile, f"r{i}")
        calc(motion, p, p.location("outcrop", index=-1))
        outputs(calc, name=name)

    # Save all of the outputs
    fpath_output = Path(f"output/{name_profile}/{name_motion}")
    if not fpath_output.exists():
        fpath_output.mkdir(parents=True)

    with (fpath_output / "output.pkl").open("wb") as fp:
        dill.dump(outputs, fp)

    # Create a CSV of the surface
    df = outputs[0].to_dataframe()
    df.to_csv(fpath_output / "response_spectrum-surf.csv.gz")
