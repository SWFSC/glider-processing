import logging
import os
from pathlib import Path

import numpy as np
import xarray as xr
from esdglider.slocum import pipeline

from esdglider import defaults, gcp, imagery, paths, plots, qartod

logger = logging.getLogger(__name__)

# Variables for user to update. All other deployment info is in the yaml file
deployment_name = "amlr01-20241120"
mode = "delayed"
write_nc = True
prof_args = {
    "stall": 15
} # Named optional parameters for finding profiles

### Consistent variables
home = Path.home()
logs_bucket_name = "swfscesd-glider-logs"
logs_path = home / "mnt-gcs" / logs_bucket_name
file_info, log_file_name = paths.get_file_info(Path(__file__))

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

    # Generate glider paths
    logger.info("Generating glider paths")
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
        mode=mode, 
        glider_paths=glider_paths,
        write_raw=write_nc,
        write_eng=write_nc,
        write_sci=write_nc,
        file_info=file_info,
        # binary_search="*.[de]cd", 
        prof_args=prof_args,
    )

    if write_nc:
        logger.info("Adjusting datasets, after review---------------------")
        # Correct profile indices, and make other adjustments to netCDF files
        tsraw = xr.load_dataset(outname_dict_ts["outname_tsraw"])
        tseng = xr.load_dataset(outname_dict_ts["outname_tseng"])
        tssci = xr.load_dataset(outname_dict_ts["outname_tssci"])

        logger.info("Correcting profile_index for raw, eng, and sci datasets")
        # Remove a particular timestamp, and rerun profile calculations
        # This timestamp was breaking profile calculations, and parameters
        # could not be tuned to handle both this timestamp and rest of data
        # We run eng and sci timeseries through this function as well for simplicity
        time_toremove = "2024-12-13 03:24:07.488281344"
        tsraw = glider.drop_ts_ranges(
            tsraw, 
            drop_list=[(time_toremove, time_toremove)], 
            dstype="raw", 
            profsummdir=paths["profsummpath"], 
            outname=outname_dict["outname_tsraw"], 
            stall = stall_int,
        )
        logging.info("eng")
        tseng = glider.drop_ts_ranges(
            tseng, 
            drop_list=[(time_toremove, time_toremove)], 
            dstype="eng", 
            profsummdir=paths["profsummpath"], 
            outname=outname_dict["outname_tseng"], 
        )
        logging.info("sci")
        tssci = glider.drop_ts_ranges(
            tssci, 
            drop_list = [(time_toremove, time_toremove)], 
            dstype="sci", 
            profsummdir=paths["profsummpath"], 
            outname=outname_dict["outname_tssci"], 
        )

        # time_toremove = np.datetime64("2024-12-13 03:24:07.488281344")
        # logging.info(
        #     "Dropping %s points from the raw dataset, for profile calcs", 
        #     np.count_nonzero(tsraw.time.values == time_toremove)
        # )

        # # Calculate new profiles for raw dataset
        # tsraw = tsraw.sel(time=(tsraw.time != time_toremove))
        # tsraw = utils.get_fill_profiles(tsraw, tsraw.time.values, tsraw.depth.values, **kwargs)
        # prof_summ = utils.calc_profile_summary(tsraw)
        # prof_summ.to_csv(paths["profsummpath"], index=False)

        # 'Calculate', ie join, profiles for eng and sci timeseries
        # tseng = utils.join_profiles(tseng, prof_summ, **kwargs)
        # tssci = utils.join_profiles(tssci, prof_summ, **kwargs)

        # # Profile checks
        # utils.check_profiles(tsraw)
        # utils.check_profiles(tseng)
        # utils.check_profiles(tssci)

        # # Write to Netcdf, and rerun gridding
        # logging.info("Write timeseries to netcdf")
        # utils.to_netcdf_esd(tsraw, outname_dict["outname_tsraw"])
        # utils.to_netcdf_esd(tseng, outname_dict["outname_tseng"])
        # utils.to_netcdf_esd(tssci, outname_dict["outname_tssci"])
        del tsraw, tssci, tseng

        logging.info("Gridding corrected science data")
        outname_dict = glider.binary_to_nc(
            deployment_info=deployment_info,
            paths=paths,
            write_raw=False,
            write_timeseries=False,
            write_gridded=True,
            file_info=file_info,
        )        

    plots.esd_all_plots(outname_dict, crs=None, base_path=paths["plotdir"])
    plots.sci_surface_map_loop(
        xr.load_dataset(outname_dict["outname_gr5m"]),
        crs="Mercator",
        base_path=paths["plotdir"],
        figsize_x=11,
        figsize_y=8.5,
    )

    ### Sensor-specific processing
    tssci = xr.load_dataset(outname_dict["outname_tssci"])

    # Acoustics
    a_paths = acoustics.get_path_acoustics(deployment_info, acoustics_path)
    acoustics.echoview_metadata(tssci, a_paths)

    # Imagery
    # i_paths = imagery.get_path_imagery(deployment_info, imagery_raw_path)
    # imagery.imagery_timeseries(tssci, i_paths)

    # ### Generate profile netCDF files for the DAC
    # glider.ngdac_profiles(
    #     outname_dict["outname_tssci"], 
    #     paths['profdir'], 
    #     paths['deploymentyaml'],
    #     force=True, 
    # )

    logging.info("Completed scheduled processing")
