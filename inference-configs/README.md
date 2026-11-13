# Inference Configuration YAML files

This directory is meant to store the YAML files which are used for running [the imagery pipeline](https://github.com/SWFSC/esdglider/blob/57f349ddb22808d5ec548e4e469758f9a92532fa/docs/imagery-pipeline.md).

Store the authored YAML here and pass its path to the pipeline's `--config`
option. Commit and push it normally; the pipeline does not automate GitHub
uploads or commits.

Each new live submission to the imagery pipeline automatically stores
the exact YAML and resolved local configuration in GCS, along with snapshots
of the selected manifests and pipeline YAML:

```text
gs://{output_bucket}/SWFSC/glider/{deployment_name}/runs/{run_id}/config/
gs://{output_bucket}/SWFSC/glider/{deployment_name}/runs/{run_id}/manifests/
gs://{output_bucket}/SWFSC/glider/{deployment_name}/runs/{run_id}/outputs/{chunk_number:02d}/
```

The run ID contains a UTC timestamp and UUID. Archive writes are create-only
at the application level; the bucket does not enforce immutability. Use the
printed run ID with `--resume-run-id` to resume DAG submission without rewriting
the archive or regenerating metadata.
