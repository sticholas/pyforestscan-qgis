# Batch Recovery Identity

Every new preflight creates a unique timestamped batch folder. It does not scan the output root and adopt the newest manifest. Historical completion is considered only when a caller explicitly supplies a batch folder for recovery.

Compatible recovery must bind source identity and metadata, requested products and parameters, grid/HAG strategy, execution plan, and output identity. Filename or output existence alone is insufficient. Phase 30D fixes unrelated historical counts; full signature-based recovery comparison remains a hardening item.
