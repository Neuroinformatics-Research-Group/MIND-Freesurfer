from scipy.spatial import cKDTree as KDTree
import numpy as np
import pandas as pd
from collections import defaultdict
from joblib import Parallel, delayed

def is_outlier(points, thresh=7): #taken from https://stackoverflow.com/questions/22354094/pythonic-way-of-detecting-outliers-in-one-dimensional-observation-data

    """
    Returns a boolean array with True if points are outliers and False 
    otherwise.

    Parameters:
    -----------
        points : An numobservations by numdimensions array of observations
        thresh : The modified z-score to use as a threshold. Observations with
            a modified z-score (based on the median absolute deviation) greater
            than this value will be classified as outliers.

    Returns:
    --------
        mask : A numobservations-length boolean array.

    References:
    ----------
        Boris Iglewicz and David Hoaglin (1993), "Volume 16: How to Detect and
        Handle Outliers", The ASQC Basic References in Quality Control:
        Statistical Techniques, Edward F. Mykytka, Ph.D., Editor. 
    """
    if len(points.shape) == 1:
        points = points[:,None]
    median = np.median(points, axis=0)
    diff = np.sum((points - median)**2, axis=-1)
    diff = np.sqrt(diff)
    med_abs_deviation = np.median(diff)

    modified_z_score = 0.6745 * diff / med_abs_deviation

    return modified_z_score > thresh

def get_KDTree(x): #Inspired by https://gist.github.com/atabakd/ed0f7581f8510c8587bc2f41a094b518

    # Check the dimensions are consistent
    x = np.atleast_2d(x)
    
    # Build a KD tree representation of the samples
    xtree = KDTree(x)
    
    return xtree

def get_KL(x, y, xtree, ytree): #Inspired by https://gist.github.com/atabakd/ed0f7581f8510c8587bc2f41a094b518

    
    x = np.atleast_2d(x)
    y = np.atleast_2d(y)
    
    x = np.atleast_2d(x)
    y = np.atleast_2d(y)

    n,d = x.shape
    m,dy = y.shape
    
    #Check dimensions
    assert(d == dy)

    # Get the first two nearest neighbours for x, since the closest one is the
    # sample itself.
    r = xtree.query(x, k=2, eps=.01, p=2)[0][:,1]
    s = ytree.query(x, k=1, eps=.01, p=2)[0]
    
    # SARAH ADD: Suppress warnings - zeros and NaNs are handled below
    # need to suppress for DWI MIND not required for T1
    # DWI voxels are larger so some ROIs have very few data points, leading to degenerate KD-tree distributions where s collapses to zero
    # however, although this issue is already handled, warnings are still being generated
    with np.errstate(divide='ignore', invalid='ignore'):
        rs_ratio = r / s

    #Remove points with zero, nan, or infinity. This happens when two regions have a vertex with the exact same value – an occurence that basically onnly happens for the single feature MSNs
    #and has to do with FreeSurfer occasionally outputting the exact same value for different vertices.
    rs_ratio = rs_ratio[np.isfinite(rs_ratio)]
    rs_ratio = rs_ratio[rs_ratio!=0.0]
    
    # There is a mistake in the paper. In Eq. 14, the right side misses a negative sign
    # on the first term of the right hand side.

    kl = -np.log(rs_ratio).sum() * d / n + np.log(m / (n - 1.))
    kl = np.maximum(kl, 0)
    
    return kl

def calculate_mind_network(data_df, feature_cols, region_list):

    MIND = pd.DataFrame(np.zeros((len(region_list), len(region_list))), \
                        index = region_list, columns = region_list)
    
    grouped_data = data_df.groupby('Label')

    KDtrees = defaultdict(object)

    for i, (name_x, dat_x) in enumerate(grouped_data):
        tree = get_KDTree(dat_x[feature_cols])
        KDtrees[name_x] = tree
    
    used_pairs = []
    
    for i, (name_x, dat_x) in enumerate(grouped_data):
        
        for name_y, dat_y in grouped_data:
            if name_x == name_y:
                continue

            if set([name_x,name_y]) in used_pairs:
                continue

            dat_x = dat_x[feature_cols]
            dat_y = dat_y[feature_cols]

            KLa = get_KL(dat_x, dat_y, KDtrees[name_x], KDtrees[name_y])
            KLb = get_KL(dat_y, dat_x, KDtrees[name_y], KDtrees[name_x])

            kl = KLa + KLb

            MIND.at[name_x,name_y] = 1/(1+kl)
            MIND.at[name_y,name_x] = 1/(1+kl)

            used_pairs.append(set([name_x,name_y]))

    MIND = MIND[region_list].T[region_list].T
    MIND.index = MIND.columns  # reset index to match columns, important if subcortical is excluded
    
    return MIND


"""
Sarah additions (Feb-March 2026), code written in collaboration with Claude (chat interface)
Comments manually written, for any errors: skc48@cam.ac.uk

filter_vertex_data()
get_qc_data()
scale_vertex_data()
calculate_mind_network_fast()

"""

"""

COMMENTS FOR filter_vertex_data()

-> added a filter_vertex_data_function that uses the same logic from the original mind function 
(i.e., retains any vertices where value not equal to 0, with the idea that 0s in a given vertex represent bad data).
However, instead of being preset in the MIND wrapper function to CT, Vol, and SA any list of features by which a researcher
wants to filter can be passed in the argument vertices2filter

The arguments that it requires are:

1) vertex_data from yor get_vertex_data function

2) features_manual_list (which is the list of features you pass the to the main MIND function, i.e. ["CT", "VoL", "SA"]) 
3) features_generated_list (which is the list of features returend by the get_vertex_data function

NB. the logic behind these two lists is that I think the MIND function when reading the vertex data won't always return
columns names that match your original feature list, so by combining these two lists you are essentially saying:
Here's the list of features I asked for, in the order I asked for them
And here is the list of column names that were actually returned for the dataframe with these features 

When you look at the original MIND wrapper function, this is what features and features used are, I just renamed features to 
feature_manual_list to make it clear that these are your manually assigned ones and features_used to features_generated_list 
so that's clear that these are the ones spat out by get_vertex_data. 

---- DEFAULTS ----

4) features2filter, your list of features (present to 'CT', 'Vol', 'SA')

NB. 0 values in vertices don't always mean bad data! CHECK your data first before deciding by which feature to filter by 
 
5) verbose (default=False), if True when running the function will print:
    -> your arguments (features selected)
    -> how may rows were dropped by the filtering process
    -> summary stats for your original data by feature (for all of features in your data)
    -> summary stats for your cleaned up data (for all of features in your data)
    (NB. summary stats should show you how your data has changed, i.e. mean, sd, max, min, and you can use this as a sanity check)
 
Remove filter_vertices Boolean as redudant in this function. 

----
This function then returns:

vertex_data_clean = your cleaned up vertex_data, with columns names that match the feature you selected
per_label_stats = a dataframe containing: vertex counts before cleaning, after cleaning, number vertices removed, % of vertices retained

-> per_label_stats will be called later in the main MIND function to filter ROIs by % of vertices removed and/or vertices removed (rows dropped)

COMMENTED OUT BECAUSE REDUNDANT: 
n_removed_vertices = the number of vertices (rows dropped) removed from your original dataframe

"""

def filter_vertex_data(vertex_data, features_manual_list, features_generated_list,
                       features2filter=('CT', 'Vol', 'SA'),
                       verbose=False):
    columns = ['Label'] + list(features_generated_list)
    feature_conv_dict = dict(zip(features_manual_list, features_generated_list))

    vertex_data_clean = vertex_data.copy()

    for feat in features2filter:
        if feat in features_manual_list:
            col = feature_conv_dict[feat]
            vertex_data_clean = vertex_data_clean[vertex_data_clean[col] != 0]

    vertex_data_clean = vertex_data_clean[columns]
    # n_removed_vertices = len(vertex_data) - len(vertex_data_clean)

    # Per-label counts: before, after, removed, % retained
    counts_before = vertex_data['Label'].value_counts()
    counts_after = vertex_data_clean['Label'].value_counts()

    per_label_stats = pd.DataFrame({
        'n_before': counts_before,
        'n_after': counts_after.reindex(counts_before.index, fill_value=0),
    })
    per_label_stats['n_removed'] = per_label_stats['n_before'] - per_label_stats['n_after']
    per_label_stats['pct_retained'] = 100 * per_label_stats['n_after'] / per_label_stats['n_before']
    per_label_stats = per_label_stats.sort_values('pct_retained')

    if verbose:
        print("VERTEX DATA CLEAN UP LOGGING")
        print("=== Features list being used and final conversion dictionaries ===")
        print("features:      ", list(features_manual_list))
        print("used_features: ", list(features_generated_list))
        print("conv_dict:     ", feature_conv_dict)
        print("=== Inspect orginal data compared to cleaned up data ===")
        print(f"Before filtering: {len(vertex_data)} rows")
        print(f"After filtering:  {len(vertex_data_clean)} rows")
        print(f"Removed:          {len(vertex_data) - len(vertex_data_clean)} rows")
        for feat in features2filter:
            if feat in features_manual_list:
                col = feature_conv_dict[feat]
                n_zeros_before = (vertex_data[col] == 0).sum()
                print(f"{feat} ({col}): {n_zeros_before} zeros before filtering")
        for feat in features2filter:
            if feat in features_manual_list:
                col = feature_conv_dict[feat]
                n_zeros = (vertex_data_clean[col] == 0).sum()
                print(f"{feat} ({col}): {n_zeros} zeros remaining")
        print("=== Check summaries for original data ===")
        for feat, col in feature_conv_dict.items():
            print(f"{feat} -> {col}: min={vertex_data[col].min():.3f}, max={vertex_data[col].max():.3f}")
        print("=== Check summaries for cleaned up data ===")
        for feat, col in feature_conv_dict.items():
            print(f"{feat} -> {col}: min={vertex_data_clean[col].min():.3f}, max={vertex_data_clean[col].max():.3f}")

    return vertex_data_clean, per_label_stats, #n_removed_vertices

"""
COMMENTS for get_qc_data()

"""

# count number of zero values
def n_zero_values(s):
    return int((s == 0).sum())

# count proportion of unique values
def prop_identical_values(s):
    # s = s.dropna()
    # prop_unique = (1 - s.nunique() / len(s)) if len(s) else np.nan
    return (1 - s.nunique() / len(s)) if len(s) else np.nan # prop_unique

def get_qc_data(vertex_data,
                features_generated_list):

    records = []
    for feat in features_generated_list:
        values = vertex_data[feat].values
        n_total = len(values)

        records.append({
            'feature': feat,
            'n_total': n_total,
            'n_outliers': int(is_outlier(values, thresh=7).sum()),
            'prop_identical_values': 1 - (len(np.unique(values)) / n_total),
            'n_zero_values': int(np.sum(values == 0)),
        })

    qc_dataframe = pd.DataFrame(records).set_index('feature')

    # by roi dataframe in long format (one column per metric, where each roi is an roi and feature is label
    roi_qc = (
        vertex_data
        .groupby('Label')[features_generated_list]
        .agg([n_zero_values, prop_identical_values])
        .stack(level=0)
        .rename_axis(['roi', 'feature'])
        .sort_index()
    )

    # ROI size
    roi_qc['n_vertices'] = (
        vertex_data.groupby('Label').size()
        .reindex(roi_qc.index.get_level_values('roi')).values
    )

    return qc_dataframe, roi_qc

"""
COMMENTS for scale_vertex_data()

(Adapted from the original MIND function)

1) vertex_data: takes your vertex x feature with ROI labels dataframe generated by get_vertex_data()

Returns: 

vertex_data_z: your scaled vertex level dataframe

NB: Scaling will does NOT care if you pass a cleaned up (see above) or the dataframe generated by get_vertex_data(),
either are accepted by the function

"""

def scale_vertex_data(vertex_data):
    # grab the features you have in your data (we ignore column 0 because that is our ROI label data)
    features2scaleby = list(vertex_data.columns[1:])

    # make copy of vertex data to store out the z scaled data
    vertex_data_z = vertex_data.copy()

    # standardize across the brain for each feature to get each dimension to roughly the same scale.
    for x in features2scaleby:
        vertex_data_z[x] = (vertex_data[x] - vertex_data[x].mean()) / vertex_data[x].std()

    return vertex_data_z


"""
Function embedded in the compute_mind_fast version of the compute mind
to run the get_KL function in parallel
"""

def compute_pair(name_x, name_y, dat_x, dat_y, tree_x, tree_y, feature_cols):
    dx = dat_x[feature_cols]
    dy = dat_y[feature_cols]
    KLa = get_KL(dx, dy, tree_x, tree_y)
    KLb = get_KL(dy, dx, tree_y, tree_x)
    return name_x, name_y, 1 / (1 + KLa + KLb)


"""
COMMENTS for calculate_mind_network_fast()

1) vertex_df: The final vertex x feature (with ROI as 'Label' column) on which you want to run your MIND network

2) features_generated_list: the features list returned by get_vertex_data

3) regions_list: the region list returned by get_vertex_data

4) percentage_change: the data stored in the column "pct_retained" in per_label_stats, so you would want to pass per_label_stats["pct_retained"]

---- DEFAULTS ----

5) n_jobs = 2 -> this is the number of CPUS you want to run your MIND network on, if you set n_jobs=-1 it will use all of the CPUs on your machine

NB: run the below lines in your CLI/terminal to check how many available cpus your machine has (for local testing, have not checked for the HPC - I doubt this is the right checking mechanism)

$ python
$ import os
$ os.cpu_count()

6) pct_threshold = 50.0 -> percentage threshold for filtering, i.e., if 50% the MIND computation will not NaN ROIs that retained more than 50% of their vertices in the cleaning step so that any ROI with less than 50%
of its original vertices/rows will not be included in the MIND computation

THIS DEFAULTS IS NOT SCIENTIFICALLY SOUND, it should be up the discretion of the researcher to ensure that the correct threshold is passed based on logical deduction (and possibly parcellation/data sample chosed)

7) min_vertices = 1 -> minimum number of vertices that an ROI should have to be include in the MIND computation

WHY this extra step? I.e., for coarser parcellations you might have ROIs will small number of vertices, so even with a % threshold you might still get ROIs that have a small number of vertices 
I.e., an ROI with 20 vertices originally, now drops to 10 but is still passed to the MIND compuations by meeting the 50% threshold. 

Defaulting to min_vertices = 1, just means we don't really care about ROIs will small n of vertices and we are going to pass any ROI that meets our % threshold as long as it's not an empty ROI (as empty ROIs shouldn't work - should raise an error). 

As above, THIS DEFAULT IS NOT SCIENTIFICALLY SOUND and should be up the discretion of the researchers to ensure that a sound n of vertices if chosen for the MIND computation. 

8) verbose = False

If True, you will get the following print out

-> ROIS that were identified as not meeting the thresholds (undersized) and that will be NAN'd (not passed to the MIND computation)
-> how much vertex level was in each of these ROIs by percentage

9) roi_flag = True

If True, the MIND function will be run on all of the data, regardless of cleaning
If False, the various vertex percentage etc. thresholds will be passed

---
RETURNS
---

MIND: your ROI x ROI mind network, with undersized ROIs masked as NaNs

"""


def calculate_mind_network_fast(vertex_df,
                                features_generated_list,
                                region_list,
                                percentage_change,  # e.g. per_label_stats["pct_retained"]
                                n_jobs=2,
                                pct_threshold=50.0,
                                min_vertices=1,
                                verbose=False,
                                roi_flag=True):

    MIND = pd.DataFrame(np.zeros((len(region_list), len(region_list))),
                        index=region_list, columns=region_list)

    # Convert to dict, faster than repeated groupby iteration
    grouped_data = {name: dat for name, dat in vertex_df.groupby('Label')}

    # Only use regions that are actually in the data
    regions = [r for r in region_list if r in grouped_data]

    if roi_flag:
        # Build KD-trees
        KDtrees = {name: get_KDTree(dat[features_generated_list]) for name, dat in grouped_data.items()}

        # Generate all unique pairs upfront — eliminates used_pairs list scan
        pairs = [(regions[i], regions[j])
                 for i in range(len(regions))
                 for j in range(i + 1, len(regions))]

        print(f"Computing {len(pairs)} region pairs across {n_jobs} cores...")

        # Parallelise across pairs
        # results = Parallel(n_jobs=n_jobs, prefer="threads")(
        results = Parallel(n_jobs=n_jobs, backend="loky", verbose=10)(
            delayed(compute_pair)(
                name_x, name_y,
                grouped_data[name_x], grouped_data[name_y],
                KDtrees[name_x], KDtrees[name_y],
                features_generated_list
            )
            for name_x, name_y in pairs
        )

        # Fill matrix
        for name_x, name_y, val in results:
            MIND.at[name_x, name_y] = val
            MIND.at[name_y, name_x] = val

        MIND.index = MIND.columns
        return MIND
    else:
        if regions == list(region_list):
            print("✓ regions matches region_list exactly (same items, same order)")
        else:
            print("✗ regions differs from region_list")
            print(f"  region_list: {len(region_list)} items")
            print(f"  regions:     {len(regions)} items")
            print(f"  missing:     {sorted(set(region_list) - set(regions))}")
            print(f"  extra:       {sorted(set(regions) - set(region_list))}")

        # Identify regions that didn't retain enough vertices.
        # A region is "undersized" if it's missing from percentage_change
        # (never appeared / lost all vertices) OR fell below the threshold.
        # percentages and threshold set as input to the function, where minium % is 50 and minimum vertex count is 1
        # THESE ARE NOT SCIENTIFICALLY SOUND
        # But, i.e., setting vertex count minimum to 1 stops the MIND computation from crashing out if a whole ROI is empty
        # SO treat the presets as 'crash out' fail safes and NOT scientific parameters

        sizes = {name: len(dat) for name, dat in grouped_data.items()}
        undersized = {
            r for r in regions
            if r not in percentage_change.index
            or percentage_change.loc[r] < pct_threshold
            or sizes[r] < min_vertices
        }

        if undersized:
            if verbose:
                print(f"Found {len(undersized)} regions with < {pct_threshold}% vertex retention "
                      f"(will return NaN for their pairs):")
                print(f"undersized set has {len(undersized)} items: {sorted(undersized)}")
                #print(f"percentage_change index has {len(percentage_change.index)} entries, "
                #      f"{percentage_change.index.duplicated().sum()} duplicates")
            for r in sorted(undersized):
                pct = percentage_change.loc[r] if r in percentage_change.index else float('nan')
                n = len(grouped_data[r])
                if verbose:
                    print(f"  {r}: n={n}, pct_retained={pct:.1f}%")

        # Build KD-trees only for regions that meet the minimum
        KDtrees = {name: get_KDTree(dat[features_generated_list])
                   for name, dat in grouped_data.items()
                   if name not in undersized}

        # Generate all unique pairs upfront
        all_pairs = [(regions[i], regions[j])
                     for i in range(len(regions))
                     for j in range(i + 1, len(regions))]

        # Split into pairs to compute vs pairs to set as NaN
        pairs_to_compute = [(a, b) for a, b in all_pairs
                            if a not in undersized and b not in undersized]
        pairs_to_skip = [(a, b) for a, b in all_pairs
                         if a in undersized or b in undersized]

        print(f"Computing {len(pairs_to_compute)} region pairs across {n_jobs} cores "
              f"(skipping {len(pairs_to_skip)} pairs involving undersized regions)...")

        # Parallelise across valid pairs only
        results = Parallel(n_jobs=n_jobs, backend="loky")(#, verbose=10)(
            delayed(compute_pair)(
                name_x, name_y,
                grouped_data[name_x], grouped_data[name_y],
                KDtrees[name_x], KDtrees[name_y],
                features_generated_list
            )
            for name_x, name_y in pairs_to_compute
        )

        # Fill matrix with computed values
        for name_x, name_y, val in results:
            MIND.at[name_x, name_y] = val
            MIND.at[name_y, name_x] = val

        # Fill NaN for pairs involving undersized regions
        for name_x, name_y in pairs_to_skip:
            MIND.at[name_x, name_y] = np.nan
            MIND.at[name_y, name_x] = np.nan

        # Also set diagonal of undersized regions to NaN
        for r in undersized:
            MIND.at[r, r] = np.nan

        MIND.index = MIND.columns
        return MIND


"""
RUN THE MIND FUNCTION IN PARALLEL, but no ROI masking 

NB. I believe this function will fail if an ROI (i.e., in coarser parcellations) has 0 vertices

def calculate_mind_network_fast_noROIflag(vertex_df, feature_cols, region_list, n_jobs=8):

    MIND = pd.DataFrame(np.zeros((len(region_list), len(region_list))),
                        index=region_list, columns=region_list)

    # Convert to dict, faster than repeated groupby iteration
    grouped_data = {name: dat for name, dat in vertex_df.groupby('Label')}

    # Only use regions that are actually in the data
    regions = [r for r in region_list if r in grouped_data]

    # Build KD-trees
    KDtrees = {name: get_KDTree(dat[feature_cols]) for name, dat in grouped_data.items()}

    # Generate all unique pairs upfront — eliminates used_pairs list scan
    pairs = [(regions[i], regions[j])
             for i in range(len(regions))
             for j in range(i + 1, len(regions))]

    print(f"Computing {len(pairs)} region pairs across {n_jobs} cores...")

    # Parallelise across pairs
    # results = Parallel(n_jobs=n_jobs, prefer="threads")(
    results = Parallel(n_jobs=n_jobs, backend="loky", verbose=10)(
        delayed(compute_pair)(
            name_x, name_y,
            grouped_data[name_x], grouped_data[name_y],
            KDtrees[name_x], KDtrees[name_y],
            feature_cols
        )
        for name_x, name_y in pairs
    )

    # Fill matrix
    for name_x, name_y, val in results:
        MIND.at[name_x, name_y] = val
        MIND.at[name_y, name_x] = val

    MIND.index = MIND.columns
    return MIND

"""