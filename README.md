# MIND-Freesurfer

*Scripts for running MIND on Freesurfer structural imaging data.*

---

## Introduction

This pipeline makes one baked-in assumption: you are working on the **CSD3 HPC cluster** with structural imaging data that has already been preprocessed in **Freesurfer**.

If you meet that requirement, you're ready to go:

1. Copy the `run_mind` directory into your scratch folder.
2. Start computing MIND networks.

### Before you run anything, edit the following

| File | What to change |
|---|---|
| `mind_run_configuration.sh` | SLURM settings, subject list path, and python call arguments |
| `license.txt` | Replace the dummy file with your **real** Freesurfer license |
| `subject_list.txt` | Replace the dummy file with your **real** subject EIDs (see the dummy file for the expected format) |

---

## Python Environment

**Required version:** Python `3.11.13`

Set up your environment in the scratch directory from which you'll launch the `.sh` scripts:

```bash
cd rds/hpc-work/run_mind
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## Parcellations

| Freesurfer parcellation | Alias |
|---|---|
| `aparc` | DK68 |
| `500_sym.aparc` | DK318 |
| `HCP.coarse.fsaverage.aparc` | HCP46 *(generated from MIND-network-informed graph metrics)* |
| `HCP.fsaverage.aparc` | HCP360 |

---

## Directory Structure

```bash
MIND-<projectname>/
├── networks/
│   └── <subject folder, e.g. SUBXXXXX>/
│       └── features/                       # e.g. CT_SA_SD_Vol_MC_FA_MD_ICVF_ISOVF_OD
│           └── <parcellation>/
│               ├── native/
│               │   ├── QC/
│               │   │   ├── roi_qc.csv      # run once, all 10 features
│               │   │   └── global_qc.csv   # run once, all 10 features
│               │   └── MIND/
│               │       ├── SUBXXXXX_mind_raw.csv
│               │       └── SUBXXXXX_mind_pca.csv
│               └── fsaverage6/
│                   ├── QC/
│                   │   ├── roi_qc.csv      # run once, all 10 features
│                   │   └── global_qc.csv   # run once, all 10 features
│                   └── MIND/
│                       ├── SUBXXXXX_mind_raw.csv
│                       └── SUBXXXXX_mind_pca.csv
│
└── stats/
    └── features/                           # e.g. CT_SA_SD_Vol_MC_FA_MD_ICVF_ISOVF_OD
        ├── QC/
        │   └── <parcellation>/
        │       ├── native/
        │       │   ├── roi_qc.csv          # run once, all 10 features
        │       │   └── global_qc.csv       # run once, all 10 features
        │       └── fsaverage6/
        │           ├── roi_qc.csv          # run once, all 10 features
        │           └── global_qc.csv       # run once, all 10 features
        └── pca_model_weights/
            ├── scaler.pkl                  # standard scaler weights
            └── pca_weights.pkl             # feature x PCA weight matrix
```

---

## QC Output

Each QC file reports the following, both **overall** and **broken down by ROI**:

- Total number of vertices with a value of `0`
- Number of vertices equal to `0`, per ROI
- Total number of vertices more than **7 MADs** from the median after z-scoring vertex-level data
- The same MAD-based outlier count, per ROI
- Proportion of identical values, both overall and per ROI
