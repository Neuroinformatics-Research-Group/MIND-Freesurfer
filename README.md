# UKB-MIND
*Scripts for running MIND on the whole of UKB structural imaging data*

## Introduction

The only baked in assumption with this pipeline is that your are working from the Cambridge CSD3 clusters and that you are using structural imaging data that has been preprocessed in Freesurfer. 

Assuming you have met those requirements then you are safe to copy the directory run_mind onto to your HPC scratch folder and start computing MIND networks. 

You will only need to make the following edits: 

- edit slurm, subjectlist, and python calls/arguments in mind_run_configuration.sh
- make sure you have your real license.txt Freesurfer file (the one in this directory is a dummy file)
- make sure you have a real subject_list.txt file with your subject EIDs (again, the one here is a dummy file that demonstrates how your subject EIDs should be stored in subject_list.txt).

## Python version required
Python 3.11.13

### Set up your python environment in your scratch directory from which you will launch the .sh scripts

$ cd rds/hpc-work/run_mind
$ python3.11 -m venv .venv
$ source .venv/bin/activate
$ pip install -r requirements.txt

## Parcellations
'aparc':                         'DK68'

'500_sym.aparc':                 'DK318'

'HCP.coarse.fsaverage.aparc':    'HCP46' _generated from the MIND networks informed graph metrics_

'HCP.fsaverage.aparc':           'HCP360'

## Directory Structure 

```bash

├── MIND-<projectname>
│   ├── networks
│   │   ├── subject specific folders (i.e., UKBXXXXX)
│   │   │  ├── features (i.e., CT_SA_SD_Vol_MC_FA_MD_ICVF_ISOVF_OD)
│   │   │  │   ├── parcelation
│   │   │  │   │   ├── native space
│   │   │  │   │   │  ├── QC
│   │   │  │   │   │  │  ├── roi_qc.csv (run once, all 10 features)
│   │   │  │   │   │  │  ├── global_qc.csv (run once, all 10 features)
│   │   │  │   │   │  ├── MIND
│   │   │  │   │   │  │  ├── raw MIND network (ie., UKBXXXXX_mind_raw.csv)
│   │   │  │   │   │  │  ├── PCA MIND network (ie., UKBXXXXX_mind_pca.csv)
│   │   │  │   │   ├── fsaverage6 space
│   │   │  │   │   │  ├── QC
│   │   │  │   │   │  │  ├── roi_qc.csv (run once, all 10 features)
│   │   │  │   │   │  │  ├── global_qc.csv (run once, all 10 features)
│   │   │  │   │   │  ├── MIND
│   │   │  │   │   │  │  ├── raw MIND network (ie., UKBXXXXX_mind_raw.csv)
│   │   │  │   │   │  │  ├── PCA MIND network (ie., UKBXXXXX_mind_pca.csv)
│   ├── stats
│   │   ├── features (i.e., CT_SA_SD_Vol_MC_FA_MD_ICVF_ISOVF_OD)
│   │   │  │   ├── QC
│   │   │  │   │   ├── parcelation
│   │   │  │   │   │  ├── native space
│   │   │  │   │   │  │  ├── roi_qc.csv (run once, all 10 features)
│   │   │  │   │   │  │  ├── global_qc.csv (run once, all 10 features)
│   │   │  │   │   │  ├── fsaverage6 space
│   │   │  │   │   │  │  ├── roi_qc.csv (run once, all 10 features)
│   │   │  │   │   │  │  ├── global_qc.csv (run once, all 10 features)
│   │   │  │   ├── PCA model weights
│   │   │  │   │   ├── Pickle file 1: standard scaler weights
│   │   │  │   │   ├── Pickle file 2: feature x PCA weights (matrix)
└──

```

## QC output

- the total number of vertices that have 0 as their value
- how many vertices == 0 per ROI
- total number of vertices that are more than 7 MADs after z-scoring the vertex level data
- same information by ROI
- the proportion of identical values (by total and by ROI)

