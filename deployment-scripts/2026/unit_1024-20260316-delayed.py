import logging
from pathlib import Path

import xarray as xr
from esdglider.slocum import pipeline

from esdglider import gcp, imagery, paths, plots, qartod, utils

logger = logging.getLogger(__name__)

### Variables for user to update
deployment_name = "unit_1024-20260316"
mode = "delayed"
write_nc = True

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

    # Generate glider paths
    logger.info("Generating glider paths")
    glider_paths = paths.get_path_glider(
        deployment_name = deployment_name, 
        mode = mode, 
        home_path = home,
    )
    gcp.gcs_mount_bucket(paths.data_in_bucket_name, glider_paths["data_in_path"], ro=True)
    gcp.gcs_mount_bucket(paths.data_out_bucket_name, glider_paths["data_out_path"], ro=False)


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
        binary_search="*.[de]cd", 
    )

    # Recalculate flbbcd values and correct cdom, if necessary
    if write_nc:
        logger.info("Correcting data---------------------")
        pipeline.correct_cdom_raw_sci(glider_paths=glider_paths)

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
    ### Ancillary data products
    tssci = xr.load_dataset(outname_dict["outname_tssci"])

    logger.info("Imagery---------------------")
    img_paths = paths.get_path_imagery(deployment_name, home_path=home)
    gcp.gcs_mount_bucket(paths.imagery_meta_bucket_name, img_paths["imagery_meta_path"], ro=True)
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
    ### Generate profile netCDF files for the DAC
    utils.create_ngdac_profiles(
        inname=outname_dict["outname_tssci"],
        outdir=glider_paths["ngdacdir"],
        deploymentyaml=glider_paths["deploymentyaml"],
        force=True,
    )

    #--------------------------------------------------------------------------
    logger.info("Completed scheduled processing")