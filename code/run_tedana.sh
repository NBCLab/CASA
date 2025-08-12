#!/bin/bash
#SBATCH --job-name=tedana
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32gb
#SBATCH --account=iacc_nbc
#SBATCH --qos=pq_nbc
#SBATCH --partition=IB_40C_512G
#SBATCH --time=02:00:00
#SBATCH --output=/home/data/nbc/Laird_CASA/code/log/%x/%x_%A.out
#SBATCH --error=/home/data/nbc/Laird_CASA/code/log/%x/%x_%A.err
#SBATCH --export=NONE  # Prevent importing login shell env → avoids PATH_modshare warnings

set -euo pipefail
pwd; hostname; date

# Max # CPUs = 360, lets take 300 -> 12 participants
# sbatch --array=1 run_tedana.sh, "to check that everything is fine"
# sbatch --array=2-12%6 run_tedana.sh
THISJOBVALUE=${SLURM_ARRAY_TASK_ID}

#--------------------------------------------------
# Conda activation (batch-safe)
#--------------------------------------------------
export PS1=""  # Avoid PS1 unbound variable error in non-interactive shells

CONDA_SH="/home/applications/spack/applications/gcc-8.2.0/miniconda3-4.5.11-oqs2mbgv3mmo3dll2f2rbxt4plfgyqzv/etc/profile.d/conda.sh"
if [ -f "$CONDA_SH" ]; then
    # shellcheck source=/dev/null
    source "$CONDA_SH"
    conda activate /home/data/nbc/Laird_CASA/casa-env
else
    echo "FATAL: conda.sh not found at $CONDA_SH" >&2
    exit 1
fi

# Sanity check environment
python -c "import tedana, sys; print('Python:', sys.executable); print('tedana:', tedana.__version__)"

#--------------------------------------------------
# Paths
#--------------------------------------------------
DSET_DIR="/home/data/nbc/Laird_CASA"
BIDS_DIR="${DSET_DIR}/dset"
CODE_DIR="${DSET_DIR}/code"
DERIVS_DIR="${BIDS_DIR}/derivatives"

fmriprep_ver=24.1.1
tedana_ver=0.0.13

FMRIPREP_DIR="${DERIVS_DIR}/fmriprep-${fmriprep_ver}"
TEDANA_DIR="${DERIVS_DIR}/tedana-${tedana_ver}"

mkdir -p "${TEDANA_DIR}"
mkdir -p "${CODE_DIR}/log/${SLURM_JOB_NAME}"
mkdir -p "${CODE_DIR}/jobs/${SLURM_JOB_NAME}"

# Parse the participants.tsv file and extract one subject ID from the line corresponding to this SLURM task.
subject=$( sed -n -E "$((${THISJOBVALUE} + 1))s/sub-(\S*)\>.*/\1/gp" ${BIDS_DIR}/participants.tsv )
echo "Processing subject: sub-${subject}"

#--------------------------------------------------
# Build + run command
#--------------------------------------------------
analysis="python ${CODE_DIR}/tedana_job.py \
  --subject sub-${subject} \
  --sessions ses-01 \
  --fmriprep_dir ${FMRIPREP_DIR} \
  --output_dir ${TEDANA_DIR} \
  --n_cores ${SLURM_CPUS_PER_TASK}"

echo
echo "=========================================="
echo "Subject:        sub-${subject}"
echo "Input (fMRIPrep): ${FMRIPREP_DIR}"
echo "Output (tedana):  ${TEDANA_DIR}"
echo "CPUs:             ${SLURM_CPUS_PER_TASK}"
echo "=========================================="
echo
echo "Commandline:"
echo "${analysis}"
echo

set +e
eval ${analysis}
exitcode=$?
set -e

#--------------------------------------------------
# Log result to TSV
#--------------------------------------------------
echo -e "sub-${subject}\tNA\tNA\t${exitcode}\t$(date)" \
  >> "${CODE_DIR}/jobs/${SLURM_JOB_NAME}/${SLURM_JOB_NAME}.${SLURM_JOB_ID}.tsv"

#--------------------------------------------------
# Check outputs
#--------------------------------------------------
if [[ ${exitcode} -eq 0 ]]; then
  echo "SUCCESS: tedana completed for sub-${subject}"
  out_dir="${TEDANA_DIR}/sub-${subject}/ses-01/func"
  if [[ -d "${out_dir}" ]]; then
    echo "Key outputs (if present):"
    ls -la "${out_dir}"/*desc-optcomDenoised_bold.nii.gz 2>/dev/null || echo "  - Denoised data: not found"
    ls -la "${out_dir}"/sub-"${subject}"_ses-01_task-*_*_report/tedana_report.html 2>/dev/null || echo "  - HTML report: not found"
  fi
else
  echo "FAILED: tedana for sub-${subject} with exit code ${exitcode}"
fi

echo "Finished sub-${subject} with exit code ${exitcode}"
date
exit ${exitcode}
