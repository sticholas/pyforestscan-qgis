# Troubleshooting Processing Jobs

Use **Validate Processing Request** before a long polygon EPT run when something looks suspicious. The check verifies the PBM backend contract, EPT metadata, requested bounds, polygon file, CRS, output folder, and product settings before a full product is generated.

For EPT jobs, valid bounds must use square-bracket coordinate ranges when converted for PDAL:

```text
([xmin, xmax], [ymin, ymax])
```

If a job fails, open the job folder and inspect `diagnostics/`. The most useful files are `summary.json`, `request_validation.json`, `backend_contract.json`, `pyforestscan_arguments.json`, and `traceback.txt`.

**Test Spatial Read** is a troubleshooting-only concept. It should be run explicitly when request validation passes but the EPT reader still fails. It is not part of normal preflight because it touches the EPT source.

**Diagnostic Test Run** means validating the request and, optionally, probing the reader without generating a full CHM or other product.

Support summaries should include product, failed stage, error code, request bounds, backend versions, and the diagnostic bundle path. They should not include credentials or raw environment dumps.
