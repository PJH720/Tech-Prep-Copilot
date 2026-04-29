# Secret Scanning Incident Response

This document tracks the response for GitHub secret-scanning alert #1.

## Alert Summary

- Source: `https://github.com/PJH720/Tech-Prep-Copilot/security/secret-scanning/1`
- Type: Twilio Account SID pattern
- Detected value: `ACf084584be7dcabfd0187d15b05b95817`
- Detected location: `chroma_db/chroma.sqlite3`
- First detected commit: `d159feb1a032cbcdb3c0dd997dcf41d1c85b396f`

## Scope Verification (Completed)

- Searched repository text files for the detected SID and Twilio credentials.
- Confirmed no direct `TWILIO_AUTH_TOKEN` or Twilio API key in tracked source files.
- Confirmed alert origin is a tracked binary artifact (`chroma_db/chroma.sqlite3`).

## Immediate Containment Runbook

If this SID is part of a real Twilio account, execute the steps below in order:

1. Rotate credentials before revocation if active workloads depend on them.
2. Revoke compromised credentials in Twilio Console.
3. Update runtime secrets in deployment environments (not in git).
4. Validate that services function with rotated credentials.
5. Review Twilio usage logs for suspicious activity:
   - Unknown source IPs
   - Unexpected SMS/call spikes
   - Unknown destination regions/numbers

## Repository Remediation (Completed)

- `chroma_db/chroma.sqlite3` is no longer tracked in git.
- `chroma_db/` is now ignored via `.gitignore`.
- LFS tracking for `chroma_db/chroma.sqlite3` was removed from `.gitattributes`.

## Alert Closure Guide

Close the GitHub alert using one of the outcomes below:

- `revoked`: if the detected secret was real and has been rotated/revoked.
- `false_positive`: if the detected value is not a live credential.

Recommended evidence to record before closure:

- Twilio console screenshot or audit log proving rotation/revocation
- Timestamp and actor who performed credential changes
- Brief summary of log review result (suspicious activity found/not found)

## Prevention Controls (Completed in repo)

- Added CI secret scanning workflow:
  - `.github/workflows/secret-scan.yml`
  - Uses `gitleaks/gitleaks-action@v2` on push/PR
- Binary/vector DB artifacts are now excluded from source control.
