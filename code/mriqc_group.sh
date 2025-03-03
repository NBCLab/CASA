#!/bin/bash
#SBATCH --job-name=mriqc
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

# modified from Julio's ABIDE analysis workflow 

set -e

pwd; hostname; date

module load singularity-3.8.2

mriqc_version=24.0.2
DATA_DIR="/home/data/nbc/Laird_CASA"
BIDS_DIR=${DATA_DIR}/dset
CODE_DIR=${DATA_DIR}/code
DERIVS_DIR="${BIDS_DIR}/derivatives/mriqc-${mriqc_version}"
SCRATCH_DIR="/scratch/nbc/champ007/Laird_CASA/mriqc"
IMG_DIR="/home/data/cis/singularity-images"
mkdir -p ${SCRATCH_DIR}

SINGULARITY_CMD="singularity run --cleanenv \
      -B ${BIDS_DIR}:/data \
      -B ${DERIVS_DIR}:/out \
      -B ${CODE_DIR}:/code \
      -B ${SCRATCH_DIR}:/work \
      ${IMG_DIR}/poldracklab_mriqc-${mriqc_version}.sif"

# Compose the command line
mem_gb=`echo "${SLURM_MEM_PER_CPU} * ${SLURM_CPUS_PER_TASK} / 1024" | bc`
cmd="${SINGULARITY_CMD} /data \
      /out \
      group \
      --no-sub \
      --verbose-reports \
      --ants-nthreads ${SLURM_CPUS_PER_TASK} \
      --n_procs ${SLURM_CPUS_PER_TASK} \
      --mem_gb ${mem_gb}"

# -w /work \
echo Running MRIQC for ${subject}
echo Commandline: $cmd
eval $cmd

rm -rf ${SCRATCH_DIR}

date 

exit 0

# Determine outliers
mriqc="${SINGULARITY_CMD} python /code/mriqc-group.py --data /out"
# Setup done, run the command
echo
echo Commandline: $mriqc
eval $mriqc
exitcode=$?

rm -rf ${SCRATCH_DIR}

date

