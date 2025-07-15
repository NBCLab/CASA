import argparse
import itertools
import json
import os
import os.path as op
import shutil
from glob import glob

from nipype.interfaces.ants import ApplyTransforms
from tedana.workflows import tedana_workflow


def _get_parser():
    parser = argparse.ArgumentParser(description="Run tedana in fmriprep derivatives")
    parser.add_argument(
        "--subject",
        dest="subject",
        required=True,
        help="Subject identifier, with the sub- prefix.",
    )
    parser.add_argument(
        "--sessions",
        dest="sessions",
        default=[None],
        required=False,
        nargs="+",
        help="Sessions identifier, with the ses- prefix.",
    )
    parser.add_argument(
        "--tasks",
        dest="tasks",
        default=[None],
        required=False,
        nargs="+",
        help="Task names",
    )
    parser.add_argument(
        "--runs",
        dest="runs",
        default=[None],
        required=False,
        nargs="+",
        help="Run names",
    )
    parser.add_argument(
        "--fmriprep_dir",
        dest="fmriprep_dir",
        required=True,
        help="Path to fMRIPrep directory",
    )
    parser.add_argument(
        "--output_dir",
        dest="output_dir",
        required=True,
        help="Path to output directory",
    )
    parser.add_argument(
        "--n_cores",
        dest="n_cores",
        default=4,
        required=False,
        help="CPUs",
    )
    return parser


def _get_sessions(preproc_dir, subject):
    temp_ses = sorted(glob(op.join(preproc_dir, subject, "ses-*")))
    if len(temp_ses) > 0:
        sessions = [op.basename(x) for x in temp_ses]
    else:
        sessions = [None]

    return sessions


def _get_tasks(preproc_dir, subject, sessions):
    if sessions[0] is not None:
        temp_tasks = sorted(
            glob(
                op.join(
                    preproc_dir,
                    subject,
                    "ses-*",
                    "func",
                    f"*_task-*_desc-confounds_timeseries.tsv",
                )
            )
        )
    else:
        temp_tasks = sorted(
            glob(
                op.join(
                    preproc_dir,
                    subject,
                    "func",
                    f"*_task-*_desc-confounds_timeseries.tsv",
                )
            )
        )

    if len(temp_tasks) > 0:
        tasks = list(
            set([op.basename(x).split("_task-")[1].split("_")[0] for x in temp_tasks])
        )
    else:
        tasks = [None]

    return tasks


def _get_runs(preproc_dir, subject, sessions):
    if sessions[0] is not None:
        temp_runs = sorted(
            glob(
                op.join(
                    preproc_dir,
                    subject,
                    "ses-*",
                    "func",
                    f"*_run-*_desc-confounds_timeseries.tsv",
                )
            )
        )
    else:
        temp_runs = sorted(
            glob(
                op.join(
                    preproc_dir, subject, "func", f"*_run-*_desc-confounds_timeseries"
                )
            )
        )

    if len(temp_runs) > 0:
        runs = list(
            set([op.basename(x).split("_run-")[1].split("_")[0] for x in temp_runs])
        )
    else:
        runs = [None]

    return runs

def _get_echos(preproc_files):
    json_files = [file.replace(".nii.gz", ".json") for file in preproc_files]
    return [json.load(open(file))["EchoTime"] for file in json_files]


def _transform_scan2mni(sub, ses, task, run, denoised_img_scan, fmriprep_dir, tedana_dir, n_cores):
    fmriprep_sub_func_dir = (
        op.join(fmriprep_dir, sub, ses, "func")
        if ses
        else op.join(fmriprep_dir, sub, "func")
    )
    fmriprep_sub_anat_dir = (
        op.join(fmriprep_dir, sub, ses, "anat")
        if ses
        else op.join(fmriprep_dir, sub, "anat")
    )
    tedana_sub_func_dir = (
        op.join(tedana_dir, sub, ses, "func")
        if ses
        else op.join(tedana_dir, sub, "func")
    )
    run_label = f"_run-{run}" if run else ""
    ses_label = f"_{ses}" if ses else ""

    denoised_img_MNI = op.join(
        tedana_sub_func_dir,
        f"{sub}{ses_label}_task-{task}{run_label}_space-MNI152NLin2009cAsym_"
        "desc-optcomDenoised_bold.nii.gz",
    )
    scan2t1w = op.join(
        fmriprep_sub_func_dir,
        f"{sub}{ses_label}_task-{task}{run_label}_from-scanner_to-T1w_mode-image_xfm.txt",
    )
    tiw2mni_files = glob(
        op.join(
            fmriprep_sub_anat_dir,
            f"{sub}{ses_label}*_from-T1w_to-MNI152NLin2009cAsym_mode-image_xfm.h5",
        )
    )
    references = glob(
        op.join(
            fmriprep_sub_anat_dir,
            f"{sub}{ses_label}_*space-MNI152NLin2009cAsym_*desc-preproc_T1w.nii.gz",
        )
    )
    assert len(references) == 1
    assert len(tiw2mni_files) == 1
    reference = references[0]
    tiw2mni = tiw2mni_files[0]

    scan2mni = ApplyTransforms()
    scan2mni.inputs.dimension = 3
    scan2mni.inputs.input_image_type = 3
    scan2mni.inputs.input_image = denoised_img_scan
    scan2mni.inputs.default_value = 0
    scan2mni.inputs.float = True
    scan2mni.inputs.interpolation = "LanczosWindowedSinc"
    scan2mni.inputs.output_image = denoised_img_MNI
    scan2mni.inputs.reference_image = reference
    scan2mni.inputs.transforms = [tiw2mni, scan2t1w]
    scan2mni.inputs.num_threads = n_cores
    # scan2mni.inputs.verbose = True # Verbosity is not implemented in NiPY
    print(f"\t\t\t{scan2mni.cmdline}", flush=True)
    scan2mni.run()

def _organize_files(tedana_sub_func_dir, report_dir):
    """Organize maps and tables in folders.
    
    This is a temporary function to move the report's and log file to a directory
    named after the prefix argument, to prevent overwriting it when more than one 
    run or task is written to the same output directory
    """

    os.makedirs(report_dir, exist_ok=True)

    report_html_file = op.join(tedana_sub_func_dir, "tedana_report.html")
    report_file = op.join(tedana_sub_func_dir, "report.txt")
    ref_file = op.join(tedana_sub_func_dir, "references.bib")
    log_files = glob(op.join(tedana_sub_func_dir, "tedana_*.tsv"))
    figure_dir = op.join(tedana_sub_func_dir, "figures")

    [shutil.move(file_, report_dir) for file_ in [report_html_file, report_file, ref_file]]
    [shutil.move(file_, report_dir) for file_ in log_files]
    shutil.move(figure_dir, report_dir)

def main(
    subject,
    sessions,
    tasks,
    runs,
    fmriprep_dir,
    output_dir,
    n_cores,
):
    """Run tedana workflow on a given fMRIPrep derivatives."""
    n_cores = int(n_cores)  # Use this for parallelizing the for loop.

    if sessions[0] is None:
        sessions = _get_sessions(fmriprep_dir, subject)

    if tasks[0] is None:
        tasks = _get_tasks(fmriprep_dir, subject, sessions)
        # TODO: Check that task name is not None, task name is required

    if runs[0] is None:
        runs = _get_runs(fmriprep_dir, subject, sessions)

    for session, task, run in itertools.product(sessions, tasks, runs):
        print(
            f"Processing {subject}, session: {session}, task: {task}, run: {run}...",
            flush=True,
        )
        fmriprep_sub_func_dir = (
            op.join(fmriprep_dir, subject, session, "func")
            if session
            else op.join(fmriprep_dir, subject, "func")
        )
        tedana_sub_func_dir = (
            op.join(output_dir, subject, session, "func")
            if session
            else op.join(output_dir, subject, "func")
        )
        run_label = f"_run-{run}" if run else ""
        ses_label = f"_{session}" if session else ""

        # Collect important files
        preproc_files = sorted(
            glob(
                op.join(
                    fmriprep_sub_func_dir,
                    f"*task-{task}*{run_label}_echo-*_desc-preproc_bold.nii.gz",
                )
            )
        )
        echo_times = _get_echos(preproc_files)
        assert len(preproc_files) == len(echo_times)

        if len(preproc_files) > 0:
            os.makedirs(tedana_sub_func_dir, exist_ok=True)
        else:
            continue

        denoised_img_scan = op.join(
            tedana_sub_func_dir,
            f"{subject}{ses_label}_task-{task}{run_label}_space-scan_desc-optcomDenoised_"
            "bold.nii.gz",
        )
        if not op.isfile(denoised_img_scan):
            print(
                f"\tRunning tedana on {subject}, session: {session}, task: {task}, run: {run}...",
                flush=True,
            )
            print("\t\t" + "\n\t\t".join(preproc_files), flush=True)
            print("\t\t\t" + "\n\t\t\t".join([str(echo) for echo in echo_times]), flush=True)
            tedana_workflow(
                preproc_files,
                echo_times,
                out_dir=tedana_sub_func_dir,
                prefix=f"{subject}{ses_label}_task-{task}{run_label}_space-scan",
                fittype="curvefit",
                tedpca="kic",
                verbose=False,
            )
    
            report_dir = op.join(
                tedana_sub_func_dir, 
                f"{subject}{ses_label}_task-{task}{run_label}_report"
            )
            _organize_files(tedana_sub_func_dir, report_dir)
    
        print(
            f"\t\tTransforming denoised optimally combined time series to MNI...",
            flush=True,
        )
        _transform_scan2mni(
            subject, 
            session, 
            task, 
            run, 
            denoised_img_scan, 
            fmriprep_dir, 
            output_dir,
            n_cores,
        )


def _main(argv=None):
    option = _get_parser().parse_args(argv)
    kwargs = vars(option)
    main(**kwargs)


if __name__ == "__main__":
    _main()
