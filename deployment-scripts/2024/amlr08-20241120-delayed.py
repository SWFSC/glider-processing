import logging
from pathlib import Path

import numpy as np
import xarray as xr
from esdglider.slocum import pipeline

from esdglider import aa, defaults, gcp, paths, plots, qartod

logger = logging.getLogger(__name__)

# Variables for user to update. All other deployment info is in the yaml file
deployment_name = "amlr08-20241120"
mode = "delayed"
write_nc = True
prof_args = {} # Named optional parameters for finding profiles

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
        binary_search="*.[de]cd", 
        prof_args=prof_args,
    )

    if write_nc:      #IF NECESSARY
        logger.info("Correcting data---------------------")
        # Recalculate flbbcd values and correct cdom
        pipeline.correct_flbbcd_raw_sci(glider_paths=glider_paths)
        pipeline.correct_cdom_raw_sci(glider_paths=glider_paths)

    ### Because the glider errored, need to handle the last profile
    if write_nc:
        logger.info("Adjusting timeseries datasets, after review")
        tsraw = xr.load_dataset(outname_dict_ts["outname_tsraw"])
        tseng = xr.load_dataset(outname_dict_ts["outname_tseng"])
        tssci = xr.load_dataset(outname_dict_ts["outname_tssci"])

        # Adjust profile index
        logger.info("Removing bogus time values from after glider was recovered")
        max_time = np.datetime64("2024-11-25")
        logger.info("Num of points dropped for raw, eng, and sci:")
        for i in [tsraw, tseng, tssci]:
            logger.info(np.count_nonzero(i.time > max_time))
        
        tsraw = tsraw.sel(time=tsraw.time < max_time)
        tseng = tseng.sel(time=tseng.time < max_time)

        logger.info("Correcting profile_index for raw and eng datasets")
        time_slice = slice("2024-11-24 11:00", "2024-11-25")
        prof_last = np.max(tsraw.profile_index.values)
        tsraw["profile_index"].loc[{ "time": time_slice }] = prof_last
        # tseng["profile_index"].loc[{ "time": time_slice }] = prof_last
        pipeline.complete_profile_correction(
            tsraw=tsraw,
            tseng=tseng,
            tssci=tssci,
            glider_paths=glider_paths,
        )
        del tsraw, tssci, tseng

        # prof_summ = utils.calc_profile_summary(tsraw, "depth_measured")
        # prof_summ.to_csv(paths["profsummpath"], index=False)
        # utils.check_profiles(prof_summ)

        # # Profile checks
        # logging.info("engineering and science profile checks")
        # utils.check_profiles(utils.calc_profile_summary(tseng, "depth"))
        # utils.check_profiles(utils.calc_profile_summary(tssci, "depth"))

        # # Write to Netcdf, and rerun gridding
        # logging.info("Write raw and eng timeseries to netcdf")
        # utils.to_netcdf_esd(tsraw, outname_dict["outname_tsraw"])
        # utils.to_netcdf_esd(tseng, outname_dict["outname_tseng"])
        # del prof_summ, tsraw, tssci, tseng

        # logging.info(
        #     "Original gridded data is ok because no changes to sci timeseries"
        # )

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

    #--------------------------------------------------------------------------
    ### Ancillary data products
    tssci = xr.load_dataset(outname_dict["outname_tssci"])

    logger.info("Active Acoustics---------------------")
    aa_paths = paths.get_path_aa(deployment_name, mode, home_path=home)
    aa.ancillary_echoview(tssci, aa_paths)

    # --------------------------------------------------------------------------
    ### Plots
    logger.info("Generating plots---------------------")
    plots.esd_all_plots(
        outname_dict, 
        crs="Mercator",
        base_path=glider_paths["plotdir"],
        figsize_x=11,
        figsize_y=8.5,
    )

    #--------------------------------------------------------------------------
    ### Profile files to the IOOS NGDAC
    # if write_nc:    
    #     logger.info("Generating profile netCDF files---------------------")
    #     pipeline.create_ngdac_profiles(
    #         inname=outname_dict_ts["outname_tssci"],
    #         outdir=glider_paths["ngdacdir"],
    #         deploymentyaml=glider_paths["deploymentyaml"],
    #         force=True,
    #     )

    # --------------------------------------------------------------------------
    logger.info("Completed scheduled processing")
    