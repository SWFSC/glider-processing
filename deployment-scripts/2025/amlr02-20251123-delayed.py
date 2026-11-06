import logging
from pathlib import Path

# import esdglider.profiles as prof
# import numpy as np
import xarray as xr
from esdglider.slocum import core, pipeline

from esdglider import aa, defaults, gcp, paths, plots, qartod, utils

logger = logging.getLogger(__name__)

### Variables for user to update
deployment_name = "amlr02-20251123"    # "amlr08-20220513"
mode = "delayed"        # "delayed" or "rt"
write_nc = True         # Write NC files?
sci_use_m_depth = False # Use m_depth for science depth?
prof_args = {
    "shake": 8, 
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
        prof_args=prof_args, 
    )

    if write_nc:      #IF NECESSARY
        logger.info("Adjusting datasets, after review---------------------")

        # Drop specific bad points from the science and engineering timeseries
        tseng = xr.load_dataset(outname_dict_ts["outname_tseng"])
        tseng = tseng.drop_sel(time="2025-11-28 00:01:44.668548608")
        tseng.to_netcdf(
            outname_dict_ts["outname_tseng"], 
            encoding={'time': core.TIME_ENCODING}
        )

        tssci = xr.load_dataset(outname_dict_ts["outname_tssci"])
        tssci = tssci.drop_sel(time="2025-11-28 00:04:17.991211008")
        tssci.to_netcdf(
            outname_dict_ts["outname_tssci"], 
            encoding={'time': core.TIME_ENCODING}
        )
        utils.check_depth(tssci.depth, tseng.depth)

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

    logger.info("Active Acoustics---------------------")
    aa_paths = paths.get_path_aa(deployment_name, mode, home_path=home)
    aa.ancillary_echoview(tssci, aa_paths)


    # --------------------------------------------------------------------------
    ### Plots
    logger.info("Generating plots---------------------")
    plots.sci_surface_map_loop(
        xr.load_dataset(outname_dict["outname_gr5m"]),
        crs="Mercator",
        base_path=glider_paths["plotdir"],
        figsize_x=11,
        figsize_y=8.5,
    )
    plots.esd_all_plots(
        outname_dict, 
        crs=None, 
        base_path=glider_paths["plotdir"], 
    )

    #--------------------------------------------------------------------------
    # ### Profile files to the IOOS NGDAC
    # if write_nc:    
    #     logger.info("Generating profile netCDF files---------------------")
    #     pipeline.create_ngdac_profiles(
    #         inname=outname_dict_ts["outname_tssci"],
    #         outdir=glider_paths["ngdacdir"],
    #         deploymentyaml=glider_paths["deploymentyaml"],
    #         force=True,
    #     )

    #     logger.info("Syncing profile netCDF files to NGDAC---------------------")
    #     pipeline.sync_to_ngdac(
    #         local_dir=glider_paths["ngdacdir"], 
    #         dry_run=True, 
    #     )

    #--------------------------------------------------------------------------
    logger.info("Completed scheduled processing")
