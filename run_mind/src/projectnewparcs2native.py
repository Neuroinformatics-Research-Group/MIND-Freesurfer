"""
project_parcellation_to_native.py

Warps an fsaverage6-space .annot parcellation into a subject's native
space using FreeSurfer's mri_surf2surf. This is the reverse direction of
project_to_fsaverage6.py's project_parcellation, which goes native -> fsaverage6;
this module goes fsaverage6 -> native.

Source parcellations are expected at:
    {parcellations_dir}/lh.{parcellation}.annot
    {parcellations_dir}/rh.{parcellation}.annot
(e.g. parcellations_dir = root_dir/parcellations)

Since the subject's native-space directory typically lives on read-only
shared storage (RDS), the warped output cannot be written back there.
Instead it's written to a scratch tmp_out_dir/label/ folder, and the
resulting paths are returned so they can be passed along to whatever
consumes native-space annotations later (e.g. get_vertex_df, or a
downstream MIND/ROI pipeline step) without needing to touch RDS.

Requires:
    - FreeSurfer installed and sourced in the environment this runs in
    - mri_surf2surf on PATH
    - setup_subjects_dir (from project_to_fsaverage6.py) called first, so
      that SUBJECTS_DIR contains both the subject (under eid) and
      fsaverage6, symlinked in

Example usage:

    from pathlib import Path
    from project_to_fsaverage6 import setup_subjects_dir
    from project_parcellation_to_native import project_parcellation_to_native

    EID = "sub-001"
    root_path = Path("/scratch/your_username")
    root_dir = Path("/my/project/directory")

    subjects_dir = setup_subjects_dir(EID, paths["surfaces_directory"], root_path)

    tmp_out_dir = root_path / "tmp_native_parc" / EID
    tmp_out_dir.mkdir(parents=True, exist_ok=True)

    parc_paths = project_parcellation_to_native(
        subjects_dir=subjects_dir,
        subjid=EID,
        parcellation="Schaefer2018_400Parcels_7Networks_order",
        hemispheres=["lh", "rh"],
        parcellations_dir=root_dir / "parcellations",
        tmp_out_dir=tmp_out_dir,
    )
    # parc_paths == {"lh": ".../label/lh.<parc>.annot", "rh": ".../label/rh.<parc>.annot"}

    # Or, if downstream code wants a '?'-templated single path (matching
    # the convention used elsewhere in this pipeline, e.g. convert_to_mgz):
    template_path = build_native_parcellation_template(tmp_out_dir, "Schaefer2018_400Parcels_7Networks_order")
    # template_path == ".../label/?.Schaefer2018_400Parcels_7Networks_order.annot"
"""

import os
import subprocess


def run_mri_surf2surf_between(srcsubject, trgsubject, hemi, sval=None, sval_annot=None, tval=None):
    """
    Direction-agnostic version of project_to_fsaverage6.run_mri_surf2surf.
    That function hardcodes --srcsubject <subjid> --trgsubject fsaverage6,
    which only supports the native -> fsaverage6 direction. This version
    takes both srcsubject and trgsubject explicitly, so it also supports
    fsaverage6 -> native (or any other subject pair present in the same
    SUBJECTS_DIR).

    Pass exactly one of sval (scalar feature) or sval_annot (annotation).
    Raises RuntimeError if mri_surf2surf exits with a nonzero return code.
    """
    if (sval is None) == (sval_annot is None):
        raise ValueError("Provide exactly one of sval or sval_annot.")

    cmd = [
        "mri_surf2surf",
        "--srcsubject", srcsubject,
        "--trgsubject", trgsubject,
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
            f"mri_surf2surf failed ({srcsubject} -> {trgsubject}) for {tval}\n"
            f"cmd: {' '.join(cmd)}\n"
            f"{result.stderr[-800:]}"
        )

    print(f"  wrote {tval}")
    return True


def project_parcellation_to_native(subjects_dir, subjid, parcellation, hemispheres,
                                    parcellations_dir, tmp_out_dir, allow_missing=False):
    """
    Warps an fsaverage6-space .annot parcellation to the subject's native
    space, writing output to tmp_out_dir/label/ (since native-space RDS
    storage is typically read-only).

    Skips any hemisphere whose output .annot already exists in
    tmp_out_dir/label/, so this is safe to re-run.

    INPUT SPECIFICATIONS:
        subjects_dir (str or Path): SUBJECTS_DIR built by setup_subjects_dir,
            containing both the subject (under subjid) and fsaverage6.
        subjid (str): subject ID, matching the folder name used in
            subjects_dir (i.e. the --trgsubject for this warp).
        parcellation (str): parcellation name, matching the '<parcellation>'
            in '{hemi}.{parcellation}.annot'.
        hemispheres (list of str): e.g. ['lh', 'rh'].
        parcellations_dir (str or Path): directory containing the source
            fsaverage6 .annot files, e.g. root_dir / 'parcellations'.
        tmp_out_dir (str or Path): scratch directory to write native-space
            .annot output into (a 'label' subfolder is created here).
        allow_missing (bool): if True, a missing hemisphere's source .annot
            is skipped with a warning instead of raising. Default False,
            since a parcellation you explicitly asked to warp missing a
            hemisphere is very likely a path/naming bug worth catching
            immediately, rather than silently producing a one-hemisphere
            (or empty) result downstream.

    RETURNS:
        dict mapping hemi -> path to the native-space .annot file, for
        whichever hemispheres were successfully written (or already
        existed). Raises RuntimeError if nothing ends up written at all.
    """
    print(f"=== Projecting parcellation ({parcellation}) fsaverage6 -> native ({subjid}) ===")

    label_dir = os.path.join(tmp_out_dir, "label")
    os.makedirs(label_dir, exist_ok=True)

    written = {}
    missing = []

    for hemi in hemispheres:
        src_annot = os.path.join(parcellations_dir, f'{hemi}.{parcellation}.annot')
        tgt_annot = os.path.join(label_dir, f'{hemi}.{parcellation}.annot')

        if os.path.exists(tgt_annot):
            written[hemi] = tgt_annot
            continue

        if not os.path.exists(src_annot):
            missing.append(src_annot)
            if allow_missing:
                print(f"  WARNING: {src_annot} not found, skipping.")
                continue
            raise FileNotFoundError(
                f"fsaverage6 parcellation not found: {src_annot}\n"
                f"Check parcellations_dir ({parcellations_dir}) and parcellation name ({parcellation})."
            )

        run_mri_surf2surf_between(
            srcsubject='fsaverage6',
            trgsubject=subjid,
            hemi=hemi,
            sval_annot=src_annot,
            tval=tgt_annot,
        )
        written[hemi] = tgt_annot

    if not written:
        raise RuntimeError(
            f"project_parcellation_to_native wrote no files for parcellation '{parcellation}' "
            f"(all sources missing: {missing}). label_dir is empty: {label_dir}"
        )

    return written


def build_native_parcellation_template(tmp_out_dir, parcellation):
    """
    Builds a single '?'-templated path for the native-space parcellation
    written by project_parcellation_to_native, matching the '?' (not '?h')
    convention used elsewhere in this pipeline (e.g. convert_to_mgz's
    custom_feature_dirs_dict), so it substitutes cleanly with
    path_template.replace('?', 'lh') / .replace('?', 'rh').

    Does not check that the files actually exist -- call this after
    project_parcellation_to_native has confirmed they were written.
    """
    label_dir = os.path.join(tmp_out_dir, "label")
    return os.path.join(label_dir, f'?.{parcellation}.annot')
