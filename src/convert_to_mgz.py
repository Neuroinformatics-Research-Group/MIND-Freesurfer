# NB. These functions are written specifically to how I (Sarah, skc48)
# have understood the DTi surface vertex level projected data to be stored
# May only be usable for our data imaging folders and not translatable to the outside world
# Conversion from 1D .MGZ written
#
# STEP 1: CONVERT .1D FILES TO .MGZ
#
# These are AFNI SurfToSurf mapping files — NOT simple one-value-per-line.
# Each row has 8 columns:
#   Col 0:   source vertex index on native surface
#   Col 1-3: indices of 3 nearest neighbours on target surface
#   Col 4-6: interpolation weights for those neighbours
#   Col 7:   interpolated DWI value at this vertex  ← this is what we want
#
# Rows with failed projections (col 1 = -1) are excluded automatically
# because their vertex index won't appear in the .annot label mapping.
#
# get_vertex_df uses nibabel's read_morph_data which cannot read this format,
# so we extract col 7, sort by vertex index, and save as .mgz.

import os, sys
import numpy as np
import nibabel as nib
from nibabel.freesurfer.mghformat import MGHImage

def load_1D(path):
    """
    Load an AFNI SurfToSurf .1D file and return per-vertex DWI values.

    File format (comment lines start with #):
      Col 0:   source vertex index
      Col 1-3: nearest neighbour indices on target surface (-1 = failed projection)
      Col 4-6: interpolation weights
      Col 7:   interpolated DWI value  ← extracted here

    Returns a 1D float32 array of length n_vertices, ordered by vertex index.
    """
    data = np.loadtxt(path, comments='#')

    vertex_indices = data[:, 0].astype(int)
    values         = data[:, 7].astype(np.float32)

    # Sort by vertex index to ensure correct vertex ordering
    sort_order     = np.argsort(vertex_indices)
    vertex_indices = vertex_indices[sort_order]
    values         = values[sort_order]

    # Warn if any vertices are missing (failed projections)
    n_expected = vertex_indices[-1] - vertex_indices[0] + 1
    if len(vertex_indices) != n_expected:
        print(f"  WARNING: {n_expected - len(vertex_indices)} vertices missing "
              f"(failed projections) in {os.path.basename(path)}")

    return values

def save_as_mgz(data, out_path):
    """
    Save a 1D vertex array as a FreeSurfer .mgz surface file.
    MGHImage requires shape (n_vertices, 1, 1).
    """
    vol = data.reshape(-1, 1, 1)
    img = MGHImage(vol, affine=np.eye(4))
    nib.save(img, out_path)

def convert_to_mgz(tmp_dir, vol2surf_dir, path_to_surf_dir, parcellation, features, check_native_parc=True):

    # Temporary directory for converted .mgz files (cleaned up at the end)
    # Placed in work_dir — NOT in Data_Imaging which is read-only
    os.makedirs(tmp_dir, exist_ok=True)

    custom_feature_dirs = {}        # metric_name -> tmp_dir, for successfully converted metrics
    custom_feature_dirs_dict = {}   # metric_name -> '?h'-templated path, for project_custom_features / build_feature_tuples

    for metric_name, file_stem in features.items():
        converted_paths = {}
        for hemi in ['lh', 'rh']:
            src  = os.path.join(vol2surf_dir, f'{file_stem}_{hemi}.1D')
            dest = os.path.join(tmp_dir, f'{hemi}.{metric_name}.mgz')

            if not os.path.exists(src):
                print(f"WARNING: {src} not found — skipping {metric_name}")
                break

            if not os.path.exists(dest):   # skip re-conversion if already done
                data = load_1D(src)
                save_as_mgz(data, dest)
                print(f"  {metric_name} {hemi}: {len(data)} vertices loaded")

            converted_paths[hemi] = dest

        if len(converted_paths) == 2:
            # Build the '?'-templated path from either hemisphere's dest path
            template_path = os.path.join(tmp_dir, f'?.{metric_name}.mgz')
            custom_feature_dirs_dict[metric_name] = template_path
            custom_feature_dirs[metric_name] = (converted_paths['lh'], converted_paths['rh'])
            print(f"  {metric_name}: ready")
        else:
            print(f"  {metric_name}: SKIPPED (missing hemisphere file)")

    if len(custom_feature_dirs) == 0:
        print("ERROR: No DWI feature files found. Check vol2surf_dir path.")
        #sys.exit(1) # removed system exit so that subjects without DWI data don't exit the script

    print(f"\nUsing {len(custom_feature_dirs)} DWI features: {list(custom_feature_dirs.keys())}")

    # CHECK PARCELLATION .ANNOT FILES
    # get_vertex_df looks for:
    #   {surf_dir}/label/lh.{parcellation}.annot
    #   {surf_dir}/label/rh.{parcellation}.annot
    #
    # These are the same .annot files used for T1 MIND — surface-only,
    # i.e., 360 cortical HCP regions. Subcortical regions (indices 1-16 in the
    # DWI volumetric parcellation) are never present in .annot files so
    # they are automatically excluded by get_vertex_df.

    if check_native_parc:
        lh_annot = os.path.join(path_to_surf_dir, 'label', f'lh.{parcellation}.annot')
        rh_annot = os.path.join(path_to_surf_dir, 'label', f'rh.{parcellation}.annot')

        if not os.path.exists(lh_annot) or not os.path.exists(rh_annot):
            print(f"ERROR: Parcellation .annot files not found in:\n"
                  f"  {os.path.join(path_to_surf_dir, 'label')}\n"
                  f"Expected: lh.{parcellation}.annot and rh.{parcellation}.annot")
            # sys.exit(1) -> see above

        print(f"Found parcellation .annot files in {os.path.join(path_to_surf_dir, 'label')}")

    return custom_feature_dirs, custom_feature_dirs_dict

def get_mgz_filepaths(tmp_dir, features):
    """
    Same output shape as convert_to_mgz's (custom_feature_dirs,
    custom_feature_dirs_dict), but skips all conversion work (assumes the
    .mgz files already exist in tmp_dir and just checks for/collects them).

    Use this instead of convert_to_mgz when you are SURE you have already created the .mgz files.
    Otherwise, your MIND computation will fail - well this function will probs fail as well.

    input:
        tmp_dir (str or Path): directory expected to contain
            {hemi}.{metric_name}.mgz for each metric_name in features.
        features (dict): metric_name -> file_stem, the same used in convert_to_mgz's `features`
            argument. We only use metric_name (file_stem is only needed for the .1D conversion step, which this function never does).

    returns:
        custom_feature_dirs (dict): metric_name -> (lh_path, rh_path),
            for metrics where both hemisphere .mgz files exist.
        custom_feature_dirs_dict (dict): metric_name -> '?'-templated path,
            for the same metrics.
    """
    custom_feature_dirs = {}
    custom_feature_dirs_dict = {}

    for metric_name in features:
        lh_path = os.path.join(tmp_dir, f'lh.{metric_name}.mgz')
        rh_path = os.path.join(tmp_dir, f'rh.{metric_name}.mgz')

        if os.path.exists(lh_path) and os.path.exists(rh_path):
            template_path = os.path.join(tmp_dir, f'?.{metric_name}.mgz')
            custom_feature_dirs_dict[metric_name] = template_path
            custom_feature_dirs[metric_name] = (lh_path, rh_path)
            print(f"  {metric_name}: found")
        else:
            print(f"  {metric_name}: SKIPPED (missing hemisphere file in {tmp_dir})")

    if len(custom_feature_dirs) == 0:
        print("ERROR: No existing DWI feature .mgz files found. "
              f"Check tmp_dir ({tmp_dir}), or use convert_to_mgz if conversion hasn't run yet.")

    print(f"\nUsing {len(custom_feature_dirs)} DWI features: {list(custom_feature_dirs.keys())}")

    return custom_feature_dirs, custom_feature_dirs_dict