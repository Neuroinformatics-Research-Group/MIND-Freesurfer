import sys
import os
import numpy as np
import pandas as pd
from MIND_helpers_2026 import calculate_mind_network, calculate_mind_network_fast, is_outlier, filter_vertex_data, scale_vertex_data, calculate_mind_network_fast_noROIflag
from get_vertex_df import get_vertex_df
import time

def compute_MIND(surf_dir, features_manual_list, parcellation, n_jobs=2, filter_vertices=False):

    vertex_data, regions, features_generated_list = get_vertex_df(surf_dir, features_manual_list, parcellation)

    '''
	Filter the data, do some QC checks here.
	To double check everything, please look at histograms of individual features to make sure everything looks ok.

	'''
    vertex_data_clean, per_label_stats = filter_vertex_data(vertex_data,
                                                            features_manual_list,
                                                            features_generated_list,
                                                            features2filter=('CT', 'Vol', 'SA'),
                                                            verbose=False)

    percentage_change = per_label_stats['pct_retained']


    # Drop outliers. This drops vertices with an MAD score in ANY of the used features. Can be customized.
    # z_score_threshhold = 7
    # outliers_per_features = np.array([is_outlier(vertex_data[x].values, z_score_threshhold) for x in features_used]).T
    # vertex_data = vertex_data.loc[np.sum(outliers_per_features, axis = 1) == 0]

    t0 = time.time()
    print('Computing MIND...')

    if filter_vertices:

        # standardize across the brain for each feature to get each dimension to roughly the same scale.
        vertex_data_z = scale_vertex_data(vertex_data_clean)
        # calculate MIND!
        MIND = calculate_mind_network_fast(vertex_data_z,
                                           features_generated_list,
                                           regions,
                                           percentage_change,  # e.g. per_label_stats["pct_retained"]
                                           n_jobs=n_jobs,
                                           pct_threshold=50.0,
                                           min_vertices=1,
                                           verbose=False)
    else:

        # standardize across the brain for each feature to get each dimension to roughly the same scale.
        vertex_data_z = scale_vertex_data(vertex_data)

        # calculate MIND!
        MIND = calculate_mind_network_fast_noROIflag(vertex_data_z, features_generated_list, regions, n_jobs=n_jobs)

        # calculate MIND network (ISAAC ORIGINAL FUNCTION)
        # MIND = calculate_mind_network(vertex_data, features_used, regions)
    print('Done!')
    print(f"MIND computation: {time.time() - t0:.1f}s")

    return MIND
