import logging
from pathlib import Path

# import esdglider.profiles as prof
# import numpy as np
# import xarray as xr
from esdglider.slocum import pipeline, rt

from esdglider import aa, gcp, imagery, paths, plots, qartod

logger = logging.getLogger(__name__)

### Variables for user to update
deployment_name = ""    # "amlr08-20220513"
mode = "delayed"        # "delayed" or "rt"
write_nc = True         # Write NC files?
sci_use_m_depth = False # Use m_depth for science depth?
prof_args = {}          # Named optional parameters for finding profiles

### Consistent variables
home = Path.home()
mnt_path = home / "mnt-gcs"
logs_bucket_name = "swfscesd-glider-logs"
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
    gcp.gcs_mount_bucket(paths.data_in_bucket_name, glider_paths["data_in_path"], ro=True)
    gcp.gcs_mount_bucket(paths.data_out_bucket_name, glider_paths["data_out_path"], ro=False)

    #--------------------------------------------------------------------------
    # logger.info("Rsyncing nrt files from SFMC to GCP---------------------")
    # rt.scrape_sfmc(
    #     deployment_name=deployment_name, 
    #     bucket_name=paths.data_in_bucket_name, 
    #     sfmc_path=str(home / "sfmc"), 
    #     cache_path=glider_paths["cacdir"], 
    #     gcpproject_id="ggn-nmfs-swfscesd-prod-1", 
    #     secret_id="sfmc-swoodman"
    # )

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
        prof_args=prof_args, 
    )

    # # Recalculate flbbcd values and correct cdom, if necessary
    # if write_nc:
    #     logger.info("Correcting data---------------------")
    #     pipeline.correct_flbbcd_raw_sci(glider_paths=glider_paths)
    #     pipeline.correct_cdom_raw_sci(glider_paths=glider_paths)

    # # Correct profiles, and make other adjustments to netCDF files, if necessary
    # if write_nc:
    #     logger.info("Adjusting datasets, after review---------------------")
    #     tsraw = xr.load_dataset(outname_dict_ts["outname_tsraw"])

    #     # Adjust profile index
    #     logger.info("Correcting profile_index for raw, eng, and sci datasets")
    #     tsraw["profile_index"].loc[{"time": "2024-11-13 15:14:59"}] = 590.5
    #     tsraw["profile_index"].loc[
    #         {"time": slice("2026-02-01 09:05", "2026-02-01 09:16:10")}
    #     ] = 397

        # pipeline.complete_profile_correction(
        #     tsraw=tsraw,
        #     tseng=xr.load_dataset(outname_dict_ts["outname_tseng"]),
        #     tssci=xr.load_dataset(outname_dict_ts["outname_tssci"]),
        #     glider_paths=glider_paths,
        # )

    # # Create qc variables for science netCDF files, after corrections
    # if write_nc:
    #     logger.info("Generating qc flags---------------------")
    #     qartod.run_qartod_qc(
    #         input_file=outname_dict_ts["outname_tssci"],
    #         output_file=outname_dict_ts["outname_tssci"],
    #         overwrite_qc=True
    #     )

    # logger.info("Generating gridded netCDF files---------------------")
    # outname_dict_gr = pipeline.generate_gridded(
    #     glider_paths=glider_paths,
    #     write_gridded=write_nc,
    # )

    # outname_dict = outname_dict_ts | outname_dict_gr


    #--------------------------------------------------------------------------
    # ### Ancillary data products
    # tssci = xr.load_dataset(outname_dict["outname_tssci"])

    # logger.info("Active Acoustics---------------------")
    # aa_paths = paths.get_path_aa(deployment_name, mode, home_path=home)
    # aa.ancillary_echoview(tssci, aa_paths)
    
    # logger.info("Imagery---------------------")
    # img_paths = paths.get_path_imagery(deployment_name, home_path=home)
    # gcp.gcs_mount_bucket(paths.imagery_meta_bucket_name, img_paths["imagery_meta_path"], ro=True)
    # imagery.imagery_timeseries(tssci, img_paths)

    #--------------------------------------------------------------------------
    # ### Plots
    # logger.info("Generating plots---------------------")
    # etopo_path = home / "ETOPO_2022_v1_15s_N45W135_erddap.nc"
    # plots.esd_all_plots(
    #     outname_dict,
    #     crs="Mercator",
    #     base_path=glider_paths["plotdir"],
    #     bar_file=str(etopo_path),
    # )
    # ## OR, for Antarctic ##
    # plots.esd_all_plots(
    #     outname_dict, 
    #     crs=None, 
    #     base_path=glider_paths["plotdir"], 
    # )
    # plots.sci_surface_map_loop(
    #     xr.load_dataset(outname_dict["outname_gr5m"]),
    #     crs="Mercator",
    #     base_path=glider_paths["plotdir"],
    #     figsize_x=11,
    #     figsize_y=8.5,
    # )

    # --------------------------------------------------------------------------
    # ### Generate profile netCDF files for the DAC
    # pipeline.create_ngdac_profiles(
    #     inname=outname_dict["outname_tssci"],
    #     outdir=glider_paths["ngdacdir"],
    #     deploymentyaml=glider_paths["deploymentyaml"],
    #     force=True,
    # )

    #--------------------------------------------------------------------------
    logger.info("Completed scheduled processing")
