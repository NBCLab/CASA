import argparse
import os.path as op
import numpy as np
import pandas as pd
import re

############################################# Enhanced MRIQC QC Script ##############################################

def _get_parser():
    parser = argparse.ArgumentParser(description="Get outliers from QC metrics")
    parser.add_argument(
        "--data",
        dest="data",
        required=True,
        help="Path to MRIQC derivatives",
    )
    return parser


def extract_subject_from_bids_name(bids_name):
    """Extract subject ID from BIDS name"""
    match = re.search(r"(sub-[^_]+)", bids_name)
    if match:
        return match.group(1)
    return None


def check_fd_mean_exclusions(data_dir):
    """Check fd_mean > 0.35 across all MRIQC files and return subjects to exclude"""
    excluded_subjects = set()
    
    # Files to check for fd_mean
    files_to_check = ["group_bold.tsv", "group_T1w.tsv", "group_T2w.tsv"]
    
    for filename in files_to_check:
        filepath = op.join(data_dir, filename)
        
        if not op.exists(filepath):
            print(f"Warning: {filename} not found, skipping fd_mean check for this file.")
            continue
            
        try:
            df = pd.read_csv(filepath, sep="\t")
            
            # Check if fd_mean column exists
            if "fd_mean" not in df.columns:
                print(f"Warning: fd_mean column not found in {filename}, skipping.")
                continue
                
            # Find rows where fd_mean > 0.35
            high_fd_mask = df["fd_mean"] > 0.35
            high_fd_df = df[high_fd_mask]
            
            print(f"Found {len(high_fd_df)} entries with fd_mean > 0.35 in {filename}")
            
            # Extract subjects from these entries
            for _, row in high_fd_df.iterrows():
                bids_name = row.get("bids_name", "")
                subject = extract_subject_from_bids_name(bids_name)
                if subject:
                    excluded_subjects.add(subject)
                    print(f"  Excluding {subject} (fd_mean={row['fd_mean']:.3f}) from {filename}")
                    
        except Exception as e:
            print(f"Error processing {filename}: {str(e)}")
            continue
    
    return list(excluded_subjects)


def main(data):
    print(f"Processing MRIQC data from: {data}")
    
    # Check if group_bold.tsv exists
    bold_file = op.join(data, "group_bold.tsv")
    if not op.exists(bold_file):
        print(f"Error: {bold_file} not found. Make sure MRIQC group analysis completed successfully.")
        return
    
    # Load group-level MRIQC metrics
    mriqc_group_df = pd.read_csv(bold_file, sep="\t")
    print(f"Loaded {len(mriqc_group_df)} entries from group_bold.tsv")

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

    print("\nProcessing percentile-based outlier detection for runs...")
    
    # Process each task separately
    for task, runs in task_runs.items():
        task_df = mriqc_group_df[mriqc_group_df["bids_name"].str.contains(f"task-{task}")]

        if task_df.empty:
            print(f"No data found for task-{task}, skipping.")
            continue
            
        print(f"Processing task-{task} ({len(task_df)} runs)...")

        for qc_metric in qc_metrics:
            if qc_metric not in task_df.columns:
                print(f"Warning: {qc_metric} column not found, skipping.")
                continue
                
            upper, lower = np.percentile(task_df[qc_metric].values, [99, 1])

            if qc_metric in ["efc", "fd_mean"]:
                run2exclude = task_df.loc[task_df[qc_metric].values > upper]
            elif qc_metric in ["snr", "tsnr"]:
                run2exclude = task_df.loc[task_df[qc_metric].values < lower]

            if not run2exclude.empty:
                print(f"  Found {len(run2exclude)} outliers for {qc_metric} (threshold: {upper if qc_metric in ['efc', 'fd_mean'] else lower:.3f})")

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
                        print(f"    Excluding: {formatted_entry} ({qc_metric}={row[qc_metric]:.3f})")

    # Save runs to exclude to a TSV file
    if all_excluded_runs:
        # Remove duplicates while preserving order
        unique_excluded_runs = list(dict.fromkeys(all_excluded_runs))
        output_df = pd.DataFrame(unique_excluded_runs, columns=["excluded_runs"])
        output_file = op.join(data, "runs_to_exclude.tsv")
        output_df.to_csv(output_file, sep="\t", index=False)
        print(f"\nSaved {len(unique_excluded_runs)} excluded runs to {output_file}")
    else:
        print("\nNo outliers detected across tasks for run exclusions.")

    # Check fd_mean > 0.35 across all MRIQC files for participant exclusions
    print("\n" + "="*60)
    print("Checking fd_mean > 0.35 for participant exclusions...")
    print("="*60)
    excluded_subjects = check_fd_mean_exclusions(data)
    
    if excluded_subjects:
        # Sort subjects for consistent output
        excluded_subjects.sort()
        # Save excluded participants to TSV file
        participants_df = pd.DataFrame(excluded_subjects, columns=["participant_id"])
        participants_output_file = op.join(data, "exclude-participants.tsv")
        participants_df.to_csv(participants_output_file, sep="\t", index=False)
        print(f"\nSaved {len(excluded_subjects)} excluded participants to {participants_output_file}")
        print(f"Excluded participants: {', '.join(excluded_subjects)}")
    else:
        print("No participants found with fd_mean > 0.35.")
        
    print("\nQuality control analysis completed successfully!")


def _main(argv=None):
    option = _get_parser().parse_args(argv)
    kwargs = vars(option)
    main(**kwargs)


if __name__ == "__main__":
    _main()