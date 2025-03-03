#!/bin/bash
#SBATCH --job-name=fmriprep
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=12
#SBATCH --mem-per-cpu=4gb
#SBATCH --account=iacc_nbc
#SBATCH --qos=pq_nbc
#SBATCH --partition=IB_40C_512G
# Outputs ----------------------------------
#SBATCH --output=/home/data/nbc/Laird_CASA/code/log/%x/%x_%A-%a.out
#SBATCH --error=/home/data/nbc/Laird_CASA/code/log/%x/%x_%A-%a.err
# ------------------------------------------
# Max # CPUs = 360
# modified from ABIDE workflow

set -e
pwd; hostname; date

# sbatch --array=1 fmriprep_job.sbatch, "to check that everything is fine"
# sbatch --array=2-12%6 fmriprep_job.sbatch #format to run multiple
THISJOBVALUE=${SLURM_ARRAY_TASK_ID}

module load singularity-3.8.2

fmriprep_version=24.1.1
DATA_DIR="/home/data/nbc/Laird_CASA"
BIDS_DIR=${DATA_DIR}/dset
CODE_DIR=${DATA_DIR}/code
DERIVS_DIR="${BIDS_DIR}/derivatives/fmriprep-${fmriprep_version}"
IMG_DIR="/home/data/cis/singularity-images"

# Parse the participants.tsv file and extract one subject ID from the line corresponding to this SLURM task.
subject=$( sed -n -E "$((${THISJOBVALUE} + 1))s/sub-(\S*)\>.*/\1/gp" ${BIDS_DIR}/participants.tsv )

SCRATCH_DIR="/scratch/nbc/champ007/Laird_CASA/fmriprep-${fmriprep_version}/${subject}"
mkdir -p ${DERIVS_DIR}
mkdir -p ${SCRATCH_DIR}

# Prepare some writeable bind-mount points.
TEMPLATEFLOW_HOST_HOME="/home/data/cis/templateflow"
FMRIPREP_HOST_CACHE=${HOME}/.cache/fmriprep
mkdir -p ${FMRIPREP_HOST_CACHE}

# Make sure FS_LICENSE is defined in the container.
FS_LICENSE="/home/champ007/Documents/freesurfer"

# Designate a templateflow bind-mount point
export SINGULARITYENV_TEMPLATEFLOW_HOME=${TEMPLATEFLOW_HOST_HOME}

SINGULARITY_CMD="singularity run --cleanenv \
      -B $BIDS_DIR:/data \
      -B ${DERIVS_DIR}:/out \
      -B ${TEMPLATEFLOW_HOST_HOME}:${SINGULARITYENV_TEMPLATEFLOW_HOME} \
      -B ${SCRATCH_DIR}:/work \
      -B ${FS_LICENSE}:/freesurfer \
      $IMG_DIR/poldracklab-fmriprep_${fmriprep_version}.sif"

# Compose the command line
mem_gb=`echo "${SLURM_MEM_PER_CPU} * ${SLURM_CPUS_PER_TASK} / 1024" | bc`
cmd="${SINGULARITY_CMD} /data \
      /out \
      participant \
      --participant-label $subject \
      -w /work/ \
      -vv \
      --omp-nthreads ${SLURM_CPUS_PER_TASK} \
      --nprocs ${SLURM_CPUS_PER_TASK} \
      --mem_mb ${mem_gb} \
      --me-output-echos \
      --output-spaces MNI152NLin2009cAsym:res-2 \
      --dummy-scans 5 \
      --return-all-components \
      --notrack \
      --use-syn-sdc \
      --fs-license-file /freesurfer/license.txt"

# Setup done, run the command
echo Running task fMRIPrep for ${subject}
echo Commandline: $cmd
eval $cmd
exitcode=$?

# Output results to a table
echo "sub-$subject   ${THISJOBVALUE}    $exitcode" \
      >> ${CODE_DIR}/log/${SLURM_JOB_NAME}.${SLURM_ARRAY_JOB_ID}.tsv
echo Finished tasks ${THISJOBVALUE} with exit code $exitcode
rm -r ${SCRATCH_DIR}
date
exit $exitcode
