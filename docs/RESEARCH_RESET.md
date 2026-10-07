# DAYS-BOT V5.0.6 — RESEARCH RESET

**Reset date:** 2026-10-07  
**Reset reason:** Infrastructure incident (GitHub API `?status=completed` filter bug)  
**Baseline run:** #823

---

## Incident Summary

Between 2026-10-05 and 2026-10-07, the cumulative DB chain was broken
by a GitHub Actions API bug:

- `?status=completed` filter returned runs from **2026-09-07** (#432)
  instead of the most recent runs.
- This caused runs #815 through #822 to start with a **fresh DB**.
- The DB chain was effectively broken for 3 trading days.

**The bug was fixed in #823** by:
- Removing `?status=completed` from the API URL
- Filtering `conclusion == "success"` in `jq` instead
- Iterating over the last 100 runs to find a valid `scan-*` artifact

**Verified in #823 log:**
