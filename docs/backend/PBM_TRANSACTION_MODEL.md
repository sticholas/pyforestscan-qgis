# PBM Transaction Model

Phase 22D moves backend installation from a linear prototype to a transaction model. The transaction engine is designed so a failed install does not leave an activated partial backend.

## Stages

1. DOWNLOAD
2. VERIFY
3. EXTRACT
4. CREATE ENVIRONMENT
5. INSTALL PACKAGES
6. VERIFY PACKAGES
7. WRITE CONFIG
8. PROMOTE BACKEND
9. READY

The transaction writes only inside the user-local PBM backend root. It does not modify QGIS Python, QGIS installation folders, shell profiles, PATH, or global environment variables.

## Rollback

If a stage fails or cancellation is requested, PBM removes staging files and reports the stage that failed. Logs remain available under the backend logs directory when logging has already been initialized.

## Public Activation

The transaction engine exists for production readiness, but public one-click installation remains disabled until release checksum pins, platform testing, and upgrade policy are complete.
