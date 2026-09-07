from src.convert_to_mgz import convert_to_mgz, get_mgz_filepaths
from src.project2fsaverage6 import setup_subjects_dir, project_parcellation, project_standard_features, project_custom_features, build_custom_feature_dict
from src.newparcsupport import ensure_new_parc_native, ensure_new_parc_fsaverage6
from src.MIND_helpers_2026 import resolve_features, get_micro_features
from src.MIND_2026 import compute_MIND

import argparse
import ast
import os
from pathlib import Path

import logging
from pathlib import Path

# get timestamps
from datetime import datetime

logger = logging.getLogger(__name__)

# ensure lists can be passed as arguments and are not intepreted as literal strings when you run the main script from a BASH script
def parse_list(value):
    try:
        parsed = ast.literal_eval(value)
        if not isinstance(parsed, list):
            raise ValueError
        return parsed
    except (ValueError, SyntaxError):
        raise argparse.ArgumentTypeError(
            f"Invalid list format: {value!r}. Expected something like \"['CT','SA']\"."
        )

def get_paths(EID: str, data_dir, out_dir, projectname, test_mode = False):
    """
    Build (and optionally create) the standard set of paths for a given subject.

    See github repo for more info on directory structure.

    :param EID: subject ID
    :param data_dir: directory where imaging data is stored (e.g., dir/Data_Imaging)
    :param out_dir: output directory for MIND networks (e.g., dur/Data_Imaging)
    :param mind_dir: base directory for MIND outputs; defaults to DATA_DIR if not given
    :param projectname: project name which will become the extension of your out directory
    :param test_mode: whether to run in test mode or not, defaults to False - where the 'test' is saving all output in scratch (i.e., rds/hpc-work), rather than in a shared outputs directory

    :return: dict with keys:
        - root_path (where you are launching analysis from, ideally your scratch)
        - surfaces_directory
        - vol2surf_directory
        - micro_directory
        - fsaverage6_directory
        - network_directory
        - stats_directory
        - parcellations_directory
    """

    # get timestamp
    now = datetime.now()

    root_path = Path.cwd()
    logger.debug("Current working directory: %s", root_path)

    # MAIN_dir = Path(MAIN_DIR)
    #run_dir = f"mindrun_{now.strftime('%Y%m%d_%H%M%S')}"
    project_dir = f"MIND_{projectname}"

    if test_mode:
        out_dir = root_path

    paths = {
        "root_path": root_path,
        "surfaces_directory": os.path.join(data_dir, EID, "surfaces", EID),
        "vol2surf_directory": os.path.join(data_dir, EID, "surfaces", "vol2surf_DWI", "surface"),
        "micro_directory": os.path.join(root_path, "tmp_mgz", EID),
        "fsaverage_directory": os.path.join(root_path, "tmp_fsavg", EID),
        #"network_directory": os.path.join(out_dir, project_dir, "networks", EID),
        "network_directory": os.path.join(out_dir, project_dir, "networks"),
        "stats_directory": os.path.join(out_dir, project_dir, "stats"),
        "parcellations_dir": os.path.join(root_path, "parcellations", "fsaverage6")
    }
    return paths

"""
If they don't exist yet, create any new directories relevant to the project (i.e., tmp or outputs)
Won't work if you don't have write access in your output directory and you're not in test_mode 
"""

def ensure_dirs(paths, keys = ("micro_directory",
                                "fsaverage_directory",
                                "network_directory",
                                "stats_directory")):
    # Create tmp and output directories from a paths dict.
    for key in keys:
        keyaspath = Path(paths[key])
        keyaspath.mkdir(parents=True, exist_ok=True)

"""
Wrapper to get the mgz_files (either create them if they haven't been created yet or extract only filepaths if they have)
"""

def get_mgz_files(paths, feature_list_to_use, parcellation, create_files,
                      known_nonnative_parcs=frozenset({"HCP.coarse.fsaverage.aparc"})):

    features = get_micro_features(feature_list_to_use)

    # run convert_to_mgz once on all microstructural features, if files exsists then skip
    # .mgz files stored by default in a tmp directory
    # DWI metrics available in vol2surf_DWI/surface/
    # creates the .mgz files from the back2sub files needed to compute mind
    # returns a dictionary of features and related filepaths so that no modifications are need to compute_MIND
    # to use the microstructural data
    if create_files:
        custom_feature_dirs, custom_feature_dirs_dict = convert_to_mgz(
            paths["micro_directory"],
            paths["vol2surf_directory"],
            paths["surfaces_directory"],
            parcellation,
            features,
            check_native_parc=(parcellation not in known_nonnative_parcs), # ensure we don't exit script if parc is new
        )
    else:
        custom_feature_dirs, custom_feature_dirs_dict = get_mgz_filepaths(paths["micro_directory"], features)

    # creates a final feature list only reading the features requested in feature_list_to_use (i.e., ["CT", "MD"])
    # where the final list keeps the "CT" naming convention for macro and returns a filepath naming convention for micro
    features2use = resolve_features(feature_list_to_use, custom_dirs=custom_feature_dirs)

    return features2use, custom_feature_dirs_dict

"""
Wrapper to get the fsaverage6_files (either create them if they haven't been created yet or extract only filepaths if they have)
"""

def get_fsaverage6_files(paths,
                            EID,
                            parcellation,
                            feature_list_to_use,
                            features2use_micro,
                            create_files,
                            micro=False,
                            macro_feature_list = ("CT", "MC", "Vol", "SD", "SA"),
                            hemispheres = ("lh", "rh"),
                            warp_parcellation = True):
    macro_map = {
        "CT": "thickness",
        "Vol": "volume",
        "SA": "area",
        "MC": "curv",
        "SD": "sulc",
    }
    # Build (or reuse) the scratch SUBJECTS_DIR, symlinking in the
    # read-only surfaces_directory and fsaverage6.
    # root_path = Path.cwd()
    subjects_dir = setup_subjects_dir(EID, paths["surfaces_directory"], paths["root_path"])

    # Translate shorthand codes to the actual FreeSurfer filenames
    macro_filenames = [macro_map[f] for f in macro_feature_list]

    if create_files:
        # Only warp the parcellation from native space if it actually exists
        # there. Parcellations that only exist as an fsaverage6/fsaverage7
        # source (e.g. HCP.coarse.fsaverage.aparc) are populated separately
        # by ensure_new_parc_fsaverage6 in main_analysis. Attempting the
        # native warp here would look for a native label/{parcellation}.annot
        # that was never going to exist.
        if warp_parcellation:
            project_parcellation(subjects_dir, EID, parcellation, hemispheres, paths["fsaverage_directory"])

        project_standard_features(subjects_dir, EID, macro_filenames, hemispheres, paths["fsaverage_directory"])
        if micro:
            project_custom_features(EID, features2use_micro, hemispheres, paths["fsaverage_directory"])

    macro_name_pairs = {shorthand: macro_map[shorthand] for shorthand in macro_feature_list}
    custom_feature_dirs = build_custom_feature_dict(paths["fsaverage_directory"], macro_name_pairs)

    if micro:
        micro_name_pairs = {name: name for name in features2use_micro.keys()}
        custom_feature_dirs.update(build_custom_feature_dict(paths["fsaverage_directory"], micro_name_pairs))

    features2use = resolve_features(feature_list_to_use, custom_dirs=custom_feature_dirs)

    return features2use

"""
Run your main analysis -

? Running on a new parcellation
-> generate new parcellation if it doesn't exists in your original data source 

? Running in native space 
-> create .mgz files if you need to use micro data and they haven't been created yet
    -> otherwise just get the filepaths
-> compute and save out your MIND network (also return qc files if you want them, otherwise make sure return_qc is set to false when calling the script)

? Running in fsaverage6 space
-> create fsaverage6 files if they haven't been created yet
    -> otherwise just get the filepaths
-> compute and save out your MIND network (also return qc files if you want them, otherwise make sure return_qc is set to false when calling the script)

NOTE that in this pipeline new files that would normally belong in the subjects original data folder are created in tmp folders 
(nothing is written into the data folder for the subject)

This is to preserve the read only access to the data and to not to edit any files/create problems downstream

HOWEVER - there are not automatic 'remove' or 'delete' steps in this pipeline, therefore once you are satisfied with your MIND run and you've computed every 
iteration you want to compute, it's up to you to delete the tmp files and free up your scratch folder (and the native_shadow folder which is symlink folder created for the new parcellations)
"""
def main_analysis(EID,
                  data_dir,
                  out_dir,
                  projectname,
                  parcellation,
                  feature_list_to_use,
                  space,
                  micro: bool,
                  resample: bool,
                  return_qc: bool,
                  n_jobs=8,
                  filter_vertices=False,
                  create_files=False,
                  test_mode=False):

    """
    :param EID: subject ID of the person for which you are computing MIND (i.e., "SUB0000001")
    :param parcellation: parcellation for which you want to run MIND (i.e., "aparc")
    :param feature_list_to_use: micro or macrostructural features on which you want to compute MIND ["CT", SA" ect.]
    :param space: "native", "fsaverage6" etc.
    :param micro: bool, True if you are using any microstructural data
    :param n_jobs: n cores you want to run the parallelized process on
    :param filter_vertices: do you want to apply any filtering logic to remove any vertex level data ? default: False
    :return: into the relevant output directory, it saves a MIND network as a .csv, and two subject level QC .csv
    """
    # features2use_micro = None
    # features2use_fsavg = None

    paths = get_paths(EID, data_dir, out_dir, projectname, test_mode=test_mode)
    ensure_dirs(paths) # make sure all of your tmp/outdirs exist

    feature_directory_name = "_".join(feature_list_to_use)

    mind_output_directory = os.path.join(paths["network_directory"], space, parcellation, feature_directory_name, "MIND")
    qc_output_directory = os.path.join(paths["network_directory"], space, parcellation, feature_directory_name, "QC")

    Path(mind_output_directory).mkdir(parents=True, exist_ok=True)
    Path(qc_output_directory).mkdir(parents=True, exist_ok=True)

    new_parcs = {"HCP.coarse.fsaverage.aparc"}

    # figure out which directory compute_MIND should actually be pointed at, before the space match below
    native_source_dir = paths["surfaces_directory"]
    fsavg_source_dir = paths["fsaverage_directory"]

    if parcellation == "HCP.coarse.fsaverage.aparc":
        if space == "native":
            native_source_dir = ensure_new_parc_native(parcellation, paths, EID, paths["parcellations_dir"], paths["root_path"])
        elif space == "fsaverage6":
            fsavg_source_dir = ensure_new_parc_fsaverage6(parcellation, paths, paths["parcellations_dir"])

    match space:
        case "native":
            if micro:
                features2use_micro, features2use_micro_dict = get_mgz_files(paths,
                                                                            feature_list_to_use,
                                                                            parcellation,
                                                                            create_files=create_files)
                feature_list_to_use = features2use_micro

            print(f"DEBUG native feature_list_to_use: {feature_list_to_use!r}")

            if return_qc:
                MIND, qc_dataframe, roi_qc = compute_MIND(native_source_dir,
                                                          feature_list_to_use,
                                                          parcellation,
                                                          resample=resample,
                                                          return_qc=return_qc,
                                                          n_jobs=n_jobs,
                                                          filter_vertices=filter_vertices)

                MIND.to_csv(os.path.join(mind_output_directory, f"{EID}_mind_raw.csv"), index=False)
                qc_dataframe.to_csv(os.path.join(qc_output_directory, f"{EID}_global_qc.csv"), index=False)
                roi_qc.to_csv(os.path.join(qc_output_directory, f"{EID}_roi_qc.csv"), index=False)

            else:

                MIND = compute_MIND(native_source_dir,
                                    feature_list_to_use,
                                    parcellation,
                                    resample=resample,
                                    return_qc=return_qc,
                                    n_jobs=n_jobs,
                                    filter_vertices=filter_vertices)

                MIND.to_csv(os.path.join(mind_output_directory, f"{EID}_mind_raw.csv"), index=False)

        case "fsaverage6":

            features2use_micro_dict = {}

            if micro:
                features2use_micro, features2use_micro_dict = get_mgz_files(paths,
                                                                            feature_list_to_use,
                                                                            parcellation,
                                                                            create_files=create_files)


            features2use_fsavg = get_fsaverage6_files(paths,
                                                      EID,
                                                      parcellation,
                                                      feature_list_to_use,
                                                      features2use_micro_dict,
                                                      create_files=create_files,
                                                      micro=micro,
                                                      warp_parcellation=(parcellation not in new_parcs))

            feature_list_to_use = features2use_fsavg
            print(f"DEBUG fsaverage6 feature_list_to_use: {feature_list_to_use!r}, fsavg_source_dir: {fsavg_source_dir!r}")

            if return_qc:

                MIND, qc_dataframe, roi_qc = compute_MIND(fsavg_source_dir,
                                                          feature_list_to_use,
                                                          parcellation,
                                                          resample=resample,
                                                          return_qc=return_qc,
                                                          n_jobs=n_jobs,
                                                          filter_vertices=filter_vertices)

                MIND.to_csv(os.path.join(mind_output_directory, f"{EID}_mind_raw.csv"), index=False)
                qc_dataframe.to_csv(os.path.join(qc_output_directory, f"{EID}_global_qc.csv"), index=False)
                roi_qc.to_csv(os.path.join(qc_output_directory, f"{EID}_roi_qc.csv"), index=False)

            else:

                MIND  = compute_MIND(fsavg_source_dir,
                                      feature_list_to_use,
                                      parcellation,
                                      resample=resample,
                                      return_qc=return_qc,
                                      n_jobs=n_jobs,
                                      filter_vertices=filter_vertices)

                MIND.to_csv(os.path.join(mind_output_directory, f"{EID}_mind_raw.csv"), index=False)
        case _:
            raise ValueError(f"Unrecognized space: {space!r}. Expected 'native' or 'fsaverage6'.")

if __name__ == "__main__":
    """
    to run
    $ python MIND_pipeline_2026.py --subject="SUB0000001" --data_dir="your/data/dir" --out_dir="your/our/dir" --projectname="yourprojectname" --parcellation="aparc" --feature_list_to_use=("CT", "SA") --space="native" --no-micro --return_qc --create_files --test_mode
    """

    parser = argparse.ArgumentParser(description='Run MIND pipeline')
    parser.add_argument("--subject",
                        required=True,
                        help="EID of the subject for which you want to run MIND")
    parser.add_argument("--data_dir",
                        required=True,
                        help="directory where you subject's data lives")
    parser.add_argument("--out_dir",
                        required=True,
                        help="director where you want your MIND data to live (if this pipeline is in test_mode that will be rewrite to your scratch dir")
    parser.add_argument("--projectname",
                        required=True,
                        help="the name of your project, which will be used to create the main/parent directory of your outputs")
    parser.add_argument("--parcellation",
                        choices=["aparc", "HCP.fsaverage.aparc", "500_sym.aparc", "HCP.coarse.fsaverage.aparc"],
                        required=True,
                        help="parcellation you wish to use")
    parser.add_argument("--feature_list_to_use",
                        required=True,
                        type=parse_list,
                        help="list of features to use (i.e., ['CT', 'FA', 'SD'] etc")
    parser.add_argument("--space",
                        required=True,
                        help="string identifying which space to use (i.e., 'native', 'fsaverage6' etc)")
    parser.add_argument("--micro",
                        action=argparse.BooleanOptionalAction,
                        required=True,
                        help="Set to True if you are using any microstructural data (--micro) or --no-micro for False")
    parser.add_argument("--resample",
                        action=argparse.BooleanOptionalAction,
                        required=True,
                        help="Set to True if you want to resample data (i.e., computing univariate MIND networks_")
    parser.add_argument("--return_qc",
                        action=argparse.BooleanOptionalAction,
                        required=True,
                        help="Set to True if you want to get your QC outputs and save them")
    parser.add_argument("--create_files",
                        action=argparse.BooleanOptionalAction,
                        default=False,
                        required=True,
                        help="Set to True if you want to create .mgz and common space (fsaverage6) files")
    parser.add_argument("--test_mode",
                        action=argparse.BooleanOptionalAction,
                        default=False,
                        required=True,
                        help="Set to True if you want to outputs to save out in scratch directory instead of main project directory")

    args = parser.parse_args()

    main_analysis(

        EID=args.subject,
        data_dir=args.data_dir,
        out_dir=args.out_dir,
        projectname=args.projectname,
        parcellation=args.parcellation,
        feature_list_to_use=args.feature_list_to_use,
        space=args.space,
        micro=args.micro,
        resample=args.resample,
        return_qc=args.return_qc,
        create_files=args.create_files,
        test_mode=args.test_mode

    )
