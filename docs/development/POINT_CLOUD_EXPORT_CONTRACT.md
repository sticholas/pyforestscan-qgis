# Point cloud export contract

Design contract; no export executor exists in 34A1.

Export must run in the existing verified managed engine, using hidden clean
subprocesses, into a distinct NEW destination. Reject samefile aliases,
source overwrite and unsupported format/class combinations. Verify source
identity immediately before and after. Do not mark success if either fails.

Resolve journal membership against ORIGINAL full-resolution attributes, apply
operations in order, and validate resulting point count, bounds, CRS, untouched
dimensions, classification, Extra Bytes, RGB, GPS time, returns and VLRs.
LAS legacy formats cannot represent every 0-255 class without format changes.

PDAL writer forwarding is an option, not proof of byte/metadata preservation.
Validate a temporary output before publishing it. Persist provenance and only
then enable an explicit Use Export in Process request. Failure/cancel leaves
no apparently complete output. EPT immutability proof is a separate blocker.
