import logging
from pathlib import Path

# import esdglider.profiles as prof
# import numpy as np
import xarray as xr
from esdglider.slocum import pipeline

from esdglider import defaults, gcp, imagery, paths, plots, qartod

logger = logging.getLogger(__name__)

### Variables for user to update
deployment_name = "chovy-20261005"    # "amlr08-20220513"
mode = "delayed"        # "delayed" or "rt"
write_nc = True         # Write NC files?
sci_use_m_depth = False # Use m_depth for science depth?
prof_args = {
    "stall": 2
}          # Named optional parameters for finding profiles

### Consistent variables
home = Path.home()
mnt_path = home / "mnt-gcs"
logs_bucket_name = defaults.BUCKET_LOGS
logs_path = mnt_path / logs_bucket_name
file_info, log_file_name = paths.get_file_info(Path(__file__))


#------------------------------------------------------------------------------
if __name__ == "__main__":
    gcp.gcs_mount_bucket(logs_bucket_name, logs_path, ro=False)
    logging.basicConfig(
        filename=logs_path / log_file_name,
        filemode="w",
        format="%(name)s:%(asctime)s:%(levelname)s:%(message)s [line %(lineno)d]",
        level=logging.INFO,
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logging.captureWarnings(True)
    logger.info("Beginning scheduled processing for %s", file_info)
    print(f"Writing logs to {logs_path / log_file_name}")

    logger.info("Generating glider paths---------------------")
    glider_paths = paths.get_path_glider(
        deployment_name = deployment_name, 
        mode = mode, 
        home_path = home,
    )
    gcp.gcs_mount_bucket(defaults.BUCKET_DATA_IN, glider_paths["data_in_path"], ro=True)
    gcp.gcs_mount_bucket(defaults.BUCKET_DATA_OUT, glider_paths["data_out_path"], ro=False)

    #--------------------------------------------------------------------------
    ### Timeseries and gridded netCDF generation
    logger.info("Generating timeseries netCDF files---------------------")
    outname_dict_ts = pipeline.generate_timeseries(
        deployment_name = deployment_name, 
        mode = mode, 
        glider_paths=glider_paths,
        write_raw=write_nc,
        write_eng=write_nc,
        write_sci=write_nc,
        sci_use_m_depth=sci_use_m_depth, 
        file_info=file_info,
        binary_search="*.[de]bd", 
        prof_args=prof_args, 
    )

    # if write_nc:      #IF NECESSARY
    #     logger.info("Correcting data---------------------")
    #     # Recalculate flbbcd values and correct cdom
    #     pipeline.correct_flbbcd_raw_sci(glider_paths=glider_paths)
    #     pipeline.correct_cdom_raw_sci(glider_paths=glider_paths)

    if write_nc:      #IF NECESSARY
        logger.info("Adjusting datasets, after review---------------------")
        # Correct profile indices, and make other adjustments to netCDF files
        tsraw = xr.load_dataset(outname_dict_ts["outname_tsraw"])

        # Adjust profile index
        logger.info("Correcting profile_index for raw, eng, and sci datasets")
        tsraw["profile_index"].loc[
            {"time": slice("2026-10-18 08:00", "2026-10-18 09:30")}
        ] = 272.5
        tsraw["profile_index"].loc[
            {"time": slice("2026-10-09 04:55:00", "2026-10-09 04:57:11")}
        ] = 104.
        tsraw["profile_index"].loc[
            {"time": slice("2026-10-08 17:03:23.5", "2026-10-08 17:05")}
        ] = 95.

        pipeline.complete_profile_correction(
            tsraw=tsraw,
            tseng=xr.load_dataset(outname_dict_ts["outname_tseng"]),
            tssci=xr.load_dataset(outname_dict_ts["outname_tssci"]),
            glider_paths=glider_paths,
        )

    # Using science netCDF files, after any corrections:
    if write_nc:
        logger.info("Generating qc flags---------------------")
        qartod.run_qartod_qc(
            input_file=outname_dict_ts["outname_tssci"],
            output_file=outname_dict_ts["outname_tssci"],
            overwrite_qc=True
        )

    logger.info("Generating gridded netCDF files---------------------")
    outname_dict_gr = pipeline.generate_gridded(
        glider_paths=glider_paths,
        write_gridded=write_nc,
    )

    outname_dict = outname_dict_ts | outname_dict_gr


    # --------------------------------------------------------------------------
    ### Ancillary data products
    tssci = xr.load_dataset(outname_dict["outname_tssci"])
    
    logger.info("Imagery---------------------")
    img_paths = paths.get_path_imagery(deployment_name, home_path=home)
    gcp.gcs_mount_bucket(defaults.BUCKET_IMAGERY_META, img_paths["imagery_meta_path"], ro=True)
    imagery.imagery_timeseries(tssci, img_paths)


    #--------------------------------------------------------------------------
    ### Plots
    logger.info("Generating plots---------------------")
    etopo_path = home / "ETOPO_2022_v1_15s_N45W135_erddap.nc"
    plots.esd_all_plots(
        outname_dict,
        crs="Mercator",
        base_path=glider_paths["plotdir"],
        bar_file=str(etopo_path),
    )

    #--------------------------------------------------------------------------
    ### Profile files to the IOOS NGDAC
    if write_nc:    
        logger.info("Generating profile netCDF files---------------------")
        pipeline.create_ngdac_profiles(
            inname=outname_dict_ts["outname_tssci"],
            outdir=glider_paths["ngdacdir"],
            deploymentyaml=glider_paths["deploymentyaml"],
            force=True,
        )

    #--------------------------------------------------------------------------
    logger.info("Completed scheduled processing")
