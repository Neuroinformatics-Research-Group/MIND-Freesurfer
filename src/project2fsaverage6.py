"""
project_to_fsaverage6.py

Functions for projecting a subject's native-space FreeSurfer surface data
into fsaverage6 space by calling FreeSurfer's mri_surf2surf. Outputs are
written into a single shared directory, with the parcellation nested under
a label/ subfolder (to match what get_vertex_df expects) and everything
else flat:

    out_dir/label/?h.<parcellation>.annot
    out_dir/?h.<standard_feature>.fsaverage6.mgh
    out_dir/?h.<name>.fsaverage6.mgh

This lets get_vertex_df be called unmodified with surf_dir=out_dir and
parcellation="<yourpacrcellationhere>.fsaverage6".

Standard/custom feature .mgh files can be passed in as (lh_path, rh_path) tuples pointing directly
into this folder (see build_feature_tuples).

Requires:
    - FreeSurfer installed and sourced in the environment this script runs in
      (SUBJECTS_DIR must be set, and fsaverage6 must exist under it)
    - mri_surf2surf on PATH

notes from the debugging process:

Previously, a missing native source file or a failed mri_surf2surf call
would only print a WARNING/ERROR and silently continue, so a bad
SUBJECTS_DIR/eid or a broken FreeSurfer environment could result in an
out_dir with an empty label/ folder and no .mgh files, but return code 0
and no raised exception. This version raises FileNotFoundError for a
missing native source and RuntimeError for a failed mri_surf2surf call,
matching the fail-loud behavior of mri_preprocessing.py's
warp_parcs_to_native. Use allow_missing=True on a per-call basis if you
deliberately want the old "skip and warn" behavior for optional features.

Example usage (from another script), using an EID/paths-dict style setup
where the native subject data lives on read-only shared storage and all
outputs go to a writable scratch root:

    from pathlib import Path
    from project_to_fsaverage6 import (
        setup_subjects_dir,
        project_parcellation,
        project_standard_features,
        project_custom_features,
        build_feature_tuples,
    )
    from get_vertex_df import get_vertex_df

    EID = "sub-001"
    MAIN_dir = Path("/rds/path/to/shared_storage")
    root_path = Path("/scratch/your_username")
    DATA_DIR = "derivatives"
    project_dir = "my_project"

    paths = {
        "surfaces_directory": MAIN_dir / DATA_DIR / EID / "surfaces" / EID,
        "vol2surf_directory": MAIN_dir / DATA_DIR / EID / "surfaces" / "vol2surf_DWI" / "surface",
        "micro_directory": root_path / "tmp_mgz" / EID,
        "fsaverage_directory": root_path / "tmp_fsavg" / EID,
        "network_directory": root_path / project_dir / "networks" / EID,
        "stats_directory": root_path / project_dir / "stats" / EID,
    }

    parcellation = "aparc"
    hemispheres = ["lh", "rh"]
    standard_features = ["thickness", "curv"]
    custom_features = {
        "FA": str(paths["vol2surf_directory"] / "?h.dti_FA_T1space_al2std60_back2sub"),
        "MD": str(paths["vol2surf_directory"] / "?h.dti_MD_T1space_al2std60_back2sub"),
    }

    out_dir = paths["fsaverage_directory"]
    out_dir.mkdir(parents=True, exist_ok=True)

    # Symlinks the read-only surfaces_directory into a scratch SUBJECTS_DIR
    # and sets the SUBJECTS_DIR environment variable for mri_surf2surf.
    subjects_dir = setup_subjects_dir(EID, paths["surfaces_directory"], root_path)

    project_parcellation(subjects_dir, EID, parcellation, hemispheres, out_dir)
    project_standard_features(subjects_dir, EID, standard_features, hemispheres, out_dir)
    project_custom_features(EID, custom_features, hemispheres, out_dir)

    features = build_feature_tuples(out_dir, standard_features + list(custom_features.keys()))

    vertex_data, combined_regions, used_features = get_vertex_df(
        surf_dir=str(out_dir),
        features=features,
        parcellation=f"{parcellation}.fsaverage6",
    )
"""

import os
import subprocess
from pathlib import Path


def setup_subjects_dir(eid, surfaces_directory, root_path, freesurfer_home=None):
    """
    Builds a scratch-based SUBJECTS_DIR that mri_surf2surf can use, by symlinking a read-only native-space subject folder (and fsaverage6) into a writable scratch location.

    Sets the SUBJECTS_DIR environment variable so mri_surf2surf picks it up automatically.

    Safe to call concurrently across many SLURM array tasks sharing the same subjects_dir:

    symlink creation is guarded against FileExistsError since multiple tasks may pass the `exists()` check before any of them actually creates the link
    (most likely for fsaverage6_link, since every task writes the identical link at job start).
    """
    root_path = Path(root_path)
    surfaces_directory = Path(surfaces_directory)

    if not surfaces_directory.exists():
        raise FileNotFoundError(
            f"surfaces_directory does not exist: {surfaces_directory}\n"
            "Check that this path is correct before setting up subjects_dir "
            "(a bad path here is a common cause of silent downstream failures)."
        )

    subjects_dir = root_path / "tmp_subjects_dir"
    subjects_dir.mkdir(parents=True, exist_ok=True)

    # Symlink the (possibly read-only) subject folder in under its EID name
    subject_link = subjects_dir / eid
    if not subject_link.exists():
        try:
            subject_link.symlink_to(surfaces_directory)
        except FileExistsError:
            # another concurrent array task (e.g. a rerun overlapping
            # this one) created it first -- fine, it's the same target
            pass

    # Symlink fsaverage6 in, if not already present. This is the highest
    # collision-risk link: every array task writes the exact same target,
    # so with many tasks starting at once, several can pass the exists()
    # check before any of them finishes creating the link.
    fsaverage6_link = subjects_dir / "fsaverage6"
    if not fsaverage6_link.exists():
        if freesurfer_home is None:
            freesurfer_home = os.environ.get("FREESURFER_HOME")
        if not freesurfer_home:
            raise EnvironmentError(
                "FREESURFER_HOME not set and not passed explicitly; cannot locate fsaverage6."
            )
        fsaverage6_src = Path(freesurfer_home) / "subjects" / "fsaverage6"
        if not fsaverage6_src.exists():
            raise FileNotFoundError(
                f"fsaverage6 not found under FREESURFER_HOME: {fsaverage6_src}"
            )
        try:
            fsaverage6_link.symlink_to(fsaverage6_src)
        except FileExistsError:
            # another concurrent array task created it first, fine
            pass

    os.environ["SUBJECTS_DIR"] = str(subjects_dir)
    return subjects_dir


def run_mri_surf2surf(subjid, hemi, sval=None, sval_annot=None, tval=None):
    """
    Runs mri_surf2surf to project a file from subjid's native space to
    fsaverage6. Pass exactly one of sval (scalar feature) or sval_annot
    (annotation/parcellation file).

    Raises RuntimeError if mri_surf2surf exits with a nonzero return code,
    instead of printing an ERROR and returning False. This ensures a
    failure here is never silently swallowed by a calling loop that
    doesn't check the return value.
    """
    if (sval is None) == (sval_annot is None):
        raise ValueError("Provide exactly one of sval or sval_annot.")

    cmd = [
        "mri_surf2surf",
        "--srcsubject", subjid,
        "--trgsubject", "fsaverage6",
        "--hemi", hemi,
    ]

    if sval_annot is not None:
        cmd += ["--sval-annot", sval_annot]
    else:
        cmd += ["--sval", sval]

    cmd += ["--tval", tval]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(
            f"mri_surf2surf failed for {tval}\n"
            f"cmd: {' '.join(cmd)}\n"
            f"{result.stderr[-800:]}"
        )

    print(f"  wrote {tval}")
    return True


def project_parcellation(subjects_dir, subjid, parcellation, hemispheres, out_dir,
                          allow_missing=False):
    """
    Projects lh/rh .annot parcellation files from native space to fsaverage6,
    writing them to out_dir/label/ (matching get_vertex_df's expected layout).

    By default, raises FileNotFoundError if a native source .annot is
    missing for a hemisphere, and RuntimeError if no output files end up
    written at all (e.g. both hemispheres missing/failed) -- so a bad
    subjects_dir/subjid, or a broken FreeSurfer environment, can no
    longer result in a silently empty label/ directory.

    Set allow_missing=True to restore the old warn-and-skip behavior for
    an optional parcellation, but this still raises if *nothing* gets
    written for any hemisphere.
    """
    print(f"=== Projecting parcellation ({parcellation}) to fsaverage6 ===")

    # get_vertex_df expects the annotation under a label/ subfolder of
    # surf_dir, so nest it here even though everything else stays flat.
    label_dir = os.path.join(out_dir, "label")
    os.makedirs(label_dir, exist_ok=True)

    written = []
    missing = []

    for hemi in hemispheres:
        src_annot = os.path.join(subjects_dir, subjid, "label", f"{hemi}.{parcellation}.annot")
        #tgt_annot = os.path.join(label_dir, f"{hemi}.{parcellation}.fsaverage6.annot")
        tgt_annot = os.path.join(label_dir, f"{hemi}.{parcellation}.annot")

        if os.path.exists(tgt_annot):
            written.append(tgt_annot)
            continue

        if not os.path.exists(src_annot):
            missing.append(src_annot)
            if allow_missing:
                print(f"  WARNING: {src_annot} not found, skipping.")
                continue
            raise FileNotFoundError(
                f"Native parcellation not found: {src_annot}\n"
                f"Check subjects_dir ({subjects_dir}) and subjid ({subjid})."
            )

        run_mri_surf2surf(subjid, hemi, sval_annot=src_annot, tval=tgt_annot)
        written.append(tgt_annot)

    if not written:
        raise RuntimeError(
            f"project_parcellation wrote no files for parcellation '{parcellation}' "
            f"(all sources missing: {missing}). label_dir is empty: {label_dir}"
        )


def project_standard_features(subjects_dir, subjid, features, hemispheres, out_dir,
                               allow_missing=True):
    """
    Projects standard FreeSurfer morphometric features (e.g. thickness,
    curv, volume, area, sulc) from native space to fsaverage6, writing
    them flat into out_dir.

    Individual missing features are skipped with a warning by default
    (allow_missing=True), matching mri_preprocessing.py's treatment of
    optional features -- but if a feature is missing/fails for *both*
    hemispheres (i.e. nothing at all gets written for it), that now
    raises RuntimeError rather than silently producing no output.
    """
    print("\n=== Projecting standard morphometric features to fsaverage6 ===")

    any_written = False

    for feature in features:
        written_this_feature = []
        for hemi in hemispheres:
            src_file = os.path.join(subjects_dir, subjid, "surf", f"{hemi}.{feature}")
            tgt_file = os.path.join(out_dir, f"{hemi}.{feature}.fsaverage6.mgh")

            if not os.path.exists(src_file):
                if allow_missing:
                    print(f"  WARNING: {src_file} not found, skipping.")
                    continue
                raise FileNotFoundError(f"Native feature file not found: {src_file}")

            run_mri_surf2surf(subjid, hemi, sval=src_file, tval=tgt_file)
            written_this_feature.append(tgt_file)

        if not written_this_feature:
            print(f"  WARNING: feature '{feature}' produced no output for either hemisphere.")
        else:
            any_written = True

    if features and not any_written:
        raise RuntimeError(
            "project_standard_features wrote no files for any requested feature: "
            f"{features}. Check subjects_dir ({subjects_dir}) and subjid ({subjid})."
        )


def project_custom_features(subjid, custom_features, hemispheres, out_dir,
                             allow_missing=True):
    """
    Projects custom scalar surface features (e.g. DTI/NODDI maps already
    in native surface space) to fsaverage6, writing them flat into out_dir.

    custom_features: dict mapping name -> path template containing a
    literal '?' where the hemisphere prefix goes, e.g.:
        {"FA": "/data/sub-001/dti_surf/?h.dti_FA_T1space_al2std60_back2sub"}

    Same fail-loud behavior as project_standard_features: an individual
    missing hemisphere file is skipped with a warning, but a feature that
    ends up with zero output files raises RuntimeError, and if *no*
    requested feature produces any output at all this raises too.
    """
    print("\n=== Projecting custom features to fsaverage6 ===")

    any_written = False

    for name, path_template in custom_features.items():
        written_this_feature = []
        for hemi in hemispheres:
            src_file = path_template.replace("?", hemi)
            tgt_file = os.path.join(out_dir, f"{hemi}.{name}.fsaverage6.mgh")

            if not os.path.exists(src_file):
                if allow_missing:
                    print(f"  WARNING: {src_file} not found, skipping.")
                    continue
                raise FileNotFoundError(f"Native custom feature file not found: {src_file}")

            run_mri_surf2surf(subjid, hemi, sval=src_file, tval=tgt_file)
            written_this_feature.append(tgt_file)

        if not written_this_feature:
            print(f"  WARNING: custom feature '{name}' produced no output for either hemisphere.")
        else:
            any_written = True

    if custom_features and not any_written:
        raise RuntimeError(
            "project_custom_features wrote no files for any requested custom feature: "
            f"{list(custom_features.keys())}. Check the path templates and subjid ({subjid})."
        )


def build_feature_tuples(out_dir, feature_names, hemispheres=("lh", "rh"), suffix="fsaverage6.mgh"):
    """
    Builds a list of (lh_path, rh_path) tuples for use as the `features`
    argument to get_vertex_df, based on files written by the project_*
    functions above into out_dir.

    inputs:
        out_dir (str): directory containing the projected feature files.
        feature_names (list of str): names of features to include, matching
            the <name> portion of "?h.<name>.<suffix>" (e.g. "thickness",
            "curv", "FA", "MD").
        hemispheres (tuple of str): hemisphere prefixes, defaults to ("lh", "rh").
        suffix (str): filename suffix used when the files were written,
            defaults to "fsaverage6.mgh" to match project_standard_features
            and project_custom_features.

    returns:
        list of (lh_path, rh_path) tuples, one per feature_name, ready to
        pass directly as `features` to get_vertex_df. Missing files are
        skipped with a warning rather than raising an error, since by the
        time this runs you may deliberately be working with a subset of
        successfully-projected features.
    """
    feature_tuples = []

    for name in feature_names:
        lh_path = os.path.join(out_dir, f"{hemispheres[0]}.{name}.{suffix}")
        rh_path = os.path.join(out_dir, f"{hemispheres[1]}.{name}.{suffix}")

        if not (os.path.exists(lh_path) and os.path.exists(rh_path)):
            print(f"  WARNING: could not find both hemispheres for feature '{name}', skipping. "
                  f"(checked {lh_path}, {rh_path})")
            continue

        feature_tuples.append((lh_path, rh_path))

    return feature_tuples

def build_custom_feature_dict(out_dir, name_pairs, suffix="fsaverage6.mgh"):
    """
    name_pairs: dict mapping the lookup key (e.g. shorthand 'CT') to the
    filename stem used when fsaverage6 files were written (e.g. 'thickness').
    Returns {key: (lh_path, rh_path)}, skipping any pair missing on disk.
    """
    result = {}
    for key, filename in name_pairs.items():
        lh = os.path.join(out_dir, f"lh.{filename}.{suffix}")
        rh = os.path.join(out_dir, f"rh.{filename}.{suffix}")
        if os.path.exists(lh) and os.path.exists(rh):
            result[key] = (lh, rh)
        else:
            print(f"  WARNING: missing fsaverage6 output for '{key}' ({filename}), skipping.")
    return result