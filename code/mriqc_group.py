import argparse
import os.path as op
import numpy as np
import pandas as pd
import re

############################################# draft ##############################################
def _get_parser():
    parser = argparse.ArgumentParser(description="Get outliers from QC metrics")
    parser.add_argument(
        "--data",
        dest="data",
        required=True,
        help="Path to MRIQC derivatives",
    )
    return parser


def main(data):
    # Load group-level MRIQC metrics
    mriqc_group_df = pd.read_csv(op.join(data, "group_bold.tsv"), sep="\t")

    # Define the task names and expected runs
    task_runs = {
        "mist": ["run-01", "run-02"],
        "mpt": ["run-01", "run-02", "run-03", "run-04"],
        "sorpf": ["run-01", "run-02"],
        "rest": ["run-01", "run-02"],
    }

    # Functional QC metrics of interest
    qc_metrics = ["efc", "snr", "fd_mean", "tsnr"]

    # DataFrame to store all excluded runs
    all_excluded_runs = []

    # Process each task separately
    for task, runs in task_runs.items():
        task_df = mriqc_group_df[mriqc_group_df["bids_name"].str.contains(f"task-{task}")]

        if task_df.empty:
            print(f"No data found for task-{task}, skipping.")
            continue

        for qc_metric in qc_metrics:
            upper, lower = np.percentile(task_df[qc_metric].values, [99, 1])

            if qc_metric in ["efc", "fd_mean"]:
                run2exclude = task_df.loc[task_df[qc_metric].values > upper]
            elif qc_metric in ["snr", "tsnr"]:
                run2exclude = task_df.loc[task_df[qc_metric].values < lower]

            for _, row in run2exclude.iterrows():
                bids_name = row["bids_name"]  # e.g., "sub-001_task-mist_run-01_bold"

                # Extract subject, task, and run number
                match = re.search(r"(sub-\d+)_task-([a-zA-Z0-9]+)_run-(\d+)", bids_name)
                if match:
                    subject, task_name, run_number = match.groups()
                    formatted_run = f"run-{run_number}"

                    # Only include if the run is in the expected list
                    if formatted_run in runs:
                        formatted_entry = f"{subject}_task-{task_name}_{formatted_run}"
                        all_excluded_runs.append(formatted_entry)

    # Save to a single TSV file
    if all_excluded_runs:
        output_df = pd.DataFrame(all_excluded_runs, columns=["excluded_runs"])
        output_file = op.join(data, "runs_to_exclude.tsv")
        output_df.to_csv(output_file, sep="\t", index=False)
        print(f"Saved all excluded runs to {output_file}")
    else:
        print("No outliers detected across tasks.")


def _main(argv=None):
    option = _get_parser().parse_args(argv)
    kwargs = vars(option)
    main(**kwargs)


if __name__ == "__main__":
    _main()
