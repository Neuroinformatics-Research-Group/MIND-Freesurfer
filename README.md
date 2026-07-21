# UKB-MIND
*Scripts for running MIND on the whole of UKB structural imaging data*

## Directory Structure 

```bash
├── MIND output
│   ├── QC output
│   ├── PCA model weights
│   │   ├── 5 macrostructural features
│   │   │   ├── Pickle file 1: standard scaler weights
│   │   │   ├── Pickle file 2: feature x PCA weights (matrix)
│   │   ├── 5 microstructural features
│   │   │   ├── Pickle file 1: standard scaler weights
│   │   │   ├── Pickle file 2: feature x PCA weights (matrix)
│   │   ├── 10 features (micro + macro)
│   │   │   ├── Pickle file 1: standard scaler weights
│   │   │   ├── Pickle file 2: feature x PCA weights (matrix)
│   ├── Subject specific folders (i.e., UKBXXXXX)
│   │   ├── 5 macrostructural features
│   │   │  ├── Native space
│   │   │  │   ├── Parcellation (i.e., aparc)
│   │   │  │   │   ├── raw MIND network (ie., UKBXXXXX_mind_raw.csv)
│   │   │  │   │   ├── PCA MIND network (ie., UKBXXXXX_mind_pca.csv)
│   │   │  ├──fsaverage6 space
│   │   │  │   ├──Parcellation (i.e., aparc)
│   │   │  │   │  ├── raw MIND network (ie., UKBXXXXX_mind_raw.csv)
│   │   │  │   │  ├── PCA MIND network (ie., UKBXXXXX_mind_pca.csv)
│   │   ├── 5 microstructural features
│   │   │  ├── Native space
│   │   │  │   ├── Parcellation (i.e., aparc)
│   │   │  │   │   ├── raw MIND network (ie., UKBXXXXX_mind_raw.csv)
│   │   │  │   │   ├── PCA MIND network (ie., UKBXXXXX_mind_pca.csv)
│   │   │  ├──fsaverage6 space
│   │   │  │   ├──Parcellation (i.e., aparc)
│   │   │  │   │  ├── raw MIND network (ie., UKBXXXXX_mind_raw.csv)
│   │   │  │   │  ├── PCA MIND network (ie., UKBXXXXX_mind_pca.csv)
│   │   ├── 10 features (macro + micro)
│   │   │  ├── Native space
│   │   │  │   ├── Parcellation (i.e., aparc)
│   │   │  │   │   ├── raw MIND network (ie., UKBXXXXX_mind_raw.csv)
│   │   │  │   │   ├── PCA MIND network (ie., UKBXXXXX_mind_pca.csv)
│   │   │  ├──fsaverage6 space
│   │   │  │   ├──Parcellation (i.e., aparc)
│   │   │  │   │  ├── raw MIND network (ie., UKBXXXXX_mind_raw.csv)
│   │   │  │   │  ├── PCA MIND network (ie., UKBXXXXX_mind_pca.csv)
└── 
```

## QC output

- the total number of vertices that have 0 as their value
- how many vertices == 0 per ROI
- total number of vertices that are more than 7 MADs after z-scoring the vertex level data
- same information by ROI
- the proportion of identical values (by total and by ROI)

