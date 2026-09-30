# DAYS-BOT V5.0.6 — PRE-REGISTRATION

**Status:** FROZEN  
**Freeze date:** 2026-09-30  
**Author:** rank1984  
**Scope:** Research protocol for the Gap-and-Go hypothesis.

---

## 0. Purpose

This document is a **pre-registration** for a research study
testing whether a specific intraday trading pattern produces
a positive expected Net R.

It is written **before** any Event is counted. It cannot be
modified after the first Event is recorded. Any modification
invalidates the study and requires a new pre-registration
with a new dataset.

---

## 1. Hypothesis

**Primary hypothesis (H1):**

> A stock that:
> 1. passed Discovery filters, and
> 2. broke the PM High (PMH) with volume confirmation,
>     in the 09:30–11:00 ET window,
> produces **mean Net R > 0** after spread, slippage, and
> commissions, under the fixed entry/stop/target rules
> defined below.

**Null hypothesis (H0):**

> The mean Net R for the same population is ≤ 0.

This is a **one-sided test**. We are not testing whether the
pattern "works sometimes". We are testing whether the
expected value is positive.

---

## 2. Frozen Parameters (15)

### P1 — PMH Definition

- **PMH** = the highest High of 1-minute bars in the
  premarket session.
- **Session window:** 04:00:00 – 09:29:59 ET.
- **09:30:00 ET** is **not** included (it belongs to RTH).
- **Source:** `snapshots.pm_high`, populated by the
  scanner during the PM window.

### P2 — PMH Freeze

- PMH is frozen at **09:30:00 ET**.
- No recalculation from RTH data.
- Enforcement: evaluator reads `snapshot.pm_high` and
  never recomputes it.
- If `snapshot.pm_high IS NULL` → **no Event**.

### P3 — Trigger Window

- Triggers are evaluated **only** in the window:
- **09:30:00 – 11:00:00 ET**.
- Any trigger timestamp outside this window is
  **not eligible** to become an Event.
- Rationale: Gap-and-Go is defined by the first
  90 minutes of Regular Trading Hours.

### P4 — Trigger Definition (BREAKOUT_VOLUME_V1)

A trigger fires on bar **N** at time **t_N** if and only if:

1. `Close_N ≥ PMH + buffer`, where  
   `buffer = max(2 ticks, 0.05 × ATR)`.
2. `Volume_N ≥ 1.2 × median(Volume of 5 valid bars
   immediately before N)`.

**Valid bars** are 1-minute bars with
`Volume > 0` and non-null OHLC.

### P5 — Volume Availability

- At least **3 out of the 5 immediately preceding bars**
  must be valid.
- If fewer than 3 valid bars exist before N
  (e.g., N is one of the first RTH bars),
  the volume confirmation is **VOLUME_UNAVAILABLE**,
  and **no Event** is created from that bar.

### P6 — VWAP Anchor

- The VWAP used in stop calculation is
  **`snapshot.pm_vwap`**.
- **RTH VWAP is not used** anywhere in the trigger,
  stop, or Net R calculation.
- If `snapshot.pm_vwap IS NULL` → **no Event**.

### P7 — Entry Fill

- If a trigger fires on bar N, entry is executed on
  bar **N+1 at its Open**.
- **Slippage applied:** `+ (spread/2) + 1 tick`.
- If bar N+1 does not exist within the same RTH
  session → **NON_EXECUTABLE**, no Event.
- If bar N+1 Open > (trigger Close + chase_cap) →
  **NON_EXECUTABLE**, no Event.

### P8 — Stop
