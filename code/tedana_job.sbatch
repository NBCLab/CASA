#!/bin/bash
#SBATCH --job-name=tedana
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=12
#SBATCH --mem-per-cpu=4gb
#SBATCH --account=iacc_nbc
#SBATCH --qos=pq_nbc
#SBATCH --partition=IB_40C_512G
# Outputs ----------------------------------
#SBATCH --output=/home/data/nbc/Laird_CASA/code/jobs/%x/%x_%A-%a.out
#SBATCH --error=/home/data/nbc/Laird_CASA/code/jobs/%x/%x_%A-%a.err
# ------------------------------------------
# Max # CPUs = 360
# modified from DIVA workflow
pwd; hostname; date
set -e

#==============Shell script==============#
#Load the software needed
module add miniconda3-4.5.11-gcc-8.2.0-oqs2mbg
module load ants-2.3.5

source /home/data/nbc/Laird_CASA/.venv/bin/activate

DSET_DIR="/home/data/nbc/Laird_DIVA"
BIDS_DIR="${DSET_DIR}/dset"
CODE_DIR="${DSET_DIR}/code"
DERIVS_DIR="${BIDS_DIR}/derivatives"

fmriprep_ver=24.1.1
tedana_ver=0.0.13
FMRIPREP_DIR="${DERIVS_DIR}/fmriprep-v${fmriprep_ver}"
TEDANA_DIR="${DERIVS_DIR}/tedana-v${tedana_ver}"

subject=$( sed -n -E "$((${SLURM_ARRAY_TASK_ID} + 1))s/sub-(\S*)\>.*/\1/gp" ${BIDS_DIR}/participants.tsv )

analysis="python ${CODE_DIR}/tedana_job.py \
    --subject sub-${subject} \
    --sessions ses-02 \
    --task rest \
    --run 1 \
    --fmriprep_dir ${FMRIPREP_DIR} \
    --output_dir ${TEDANA_DIR} \
    --n_cores ${SLURM_CPUS_PER_TASK}"

# Setup done, run the command
echo
echo Commandline: $analysis
eval $analysis 
exitcode=$?

# Output results to a table
echo "sub-$subject   ${SLURM_ARRAY_TASK_ID}    $exitcode" \
      >> ${CODE_DIR}/jobs/${SLURM_JOB_NAME}/${SLURM_JOB_NAME}.${SLURM_ARRAY_JOB_ID}.tsv
echo Finished tasks ${SLURM_ARRAY_TASK_ID} with exit code $exitcode
date

exit $exitcode