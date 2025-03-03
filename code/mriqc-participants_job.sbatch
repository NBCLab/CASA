#!/bin/bash
#SBATCH --job-name=mriqc
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem-per-cpu=4gb
#SBATCH --account=iacc_nbc
#SBATCH --qos=pq_nbc
#SBATCH --partition=IB_40C_512G
# Outputs ----------------------------------
#SBATCH --output=/home/data/nbc/Laird_CASA/code/log/%x/%x_%A-%a.out
#SBATCH --error=/home/data/nbc/Laird_CASA/code/log/%x/%x_%A-%a.err
# ------------------------------------------

pwd; hostname; date
set -e

# Max # CPUs = 360, lets take 300 -> 12 participants
# sbatch --array=1 mriqc-participants_job.sbatch, "to check that everything is fine"
# sbatch --array=2-12%6 mriqc-participants_job.sbatch
THISJOBVALUE=${SLURM_ARRAY_TASK_ID}

#==============Shell script==============#
#Load the software needed
module load singularity-3.8.2

mriqc_version=24.0.2
DATA_DIR="/home/data/nbc/Laird_CASA"
BIDS_DIR=${DATA_DIR}/dset
CODE_DIR=${DATA_DIR}/code
DERIVS_DIR="${BIDS_DIR}/derivatives/mriqc-${mriqc_version}"
IMG_DIR="/home/data/cis/singularity-images"

# Parse the participants.tsv file and extract one subject ID from the line corresponding to this SLURM task.
subject=$( sed -n -E "$((${THISJOBVALUE} + 1))s/sub-(\S*)\>.*/\1/gp" ${BIDS_DIR}/participants.tsv )

SCRATCH_DIR="/scratch/nbc/champ007/Laird_CASA/mriqc-${mriqc_version}/${subject}"
TEMPLATEFLOW_HOST_HOME="/home/data/cis/templateflow"
mkdir -p ${DERIVS_DIR}
mkdir -p ${SCRATCH_DIR}

# Designate a templateflow bind-mount point
# prevents workflow from downloading the templateflow
export SINGULARITYENV_TEMPLATEFLOW_HOME=${TEMPLATEFLOW_HOST_HOME}

SINGULARITY_CMD="singularity run --cleanenv \
      -B $BIDS_DIR:/data \
      -B ${DERIVS_DIR}:/out \
      -B ${TEMPLATEFLOW_HOST_HOME}:${SINGULARITYENV_TEMPLATEFLOW_HOME} \
      -B ${SCRATCH_DIR}:/work \
      ${IMG_DIR}/poldracklab_mriqc-${mriqc_version}.sif"

# Compose the command line
mem_gb=`echo "${SLURM_MEM_PER_CPU} * ${SLURM_CPUS_PER_TASK} / 1024" | bc`
cmd="${SINGULARITY_CMD} /data \
      /out \
      participant \
      --participant-label ${subject} \
      --no-sub \
      --verbose-reports \
      -w /work \
      --ants-nthreads ${SLURM_CPUS_PER_TASK} \
      --n_procs ${SLURM_CPUS_PER_TASK} \
      --mem_gb ${mem_gb}"

echo Running MRIQC for ${subject}
echo Commandline: $cmd
eval $cmd

# Output results to a table
echo "sub-$subject   ${THISJOBVALUE}    $exitcode" \
      >> ${DERIVS_DIR}/logs/${SLURM_JOB_NAME}.${SLURM_ARRAY_JOB_ID}.tsv
echo Finished tasks ${THISJOBVALUE} with exit code $exitcode
rm -r ${SCRATCH_DIR}
date

exit $exitcode
