#!/usr/bin/env bash
# submit_mind.sh
#
# Leave this file untouched between runs. Edit mind_run_configuration.sh
# instead, and submit via launch_mind.sh (not `sbatch submit_mind.sh`) directly
# this file has no #SBATCH lines; SLURM settings are passed
# in as CLI flags by launch_mind.sh).
# launch as:
# bash launch_mind.sh

set -euo pipefail
SECONDS=0

# script_dir is inherited from launch_mind.sh via --export=ALL,script_dir=...
# (NOT re-derived from SLURM_SUBMIT_DIR, which reflects the directory the
# job was submitted *from*, not where these scripts and subject_list.txt
# actually live -- those can differ).
source "${script_dir}/mind_run_configuration.sh"

mkdir -p logs

# Per-array-task subject lookup. This runs here (not in
# mind_run_configuration.sh) because SLURM_ARRAY_TASK_ID is only set once
# a task is actually scheduled on a compute node -- sourcing this same
# logic from launch_mind.sh, before sbatch has even run, would find no
# array task ID and fail before submission.
sublist="${script_dir}/subject_list.txt"
export subject=$(sed -n "${SLURM_ARRAY_TASK_ID}p" "$sublist")

if [ -z "$subject" ]; then
    echo "ERROR: No subject found for array task $SLURM_ARRAY_TASK_ID"
    exit 1
fi

echo "Running subject: $subject (array task $SLURM_ARRAY_TASK_ID)"

#! Optionally modify the environment seen by the application
#! (note that SLURM reproduces the environment at submission irrespective of ~/.bashrc):
. /etc/profile.d/modules.sh                # Leave this line (enables the module command)
module purge                               # Removes all modules still loaded
module load rhel8/default-icl              # REQUIRED - loads the basic environment
module load freesurfer/7.4.1               # load surf2surf for the fsaverage6 conversion
echo "FREESURFER_HOME=$FREESURFER_HOME"

source "$scratch_path"/.venv/bin/activate

export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1

cd "$scratch_path"

export FS_LICENSE="$scratch_path"/license.txt

START_TIME=$(date +%s)

/usr/bin/time -v ./.venv/bin/python ./MIND_pipeline_2026.py \
    --subject="$subject" \
    --data_dir="$data_dir" \
    --out_dir="$out_dir" \
    --projectname="$projectname" \
    --parcellation="$parcellation" \
    --feature_list_to_use="$feature_list_to_use" \
    --space="$space" \
    --"$micro" \
    --"$resample" \
    --"$return_qc" \
    --"$create_files" \
    --"$test_mode"

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))
echo "Python script runtime: $ELAPSED seconds ($((ELAPSED/60)) min $((ELAPSED%60)) sec)"
echo "Job finished at $(date)"
echo "Total runtime: $SECONDS seconds ($((SECONDS/60)) min $((SECONDS%60)) sec)"
