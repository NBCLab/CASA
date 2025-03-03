"""Create events files for Stranger Things scans."""
"""needs to be modified""" 

from glob import glob
import os.path as op

import nibabel as nib
import pandas as pd
from moviepy.editor import VideoFileClip

IN_DIR = "/home/data/nbc/Laird_DIVA/dset/"
STIM_DIR = "/home/data/nbc/Laird_DIVA/stimuli/task_stimuli/stranger_things_mkv/"

strangerthings_scans = sorted(glob(op.join(
    IN_DIR,
    "sub-*/ses-*/func/*task-strangerthings*_echo-1_part-mag_bold.nii.gz",
)))
T_R = 1.5

for scan in strangerthings_scans:
    scan_dir = op.dirname(scan)
    scan_name = op.basename(scan)

    ses_number = [part for part in scan_dir.split("/") if part.startswith("ses-")][0]
    ses_number = ses_number.split("-")[1]

    episode_number = f"S01E{ses_number}"
    run_number = [part for part in scan_name.split("_") if part.startswith("run")][0]
    run_number = run_number.split("-")[1]

    scan_parts = scan_name.split("_")
    scan_parts = [part for part in scan_parts if not part.startswith(("part", "echo"))]
    events_file = "_".join(scan_parts)
    events_file = events_file.replace("_bold.nii.gz", "_events.tsv")

    img = nib.load(scan)
    n_vols = img.shape[3]
    fixation1_onset = 0
    fixation1_duration = 3
    film_onset = fixation1_duration
    vols_after_fixation = n_vols - 2

    stim_file = f"stranger_things/{episode_number}/{episode_number}R{run_number.zfill(2)}.mkv"

    # Determine film duration
    stim_path = op.join(STIM_DIR, episode_number, f"{episode_number}R{run_number.zfill(2)}.mkv")
    clip = VideoFileClip(stim_path)
    film_duration = clip.duration

    fixation2_duration = (vols_after_fixation * T_R) - film_duration
    fixation2_onset = fixation1_duration + film_duration

    df = pd.DataFrame(
        columns=["onset", "duration", "trial_type", "stim_file"],
        data=[
            [fixation1_onset, fixation1_duration, "fixation", "n/a"],
            [film_onset, film_duration, "fixation", stim_file],
            [fixation2_onset, fixation2_duration, "fixation", "n/a"],
        ]
    )
    out_file = op.join(scan_dir, events_file)
    df.to_csv(out_file, sep="\t", na_rep="n/a", index=False, line_terminator="\n", float_format="%.2f")