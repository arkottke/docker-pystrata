import itertools
import dill
import pyrvt

import numpy as np

from pathlib import Path


mags = [5, 6, 7]
dists = [10, 30, 80]

outpath = Path(__file__).parent / "../data/input/motions"

if not outpath.exists():
    outpath.mkdir(parents=True)


freqs = np.geomspace(0.05, 200, num=2048)

for mag, dist in itertools.product(mags, dists):
    mot = pyrvt.motions.StaffordEtAl22Motion(
        mag, dist_rup=dist, freqs=freqs, disable_site_amp=True
    )

    # Could also use JSON to store the motions
    d = {
        "freqs": mot.freqs,
        "fourier_amps": mot.fourier_amps,
        "duration": mot.duration,
    }
    name = f"m{mag:0.1f}-r{dist:0.0f}km".replace(".", "p") + ".pkl"
    with (outpath / name).open("wb") as fp:
        dill.dump(d, fp)
