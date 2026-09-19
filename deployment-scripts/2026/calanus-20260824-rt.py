import logging

# import numpy as np
# import xarray as xr
from pathlib import Path

from esdglider.slocum import pipeline, rt

from esdglider import gcp, paths, plots, qartod, utils

logger = logging.getLogger(__name__)

### Variables for user to update
deployment_name = "calanus-20260824"
mode = "rt"
write_nc = True         # Write NC files?
sci_use_m_depth = False # Use m_depth for science depth?
prof_args = {}          # Named optional parameters for finding profiles

### Consistent variables
home = Path.home()
logs_bucket_name = "swfscesd-glider-logs"
logs_path = home / "mnt-gcs" / logs_bucket_name
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

    logger.info("Generating glider paths")
    glider_paths = paths.get_path_glider(
        deployment_name = deployment_name, 
        mode = mode, 
        home_path = home,
    )
    gcp.gcs_mount_bucket(paths.data_in_bucket_name, glider_paths["data_in_path"], ro=True)
    gcp.gcs_mount_bucket(paths.data_out_bucket_name, glider_paths["data_out_path"], ro=False)

    logger.info("Rsyncing nrt files from SFMC to GCP---------------------")
    rt.scrape_sfmc(
        deployment_name, 
        "swfscesd-glider-deployments-data-in", 
        "/home/user/sfmc", 
        "ggn-nmfs-swfscesd-prod-1", 
        "sfmc-swoodman"
    )

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
        file_info=file_info,
        run_checks=False, 
        #prof_args=prof_args, 
    )

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

    # Create qc variables for science netCDF files, after corrections
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
    ### Generate profile netCDF files for the DAC
    utils.create_ngdac_profiles(
        inname=outname_dict["outname_tssci"],
        outdir=glider_paths["ngdacdir"],
        deploymentyaml=glider_paths["deploymentyaml"],
        force=True,
    )

    #--------------------------------------------------------------------------
    logger.info("Completed scheduled processing")
