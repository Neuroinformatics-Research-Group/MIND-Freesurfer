# UKB-MIND
*Scripts for running MIND on the whole of UKB structural imaging data*

## Directory Structure 

```bash
Parent directory: MIND output
  
   **Sub directory**: sub x QC per feature tables
   
   **Sub directory**: Subject specific folders
   
                           -> native space
                           
                                 -> parcellation
                                 
                                       -> raw 
                                       
                                       -> PCA
                                       
                           -> fsavergae6 space
                           
                                 -> parc
                                 
                                       -> raw
                                       
                                       -> pca
   
   **Sub directory**: PCA model weights
   
         -> 5 macrostructural features
         
               Pickle file 1: standard scaler weights
               
               Pickle file 2: feature x PCA weights (matrix)
               
         -> 5 microstructural features 
         
         -> 10 feature altogether
```

## QC output

- the total number of vertices that have 0 as their value
- how many vertices == 0 per ROI
- total number of vertices that are more than 7 MADs after z-scoring the vertex level data
- same information by ROI
- the proportion of identical values (by total and by ROI)

