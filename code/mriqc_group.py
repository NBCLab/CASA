import argparse
import os.path as op
import numpy as np
import pandas as pd
import re


def _get_parser():
    parser = argparse.ArgumentParser(description="Get outliers from QC metrics")
    parser.add_argument(
        "--data",
        dest="data",
        required=True,
        help="Path to MRIQC derivatives",
    )
    return parser


def parse_bids_name(bids_name):
    """Extract BIDS components from bids_name string."""
    match = re.match(
        r"(sub-[^_]+)_(ses-[^_]+)_task-([^_]+)_(run-\d+)(?:_(echo-\d+))?_(bold|T1w|T2w)?",
        bids_name
    )
    if match:
        participant_id, session, task, run, echo, modality = match.groups()
        return {
            "participant_id": participant_id,
            "session": session,
            "task": task,
            "run": run,
            "echo": echo if echo else "",
            "modality": modality if modality else "",
            "bids_name": bids_name
        }
    else:
        return {
            "participant_id": "",
            "session": "",
            "task": "",
            "run": "",
            "echo": "",
            "modality": "",
            "bids_name": bids_name
        }


def check_fd_mean_exclusions(data_dir):
    """Check fd_mean > 0.35 across all MRIQC files and return bids_name to exclude"""
    excluded_runs = set()
    files_to_check = ["group_bold.tsv", "group_T1w.tsv", "group_T2w.tsv"]

    for filename in files_to_check:
        filepath = op.join(data_dir, filename)
        if not op.exists(filepath):
            print(f"Warning: {filename} not found, skipping fd_mean check.")
            continue

        try:
            df = pd.read_csv(filepath, sep="\t")
            if "fd_mean" not in df.columns:
                print(f"Warning: fd_mean column not found in {filename}, skipping.")
                continue

            high_fd_df = df[df["fd_mean"] > 0.35]
            print(f"Found {len(high_fd_df)} entries with fd_mean > 0.35 in {filename}")

            for _, row in high_fd_df.iterrows():
                bids_name = row.get("bids_name", "")
                excluded_runs.add(bids_name)
                print(f"  Excluding {bids_name} (fd_mean={row['fd_mean']:.3f}) from {filename}")

        except Exception as e:
            print(f"Error processing {filename}: {e}")
            continue

    return excluded_runs


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

    qc_metrics = ["efc", "snr", "fd_mean", "tsnr"]
    percentile_excluded = set()

    # Process each task separately for percentile-based exclusions
    for task, runs in task_runs.items():
        task_df = mriqc_group_df[mriqc_group_df["bids_name"].str.contains(f"task-{task}", na=False)]

        if task_df.empty:
            print(f"No data found for task-{task}, skipping.")
            continue

        for qc_metric in qc_metrics:
            vals = task_df[qc_metric].dropna().values
            if len(vals) == 0:
                continue

            upper, lower = np.percentile(vals, [99, 1])

            if qc_metric in ["efc", "fd_mean"]:
                run2exclude = task_df.loc[task_df[qc_metric] > upper]
            elif qc_metric in ["snr", "tsnr"]:
                run2exclude = task_df.loc[task_df[qc_metric] < lower]
            else:
                continue

            percentile_excluded.update(run2exclude["bids_name"].dropna().tolist())

    # fd_mean > 0.35 exclusions
    fd_excluded = check_fd_mean_exclusions(data)

    # Merge both exclusion sets
    all_excluded = sorted(percentile_excluded.union(fd_excluded))

    # Parse into columns
    organized_data = [parse_bids_name(name) for name in all_excluded]
    runs_df = pd.DataFrame(organized_data)
    runs_df.sort_values(by=["participant_id", "task", "run", "echo"], inplace=True)

    # Save combined output
    output_file = op.join(data, "exclude-runs.tsv")
    runs_df.to_csv(output_file, sep="\t", index=False)
    print(f"\nSaved {len(runs_df)} total excluded runs to {output_file}")


def _main(argv=None):
    option = _get_parser().parse_args(argv)
    kwargs = vars(option)
    main(**kwargs)


if __name__ == "__main__":
    _main()
