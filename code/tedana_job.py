#!/usr/bin/env python
import argparse
import itertools
import json
import os
import os.path as op
import shutil
import subprocess
from glob import glob

from nipype.interfaces.ants import ApplyTransforms


def _get_parser():
    parser = argparse.ArgumentParser(description="Run tedana in fMRIPrep derivatives")

    parser.add_argument("--subject", required=True,
                        help="Subject identifier, with the sub- prefix (e.g., sub-0001).")
    parser.add_argument("--sessions", nargs="+", default=[None],
                        help="Session identifiers with ses- prefix (e.g., ses-01). If omitted, auto-discover.")
    parser.add_argument("--tasks", nargs="+", default=[None],
                        help="Task names. If omitted, auto-discover.")
    parser.add_argument("--runs", nargs="+", default=[None],
                        help="Run labels (e.g., 01). If omitted, auto-discover.")
    # Friendly aliases
    parser.add_argument("--task", dest="tasks", nargs="+", help="Alias for --tasks")
    parser.add_argument("--run", dest="runs", nargs="+", help="Alias for --runs")

    parser.add_argument("--fmriprep_dir", required=True, help="Path to fMRIPrep derivatives")
    parser.add_argument("--output_dir", required=True, help="Path to tedana output base directory")
    parser.add_argument("--n_cores", default=4, type=int, help="Threads for ANTs ApplyTransforms")

    # Optional knobs (CLI-supported)
    parser.add_argument("--fittype", default="curvefit", choices=["curvefit", "loglin"],
                        help="T2* fitting method for optcomb.")
    parser.add_argument("--tedpca", default="kic",
                        help="Dimensionality estimation for tedana (e.g., kic/mdl/aic/none).")
    parser.add_argument("--verbose", action="store_true", help="More tedana printouts.")
    return parser


def _get_sessions(preproc_dir, subject):
    found = sorted(glob(op.join(preproc_dir, subject, "ses-*")))
    return [op.basename(x) for x in found] if found else [None]


def _get_tasks(preproc_dir, subject, sessions):
    pattern = (op.join(preproc_dir, subject, "ses-*", "func", "*_task-*_desc-confounds_timeseries.tsv")
               if sessions[0] is not None else
               op.join(preproc_dir, subject, "func", "*_task-*_desc-confounds_timeseries.tsv"))
    files = sorted(glob(pattern))
    return list({op.basename(x).split("_task-")[1].split("_")[0] for x in files}) if files else [None]


def _get_runs(preproc_dir, subject, sessions):
    pattern = (op.join(preproc_dir, subject, "ses-*", "func", "*_run-*_desc-confounds_timeseries.tsv")
               if sessions[0] is not None else
               op.join(preproc_dir, subject, "func", "*_run-*_desc-confounds_timeseries.tsv"))
    files = sorted(glob(pattern))
    return list({op.basename(x).split("_run-")[1].split("_")[0] for x in files}) if files else [None]


def _get_echos(preproc_files):
    echo_times = []
    for f in preproc_files:
        jf = f.replace(".nii.gz", ".json")
        with open(jf, "r") as jh:
            meta = json.load(jh)
        if "EchoTime" not in meta:
            raise KeyError(f"EchoTime not found in {jf}")
        echo_times.append(meta["EchoTime"])
    return echo_times


def _find_denoised_file(out_dir, prefix):
    """
    Try several naming patterns across tedana versions.
    Returns path or None.
    """
    patterns = [
        f"{prefix}_desc-optcomDenoised_bold.nii.gz",
        f"{prefix}_desc-denoised_bold.nii.gz",
        f"{prefix}_desc-MEICA_denoised_bold.nii.gz",
        f"{prefix}_desc-optcom_denoised_bold.nii.gz",
    ]
    for pat in patterns:
        cand = op.join(out_dir, pat)
        if op.isfile(cand):
            return cand
    # Last-chance wildcard search
    hits = glob(op.join(out_dir, f"{prefix}*denois*bold.nii.gz"))
    return hits[0] if hits else None


def _transform_scan2mni(sub, ses, task, run, denoised_img_scan, fmriprep_dir, tedana_dir, n_cores):
    func_dir = op.join(fmriprep_dir, sub, ses, "func") if ses else op.join(fmriprep_dir, sub, "func")
    anat_dir = op.join(fmriprep_dir, sub, ses, "anat") if ses else op.join(fmriprep_dir, sub, "anat")
    out_func = op.join(tedana_dir, sub, ses, "func") if ses else op.join(tedana_dir, sub, "func")

    run_label = f"_run-{run}" if run else ""
    ses_label = f"_{ses}" if ses else ""

    denoised_img_mni = op.join(
        out_func,
        f"{sub}{ses_label}_task-{task}{run_label}_space-MNI152NLin2009cAsym_desc-optcomDenoised_bold.nii.gz",
    )
    scan2t1w = op.join(
        func_dir,
        f"{sub}{ses_label}_task-{task}{run_label}_from-scanner_to-T1w_mode-image_xfm.txt",
    )
    t1w2mni_files = glob(
        op.join(anat_dir, f"{sub}{ses_label}*_from-T1w_to-MNI152NLin2009cAsym_mode-image_xfm.h5")
    )
    references = glob(
        op.join(anat_dir, f"{sub}{ses_label}_*space-MNI152NLin2009cAsym_*desc-preproc_T1w.nii.gz")
    )
    assert len(references) == 1, f"Expected 1 MNI reference, found {len(references)}"
    assert len(t1w2mni_files) == 1, f"Expected 1 T1w->MNI transform, found {len(t1w2mni_files)}"

    reference = references[0]
    t1w2mni = t1w2mni_files[0]

    at = ApplyTransforms()
    at.inputs.dimension = 3
    at.inputs.input_image_type = 3
    at.inputs.input_image = denoised_img_scan
    at.inputs.default_value = 0
    at.inputs.float = True
    at.inputs.interpolation = "LanczosWindowedSinc"
    at.inputs.output_image = denoised_img_mni
    at.inputs.reference_image = reference
    # antsApplyTransforms applies transforms in reverse order; this yields scan->T1w, then T1w->MNI
    at.inputs.transforms = [t1w2mni, scan2t1w]
    at.inputs.num_threads = int(n_cores)
    print(f"\t\t\t{at.cmdline}", flush=True)
    at.run()


def _organize_files(tedana_sub_func_dir, report_dir):
    """Move report, logs, and figures into a dedicated report folder."""
    os.makedirs(report_dir, exist_ok=True)

    maybes = [
        op.join(tedana_sub_func_dir, "tedana_report.html"),
        op.join(tedana_sub_func_dir, "report.txt"),
        op.join(tedana_sub_func_dir, "references.bib"),
    ]
    for p in maybes:
        if op.isfile(p):
            shutil.move(p, report_dir)

    for lf in glob(op.join(tedana_sub_func_dir, "tedana_*.tsv")):
        shutil.move(lf, report_dir)

    figdir = op.join(tedana_sub_func_dir, "figures")
    if op.isdir(figdir):
        shutil.move(figdir, report_dir)


def main(subject, sessions, tasks, runs, fmriprep_dir, output_dir, n_cores,
         fittype="curvefit", tedpca="kic", verbose=False):

    n_cores = int(n_cores)

    if sessions[0] is None:
        sessions = _get_sessions(fmriprep_dir, subject)
    if tasks[0] is None:
        tasks = _get_tasks(fmriprep_dir, subject, sessions)
    if runs[0] is None:
        runs = _get_runs(fmriprep_dir, subject, sessions)

    for session, task, run in itertools.product(sessions, tasks, runs):
        print(f"Processing {subject}, session: {session}, task: {task}, run: {run}...", flush=True)

        fprep_func = op.join(fmriprep_dir, subject, session, "func") if session else op.join(fmriprep_dir, subject, "func")
        out_func = op.join(output_dir, subject, session, "func") if session else op.join(output_dir, subject, "func")
        os.makedirs(out_func, exist_ok=True)

        run_label = f"_run-{run}" if run else ""
        ses_label = f"_{session}" if session else ""
        prefix = f"{subject}{ses_label}_task-{task}{run_label}_space-scan"

        preproc_files = sorted(
            glob(op.join(fprep_func, f"*task-{task}*{run_label}_echo-*_desc-preproc_bold.nii.gz"))
        )
        if not preproc_files:
            print(f"\tNo preproc files found for task={task}, run={run}. Skipping.", flush=True)
            continue

        echo_times = _get_echos(preproc_files)
        assert len(preproc_files) == len(echo_times), "Mismatch N echoes vs files."

        # --- Run tedana CLI: full pipeline including denoising ---
        denoised_img_scan = _find_denoised_file(out_func, prefix)
        if not denoised_img_scan:
            cmd = (["tedana", "-d"] + preproc_files +
                   ["-e"] + [str(e) for e in echo_times] +
                   ["--out-dir", out_func,
                    "--prefix", prefix,
                    "--fittype", fittype,
                    "--tedpca", tedpca])
            if verbose:
                cmd.append("--verbose")

            print("\t\tRunning:", " ".join(cmd), flush=True)
            subprocess.run(cmd, check=True)

            # Move report & figures out of the func dir into a dedicated report folder
            report_dir = op.join(out_func, f"{subject}{ses_label}_task-{task}{run_label}_report")
            _organize_files(out_func, report_dir)

            # Try to find the denoised file now
            denoised_img_scan = _find_denoised_file(out_func, prefix)

        if not denoised_img_scan:
            # Fall back to optcom if denoised not found (warn)
            fallback = op.join(out_func, f"{prefix}_desc-optcom_bold.nii.gz")
            if op.isfile(fallback):
                print("\tWARNING: could not find a denoised file; using optcom bold as fallback.", flush=True)
                denoised_img_scan = fallback
            else:
                print("\tERROR: no denoised or optcom file found; skipping transform.", flush=True)
                continue

        # --- Transform to MNI ---
        print("\tTransforming denoised/optcom to MNI…", flush=True)
        _transform_scan2mni(subject, session, task, run, denoised_img_scan, fmriprep_dir, output_dir, n_cores)


def _main(argv=None):
    args = _get_parser().parse_args(argv)
    kwargs = vars(args)
    main(**kwargs)


if __name__ == "__main__":
    _main()
