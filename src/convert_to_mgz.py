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

def convert_to_mgz(tmp_dir, vol2surf_dir, path_to_surf_dir, parcellation, features):

    # Temporary directory for converted .mgz files (cleaned up at the end)
    # Placed in work_dir — NOT in Data_Imaging which is read-only
    os.makedirs(tmp_dir, exist_ok=True)

    feature_tuples = []   # list of (lh_path, rh_path) tuples — one per metric

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
            feature_tuples.append((converted_paths['lh'], converted_paths['rh']))
            print(f"  {metric_name}: ready")
        else:
            print(f"  {metric_name}: SKIPPED (missing hemisphere file)")

    if len(feature_tuples) == 0:
        print("ERROR: No DWI feature files found. Check vol2surf_dir path.")
        sys.exit(1)

    print(f"\nUsing {len(feature_tuples)} DWI features: {list(features.keys())[:len(feature_tuples)]}")

    # CHECK PARCELLATION .ANNOT FILES
    # get_vertex_df looks for:
    #   {surf_dir}/label/lh.{parcellation}.annot
    #   {surf_dir}/label/rh.{parcellation}.annot
    #
    # These are the same .annot files used for T1 MIND — surface-only,
    # i.e., 360 cortical HCP regions. Subcortical regions (indices 1-16 in the
    # DWI volumetric parcellation) are never present in .annot files so
    # they are automatically excluded by get_vertex_df.

    lh_annot = os.path.join(path_to_surf_dir, 'label', f'lh.{parcellation}.annot')
    rh_annot = os.path.join(path_to_surf_dir, 'label', f'rh.{parcellation}.annot')

    if not os.path.exists(lh_annot) or not os.path.exists(rh_annot):
        print(f"ERROR: Parcellation .annot files not found in:\n"
              f"  {os.path.join(path_to_surf_dir, 'label')}\n"
              f"Expected: lh.{parcellation}.annot and rh.{parcellation}.annot")
        sys.exit(1)

    print(f"Found parcellation .annot files in {os.path.join(path_to_surf_dir, 'label')}")

    return feature_tuples
