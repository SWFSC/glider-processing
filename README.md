# glider-processing

Repository of the Ecosystem Science Division (ESD) glider lab at the Southwest Fisheries Science Center (SWFSC), for processing glider data. 

See the [glider lab manual](https://swfsc.github.io/glider-lab-manual) for more in-depth info.

## Directories

### deployment-configs

Deployment config files, for each deployment. These yaml files are used during data processing by [esdglider](https://github.com/SWFSC/esdglider). These files are typically created by first using esdglider's [generate-deployment_yaml](https://github.com/SWFSC/esdglider/blob/main/esdglider/config.py) to make a file with the basic info, and then editing that file (e.g., adding the comment and summary blocks) by hand.

### deployment-reports

ESD glider deployment reports, created as Quarto documents. See the readme in this folder for more details.

### deployment-scripts

Scripts used for processing data from glider deployments. Typically, these scripts are run on GCP workstations to create netCDF files from the delayed binary data after a glider has been recovered, apply any corrections, and format the files as needed to make them publicly available.

## Disclaimer

This repository is a scientific product and is not official communication of the National Oceanic and Atmospheric Administration, or the United States Department of Commerce. All NOAA GitHub project code is provided on an ‘as is’ basis and the user assumes responsibility for its use. Any claims against the Department of Commerce or Department of Commerce bureaus stemming from the use of this GitHub project will be governed by all applicable Federal law. Any reference to specific commercial products, processes, or services by service mark, trademark, manufacturer, or otherwise, does not constitute or imply their endorsement, recommendation or favoring by the Department of Commerce. The Department of Commerce seal and logo, or the seal and logo of a DOC bureau, shall not be used in any manner to imply endorsement of any commercial product or activity by DOC or the United States Government.
