import logging
from pathlib import Path

# import numpy as np
import xarray as xr
from esdglider.slocum import pipeline

from esdglider import gcp, imagery, paths, plots, qartod

logger = logging.getLogger(__name__)

### Variables for user to update
deployment_name = "amlr30-20260114"
mode = "delayed"
write_nc = True
prof_args = {
    "shake": 15,
    "interrupt": 500,
    "length": 16,
}

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
        prof_args=prof_args,     )

    if write_nc:
        tsraw = xr.load_dataset(outname_dict_ts["outname_tsraw"])
        # tseng = xr.load_dataset(outname_dict_ts["outname_tseng"])
        # tssci = xr.load_dataset(outname_dict_ts["outname_tssci"])

        # Adjust profile index
        logger.info("Correcting profile_index for raw, eng, and sci datasets")
        # tssci["profile_index"].loc[dict(time="2024-11-13 15:14:59")] = 590.5
        tsraw["profile_index"].loc[
            {"time": slice("2026-02-01 09:05", "2026-02-01 09:16:10")}
        ] = 397
        tsraw["profile_index"].loc[
            {"time": slice("2026-01-24 00:03:07", "2026-01-24 00:04:10")}
        ] = 167
        tsraw["profile_index"].loc[
            {"time": slice("2026-01-25 01:51", "2026-01-25 01:55")}
        ] = 182
        
        pipeline.complete_profile_correction(
            tsraw=tsraw,
            tseng=xr.load_dataset(outname_dict_ts["outname_tseng"]),
            tssci=xr.load_dataset(outname_dict_ts["outname_tssci"]),
            glider_paths=glider_paths,
        )
        logger.info("Completed adjustments")

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
    plots.esd_all_plots(
        outname_dict, 
        crs=None, 
        base_path=glider_paths["plotdir"], 
    )
    plots.sci_surface_map_loop(
        xr.load_dataset(outname_dict["outname_gr5m"]),
        crs="Mercator",
        base_path=glider_paths["plotdir"],
        figsize_x=11,
        figsize_y=8.5,
    )

    #--------------------------------------------------------------------------
    ### Generate profile netCDF files for the DAC
    pipeline.create_ngdac_profiles(
        inname=outname_dict["outname_tssci"],
        outdir=glider_paths["ngdacdir"],
        deploymentyaml=glider_paths["deploymentyaml"],
        force=True,
    )

    #--------------------------------------------------------------------------
    logger.info("Completed scheduled processing")
