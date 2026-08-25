"""
new_parc_support.py

Support for a parcellation ("new_parc") that only exists as an
fsaverage6-space .annot under {root_dir}/parcellations/, not natively in
any subject's RDS surfaces_directory or fsaverage_directory.

Two cases:

  space == "fsaverage6": paths["fsaverage_directory"] is already scratch
      (writable), so we just need new_parc's .annot symlinked into its
      label/ subfolder. No warping needed -- the source is already in
      fsaverage6 space.

  space == "native": paths["surfaces_directory"] is read-only RDS, so we
      can't write new_parc's native-space .annot there. Instead we build
      a scratch "shadow" directory that symlinks in the real surf/ and
      label/ contents (so compute_MIND sees the same feature files it
      would in the real dir) and additionally contains new_parc's
      native-space .annot, warped down from fsaverage6 via
      project_parcellation_to_native.

Both ensure_* functions are safe to call every run: symlinks are only
created if missing, and project_parcellation_to_native itself skips
re-warping if the target .annot already exists. So across repeated runs
(e.g. CT, then CT+SA), nothing gets recreated that's already there --
only whatever's newly required gets built.

Both ensure_* functions return a plain str, not a Path -- get_vertex_df
does `surf_dir + '/'` internally, a raw string concat that raises
TypeError on a PosixPath, so the cast happens at the return boundary
here rather than upstream.

ASSUMPTIONS (please confirm / adjust against your actual code):
  - compute_MIND's first positional arg is a single directory that must
    contain both the feature files and a label/ subfolder with the
    requested parcellation's .annot -- i.e. the same layout convention
    used by get_vertex_df elsewhere in this pipeline.
  - get_paths(EID, ...) returns a dict with "surfaces_directory" and
    "fsaverage_directory" keys, matching project_to_fsaverage6.py's
    docstring example.
  - HEMIS = ['lh', 'rh'] and a root_dir / parcellations_dir and a
    writable root_path/scratch root are available -- pass these in
    explicitly since I can't see where they're defined in your codebase.
"""

import os
from pathlib import Path

from src.project2fsaverage6 import setup_subjects_dir
from src.projectnewparcs2native import project_parcellation_to_native

# NEW_PARC_NAME = "hcp_coarse"

def ensure_new_parc_fsaverage6(parcellation, paths, parcellations_dir, hemispheres=('lh', 'rh')):
    fsavg_dir = Path(paths["fsaverage_directory"])
    label_dir = fsavg_dir / "label"
    label_dir.mkdir(parents=True, exist_ok=True)
    for hemi in hemispheres:
        # src = Path(parcellations_dir) / "fsaverage6" / f"{hemi}.{parcellation}.annot"
        src = Path(parcellations_dir) / f"{hemi}.{parcellation}.annot"
        dst = label_dir / f"{hemi}.{parcellation}.annot"

        if dst.is_symlink() and not dst.exists():
            print(f"  removing broken symlink {dst}")
            dst.unlink()
        elif dst.exists():
            continue

        if not src.exists():
            raise FileNotFoundError(
                f"new_parc fsaverage6 annotation not found: {src}\n"
                f"Check parcellations_dir ({parcellations_dir})."
            )
        dst.symlink_to(src)
        print(f"  linked {dst}")
    return str(fsavg_dir)

def ensure_new_parc_native(parcellation, paths, eid, parcellations_dir, root_path, hemispheres=('lh', 'rh')):
    """
    Builds (or reuses) a scratch shadow native surf_dir for eid: symlinks
    in the real surf/ and label/ contents from the read-only RDS
    surfaces_directory, then warps new_parc's fsaverage6 .annot down into
    its label/ subfolder via project_parcellation_to_native.

    Safe to call every run -- existing symlinks and an already-warped
    new_parc.annot are both left alone.

    RETURNS:
        str path to the shadow directory, to pass to compute_MIND in
        place of paths["surfaces_directory"] when parcellation ==
        "new_parc" and space == "native".
    """
    root_path = Path(root_path)
    real_surf_dir = Path(paths["surfaces_directory"])

    shadow_dir = root_path / "native_shadow" / eid
    shadow_surf = shadow_dir / "surf"
    shadow_label = shadow_dir / "label"
    shadow_surf.mkdir(parents=True, exist_ok=True)
    shadow_label.mkdir(parents=True, exist_ok=True)

    # Symlink real surf/ contents in (feature files compute_MIND needs)
    real_surf = real_surf_dir / "surf"
    for f in real_surf.iterdir():
        link = shadow_surf / f.name
        if not link.exists():
            link.symlink_to(f)

    # Symlink existing label/ files in too, so other parcellations
    # (aparc etc.) still resolve correctly from this same shadow dir
    real_label = real_surf_dir / "label"
    if real_label.exists():
        for f in real_label.iterdir():
            link = shadow_label / f.name
            # skip new_parc itself -- that gets written for real below,
            # not symlinked, since it doesn't exist in the real dir
            if f.name.startswith(f"{f.name.split('.')[0]}.{parcellation}."):
                continue
            if not link.exists():
                link.symlink_to(f)

    # Warp new_parc fsaverage6 -> native directly into shadow_dir/label/.
    # Reuses setup_subjects_dir (subject + fsaverage6 both symlinked into
    # one SUBJECTS_DIR), same as the native<->fsaverage6 warps elsewhere.
    subjects_dir = setup_subjects_dir(eid, real_surf_dir, root_path)
    project_parcellation_to_native(
        subjects_dir=subjects_dir,
        subjid=eid,
        parcellation=parcellation,
        hemispheres=hemispheres,
        parcellations_dir=parcellations_dir,
        tmp_out_dir=shadow_dir,   # writes straight into shadow_dir/label/
    )

    # Same reasoning as ensure_new_parc_fsaverage6: get_vertex_df does
    # `surf_dir + '/'` internally, which breaks on a PosixPath. Cast here
    # rather than upstream so shadow_dir stays a Path for everything else
    # in this function.
    return str(shadow_dir)