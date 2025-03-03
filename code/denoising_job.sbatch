#!/bin/bash
#SBATCH --job-name=denoising
#SBATCH --time=24:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=8gb
#SBATCH --account=iacc_nbc
#SBATCH --qos=pq_nbc
#SBATCH --partition=IB_40C_512G
# Outputs ----------------------------------
#SBATCH --output=/home/data/nbc/Laird_ABIDE/code/log/%x/%x_%A-%a.out
#SBATCH --error=/home/data/nbc/Laird_ABIDE/code/log/%x/%x_%A-%a.err
# ------------------------------------------

################ needs to be modified ##############
set -e

pwd; hostname; date
# 38g-per-core
#==============Shell script==============#
#Load the software needed
# source /home/data/abcd/code/abcd_fmriprep-analysis/env/environment
module load singularity-3.8.2

DATA_DIR="/home/data/nbc/Laird_ABIDE"
BIDS_DIR=${DATA_DIR}/dset
CODE_DIR=${DATA_DIR}/code
DERIVS_DIR="${BIDS_DIR}/derivatives"
IMG_DIR="/home/data/cis/singularity-images"

mriqc_ver=23.1.0
fmriprep_ver=23.1.3
afni_ver=22.0.20
MRIQC_DIR="${DERIVS_DIR}/mriqc-${mriqc_ver}"
FMRIPREP_DIR="${DERIVS_DIR}/fmriprep-${fmriprep_ver}"
CLEAN_DIR="${DERIVS_DIR}/denoising-${afni_ver}"
mkdir -p ${CLEAN_DIR}

# Max # CPUs = 360, lets take 300 -> 38 participants
# sbatch --array=1 denoising_job.sbatch, "to check that everything is fine"
# sbatch --array=2-1000%38 denoising_job.sbatch
# THISJOBVALUE=${SLURM_ARRAY_TASK_ID}

# Use for array > 1000 elements uncomment the following two lines and comment the previous line
# sbatch --array=1-1000%38 denoising_job.sbatch
# VALUES=({1000..2000})
# sbatch --array=1-156 denoising_job.sbatch
VALUES=({2000..2156})
THISJOBVALUE=${VALUES[${SLURM_ARRAY_TASK_ID}]}

# Parse the participants.tsv file and extract one subject ID from the line corresponding to this SLURM task.
subject=$( sed -n -E "$((${THISJOBVALUE} + 1))s/sub-(\S*)\>.*/\1/gp" ${BIDS_DIR}/participants.tsv )

DM_SCANS=5 

FD_THR=0.35
desc_clean="aCompCorCens"
desc_sm="aCompCorSM6Cens"
space="MNI152NLin2009cAsym"
# Run denoising pipeline
SHELL_CMD="singularity exec --cleanenv \
    -B ${CODE_DIR}:/code \
    -B ${MRIQC_DIR}:/mriqc \
    -B ${FMRIPREP_DIR}:/fmriprep \
    -B ${CLEAN_DIR}:/clean \
    $IMG_DIR/afni-${afni_ver}.sif"

# modification: had to remove session
denoising="${SHELL_CMD} python /code/denoising.py \
    --mriqc_dir /mriqc \
    --preproc_dir /fmriprep \
    --clean_dir /clean \
    --subject sub-${subject} \
    --space ${space} \
    --fd_thresh ${FD_THR} \
    --dummy_scans ${DM_SCANS} \
    --desc_list ${desc_clean} ${desc_sm} \
    --n_jobs ${SLURM_CPUS_PER_TASK}"

# Setup done, run the command
echo
echo Commandline: $denoising
eval $denoising 
exitcode=$?

# Output results to a table
echo "sub-$subject   ${THISJOBVALUE}    $exitcode" \
      >> ${CODE_DIR}/log/${SLURM_JOB_NAME}.${SLURM_ARRAY_JOB_ID}.tsv
echo Finished tasks ${THISJOBVALUE} with exit code $exitcode

date
exit $exitcode