#!/usr/bin/env bash
# launch_mind.sh
#
# Run this script to submit the job, do NOT sbatch submit_mind.sh directly.
# All SLURM settings (account, partition, job name, email) and MIND
# arguments are read from mind_run_configuration.sh. Edit that file only;
# this launcher and submit_mind.sh should stay untouched between runs.

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${script_dir}/mind_run_configuration.sh"

mkdir -p "${script_dir}/logs"

# Array size is derived from subject_list.txt so it always matches the
# current subject list, without needing to edit this file when the list
# changes. sublist here mirrors the path submit_mind.sh resolves
# internally (relative to script_dir, passed through via --export below).
sublist="${script_dir}/${subject_list_filename}"
n_subs=$(wc -l < "$sublist")

# script_dir is passed through explicitly rather than relying on
# SLURM_SUBMIT_DIR downstream, since SLURM_SUBMIT_DIR reflects whatever
# directory this script happened to be *run* from, not where the scripts
# themselves live -- those can differ (e.g. launched via a full path from
# elsewhere), which would break the subject_list.txt / config lookups in
# submit_mind.sh. --export=ALL keeps the rest of the current environment
# too (needed since scratch_path etc. are already exported above).
sbatch \
    --account="$account" \
    --partition="$partition" \
    --job-name="$job_name" \
    --output=logs/"$job_name"_%j.out \
    --error=logs/"$job_name"_%j.err \
    --time=00:10:00 \
    --cpus-per-task=8 \
    --mem=10G \
    --nodes=1 \
    --ntasks=1 \
    --mail-user="$email" \
    --mail-type=END,FAIL \
    --chdir="$scratch_path" \
    --export=ALL,script_dir="$script_dir" \
    --array=1-"$n_subs" \
    "${script_dir}/submit_mind.sh"