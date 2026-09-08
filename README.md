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
│   └── native/
│       └── <parcellation>/
│           └── features/                       # e.g. CT_SA_SD_Vol_MC_FA_MD_ICVF_ISOVF_OD
│               │   ├── QC/
│               │   │   ├── SUBXXXXX_roi_qc.csv      # run once, all 10 features
│               │   │   └── SUBXXXXX_global_qc.csv   # run once, all 10 features
│               │   └── MIND/
│               │       ├── SUBXXXXX_mind_raw.csv
│               │       └── SUBXXXXX_mind_pca.csv
│   └── fsaverage6/
│       └── <parcellation>/
│           └── features/                       # e.g. CT_SA_SD_Vol_MC_FA_MD_ICVF_ISOVF_OD
│               │   ├── QC/
│               │   │   ├── SUBXXXXX_roi_qc.csv      # run once, all 10 features
│               │   │   └── SUBXXXXX_global_qc.csv   # run once, all 10 features
│               │   └── MIND/
│               │       ├── SUBXXXXX_mind_raw.csv
│               │       └── SUBXXXXX_mind_pca.csv
│
└── stats/
    └── features/                           # e.g. CT_SA_SD_Vol_MC_FA_MD_ICVF_ISOVF_OD
        ├── QC/
        │   └── <parcellation>/
        │       ├── native/
        │       │   ├── roi_qc.csv          # all 10 features
        │       │   └── global_qc.csv       # all 10 features
        │       └── fsaverage6/
        │           ├── roi_qc.csv          # all 10 features
        │           └── global_qc.csv       # all 10 features
        └── pca_model_weights/
            ├── scaler.pkl                  # standard scaler weights
            └── pca_weights.pkl             # feature x PCA weight matrix
```

---

## QC Output

If you set the flag 'return_qc' as True, every run of the pipeline will produce two per subject .csv files relating to downstream quality control of the data, in addition to your desired MIND network. 

- **File 1**: A **global** QC file (SUBXXXXX_global_qc.csv), will contain the following information:
    - Total number of vertices ('n_total')
    - Total number of outlier vertices, which are vertices more than **7 MADs** from the median after z-scoring vertex-level data ('n_outliers')
    - Total number of vertices equal to 0 ('n_zero_values')
    - Entropy Concentration Coefficient across all ROIs, regardless of whether they are used in the MIND networks (i.e., 'lh_??' for HCP parcellations^1) ('C_n_outliers', 'C_n_identical_values', 'C_n_zero_values')
    - Entropy Concentration Coefficient^2 across only ROIs included in the MIND networks (i.e., excluding 'lh_??' for HCP parcellations) ('C_n_outliers_excl_bad_rois', 'C_n_identical_values_excl_bad_rois', 'C_n_zero_values_excl_bad_rois')
    - The dataframe/file is in long formate, so a 'features' column containing the respective features (i.e., CT, FA, etc.)

1) Applied the same 'bad ROI' logic as in the original MIND network computation (refer to Sebenius et al., 2023 for more detailed information)
2) Entropy Concentration Coefficient is computed using the equation first described in Bandt (2020), defined in the following section (see 'Concentration coefficient per feature').
   
- **File 2**: A **per ROI** QC file (SUBXXXX_roi_qc.csv), will contain:
    - Total number of vertices ('n_total')
    - Total number of outlier vertices, which are vertices more than **7 MADs** from the median after z-scoring vertex-level data ('n_outliers')
    - Total number of vertices equal to 0 ('n_zero_values')
    - The dataframe/file is in long formate, so a 'features' column containing the respective features (i.e., CT, FA, etc.)
    - An ROI column containing the respective ROI labels
---

## Concentration coefficient per feature

For each feature `f` and each count type `c` (`n_outliers`, `n_identical_values`, `n_zero_values`), we quantify how concentrated that count is across ROIs, relative to the distribution of vertices across those same ROIs, using the **entropy concentration coefficient** of Bandt (2020).

Let $i = 1, \dots, N_f$ index the ROIs belonging to feature $f$, with raw counts

$$
p_i = \text{count}_c(\text{ROI}_i), \qquad q_i = n\_vertices(\text{ROI}_i)
$$

and totals $P_{\text{tot}} = \sum_i p_i$, $Q_{\text{tot}} = \sum_i q_i$. If either total is zero, concentration is undefined ($C_f = \text{NaN}$). Otherwise, normalize into probability distributions over ROIs:

$$
P_i = \frac{p_i}{P_{\text{tot}}}, \qquad Q_i = \frac{q_i}{Q_{\text{tot}}}
$$

Following Bandt, define the Shannon entropy of $P$,

$$
H(P) = -\sum_{i=1}^{N_f} P_i \log P_i
$$

and the Kullback–Leibler divergence of $P$ from $Q$,

$$
D(P,Q) = \sum_{i=1}^{N_f} P_i \log \frac{P_i}{Q_i}
$$

The **entropy ratio** is then

$$
U(P,Q) = \frac{H(P)}{H(P) + D(P,Q)}
$$

and the **entropy concentration coefficient** — what `concentration_coefficient(P, Q)` computes — is its complement:

$$
C_f = 1 - U(P,Q) = \frac{D(P,Q)}{H(P) + D(P,Q)}
$$

**Interpretation:** $C_f \in [0, 1]$. $C_f = 0$ iff $P = Q$ (occurrences of `c` exactly track vertex count, i.e. maximally uniform). $C_f = 1$ iff $P$ is a point mass where all occurrences of `c` concentrated in a single ROI. This coefficient behaves like Gini's concentration coefficient in scale and interpretation, but, unlike Gini or raw KL divergence, should be largely unbiased by the number of ROIs $N_f$, since it's a ratio of entropies rather than a sum of absolute deviations. See Bandt (2020) for a detailed discussion.

This is computed independently per feature `f` and per count type `c`, producing the per-feature concentration coefficients reported for each metric.

---

## References

Bandt, C. (2020). Entropy Ratio and Entropy Concentration Coefficient, with Application to the COVID-19 Pandemic. *Entropy*, 22(11), 1315. https://doi.org/10.3390/e22111315

Sebenius, I., Seidlitz, J., Warrier, V., Bethlehem, R. A., Alexander-Bloch, A., Mallard, T. T., ... & Morgan, S. E. (2023). Robust estimation of cortical similarity networks from brain MRI. *Nature neuroscience*, 26(8), 1461-1471.
