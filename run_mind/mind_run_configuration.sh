#!/usr/bin/env bash
# mind_run_configuration.sh
#
# EDIT THIS FILE for every custom run. The SLURM submission script sources it and stays untouched.

# SLURM confirguration

export scratch_path="your/scratch/directory/path/here"
export email="your@email.ac.uk"
export account=YOURACCOUNT
export partition=PARTITION
export job_name="your_job_name_here"

# subject list file

export subject_list_filename="subject_list.txt"

# MIND arguments

export data_dir="your/data/directory/path/here"
export out_dir="path/where/you/plan/to/save/mind/networks"
export projectname="PROJECTNAME"
export parcellation="aparc" # "500_sym.aparc" "HCP.coarse.fsaverage.aparc" "HCP.fsaverage.aparc"
export feature_list_to_use="['FA', 'MD', 'ICVF', 'ISOVF', 'OD', 'CT', 'MC', 'Vol', 'SD', 'SA']"
export space="native" # "fsaverage6"
export micro="micro" # "no-micro"
export resample="no-resample" # "resample"
export return_qc="return_qc" # "no-return_qc"
export create_files="create_files" # "no-create_files"
export test_mode="no-test_mode" # test_mode

