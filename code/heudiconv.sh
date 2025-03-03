#!/bin/bash
#SBATCH --job-name=heudiconv
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem-per-cpu=2gb
#SBATCH --account=iacc_nbc
#SBATCH --qos=pq_nbc
#SBATCH --partition=IB_40C_512G
# Outputs ----------------------------------
#SBATCH --output=/home/data/nbc/Laird_CASA/code/log/%x/%x_%A-%a.out
#SBATCH --error=/home/data/nbc/Laird_CASA/code/log/%x/%x_%A-%a.err
# ------------------------------------------

module load singularity-3.8.2

DATA_DIR="/home/data/nbc/Laird_CASA"
IMG_DIR="/home/data/cis/singularity-images"
BIDS_DIR="${DATA_DIR}/dset"
CODE_DIR="${DATA_DIR}/code"
RAW_DIR="${DATA_DIR}/sourcedata"

SINGULARITY_CMD="singularity run --cleanenv \
                    -B ${BIDS_DIR}:/output \
                    -B ${DATA_DIR}:/data \
                    $IMG_DIR/heudiconv_1.3.0.sif"

# Extract subject IDs and session numbers
subjs=()
sessions=()

# Collect subject and session info
for dir in ${RAW_DIR}/Laird_CASA-*; do
    base_name=$(basename "$dir")

    subj=$(echo "$base_name" | sed -E 's/Laird_CASA-([0-9]+)_S.*/\1/')
    sess=$(echo "$base_name" | sed -E 's/.*_S([0-9]+)/0\1/')

    # Add subjects to the list except 00009
    if [[ "$subj" != "00009" ]]; then
        subjs+=("$subj")
        sessions+=("$sess")
    fi
done

# Print the list of subjects
echo "Processing subjects: ${subjs[@]}"

for i in "${!subjs[@]}"; do
    subj="${subjs[$i]}"
    sess="${sessions[$i]}"

    echo "Running Heudiconv for sub-${subj}_${sess}"

    # Run Heudiconv command
    cmd="${SINGULARITY_CMD} -d /data/sourcedata/Laird_CASA-{subject}_S1/scans/*/DICOM/* \
        -s ${subj} \
        -ss ${sess} \
        -f /data/code/heuristic.py \
        -c dcm2niix \
        -o /output \
        --bids \
        --overwrite \
        --minmeta"

    # Run the command
    echo "Commandline: $cmd"
    eval $cmd
    exitcode=$?
    echo "Heudiconv finished for sub-${subj} (session ${sess}) with exit code $exitcode"

    if [ $exitcode -ne 0 ]; then
        echo "Warning: Heudiconv failed for sub-${subj} (session ${sess}) with exit code $exitcode"
    fi
done

exit
