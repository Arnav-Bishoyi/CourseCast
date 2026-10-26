"""Evaluation utilities for CourseCast "stays open until the ticket" forecasts.

Target (v1, proposed): for a section that is OPEN at forecast origin t0 and a ticket
time T = t0 + h, y = 1 if the section was observed continuously open over (t0, T]
and y = 0 if a closed observation appears in (t0, T]. "Open at T after a reopening"
is a different target and is computed separately (``y_open_at_ticket``) so the team
can compare them. See the Week 2 notebook for the full definitions.

Everything here uses integer *hour indices* (hours since the Unix epoch) internally.
Nothing in this module reads real data; the toy simulator at the bottom is the only
data source and is labelled as toy everywhere it is used.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

# Sources that tell us only the *current* status, not when it changed. They must not
# be used to estimate past closure timing or rates.
ARCHIVED_SOURCES = frozenset({"archived", "frozen", "archive", "current_snapshot"})


# --------------------------------------------------------------------------- inputs
def trusted_only(obs: pd.DataFrame, allow_demo: bool = False) -> pd.DataFrame:
    """Drop rows that cannot support timing estimates.

    Removes archived/frozen sources and (unless ``allow_demo``) demo/synthetic rows.
    Expects optional columns ``source`` and ``is_demo``.
    """
    keep = pd.Series(True, index=obs.index)
    if "source" in obs:
        keep &= ~obs["source"].isin(ARCHIVED_SOURCES)
    if "is_demo" in obs and not allow_demo:
        keep &= ~obs["is_demo"].astype(bool)
    return obs[keep]


def to_panel(obs: pd.DataFrame) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """obs[section, observed_at, status] -> {section: (hours, is_open)}.

    Status must be 'open' or 'closed'. Unknown/failed fetches should simply be absent
    from ``obs`` (never recoded as closed). Multiple observations within one hour
    keep the last one.
    """
    df = obs[obs["status"].isin(["open", "closed"])].copy()
    # unit-agnostic (pandas may store datetime64 as ns or us)
    df["hour"] = ((pd.to_datetime(df["observed_at"], utc=True) - pd.Timestamp(0, tz="UTC"))
                  // pd.Timedelta(hours=1)).astype("int64")
    panel = {}
    for sec, g in df.sort_values("hour").groupby("section"):
        g = g.drop_duplicates("hour", keep="last")
        panel[sec] = (g["hour"].to_numpy(), (g["status"] == "open").to_numpy())
    return panel


# --------------------------------------------------------------------------- labels
def build_labels(panel, horizons, origin_step=1, max_gap_hours=3, data_end=None) -> pd.DataFrame:
    """One row per (section, origin, horizon) for origins observed open.

    Columns
      y_cont            1 = continuously open through T, 0 = a closed observation in (t0, T],
                        NaN = censored (outcome not determinable from the observations)
      resolved_at       hour index when y_cont became known (closure hour, or T)
      censor_reason     '' | 'gap' (observation gap > max_gap_hours hid the interval)
                        | 'end' (data ended before T)
      y_open_at_ticket  status at T (nearest observation within max_gap_hours), NaN if unknown
      reopened          True when a closed observation is followed by open at T (the case
                        where the two targets disagree)

    A closed observation settles y_cont=0 even across a gap (the section was not
    continuously open). An open-open pair separated by more than ``max_gap_hours`` is
    NOT evidence of continuity (it could have closed and reopened unseen) -> censored.
    """
    rows = []
    for sec, (hrs, is_open) in panel.items():
        last_hour = hrs[-1] if data_end is None else data_end
        origins = np.flatnonzero(is_open)[::origin_step]
        for i in origins:
            t0 = hrs[i]
            for h in horizons:
                T = t0 + h
                j_end = np.searchsorted(hrs, T, side="right")  # obs in (t0, T] are i+1 .. j_end-1
                seg_o = is_open[i + 1:j_end]
                seg_h = hrs[i + 1:j_end]
                y = np.nan; resolved = np.nan; reason = ""
                closed_idx = np.flatnonzero(~seg_o)
                if closed_idx.size:
                    y, resolved = 0.0, float(seg_h[closed_idx[0]])
                else:
                    pts = np.concatenate(([t0], seg_h, [T]))
                    if T > last_hour:
                        reason = "end"
                    elif np.diff(pts).max() > max_gap_hours:
                        reason = "gap"
                    else:
                        y, resolved = 1.0, float(T)
                # target B: state at the ticket, plus whether a closure occurred first
                k = np.searchsorted(hrs, T)  # first obs >= T
                cand = [c for c in (k - 1, k) if 0 <= c < len(hrs) and abs(hrs[c] - T) <= max_gap_hours]
                y_t = np.nan
                if cand:
                    c = min(cand, key=lambda c: abs(hrs[c] - T))
                    y_t = float(is_open[c])
                reopened = bool(closed_idx.size and y_t == 1.0)
                rows.append((sec, t0, h, y, resolved, reason, y_t, reopened))
    return pd.DataFrame(rows, columns=["section", "origin", "horizon", "y_cont", "resolved_at",
                                       "censor_reason", "y_open_at_ticket", "reopened"])


# ------------------------------------------------------------------------ baseline
@dataclass
class ConstantHazard:
    """Single open->closed hazard per hour, shared by all sections and horizons."""
    rate: float
    events: int
    exposure_hours: float

    def predict(self, horizon_hours) -> np.ndarray:
        """P(remain continuously open for h hours | open now) = exp(-rate * h)."""
        return np.exp(-self.rate * np.asarray(horizon_hours, dtype=float))


def fit_constant_hazard(panel, cutoff_hour, max_gap_hours=3, prior_events=0.5, prior_hours=0.0) -> ConstantHazard:
    """Estimate hazard = closures / open-exposure-hours using ONLY transitions fully
    observed at or before ``cutoff_hour`` (the forecast origin).

    Each consecutive observation pair (a, b) with a open and b-a <= max_gap_hours adds
    (b-a) exposure hours, and one event if b is closed. Longer gaps are skipped (they
    could hide close+reopen), which avoids guessing about unobserved time. A small
    pseudo-count keeps the rate above zero when a pilot has seen no closures.
    """
    ev = 0; exp = 0.0
    for hrs, is_open in panel.values():
        m = np.searchsorted(hrs, cutoff_hour, side="right")
        h, o = hrs[:m], is_open[:m]
        if len(h) < 2:
            continue
        dt = np.diff(h)
        ok = o[:-1] & (dt <= max_gap_hours)
        exp += dt[ok].sum()
        ev += int((ok & ~o[1:]).sum())
    return ConstantHazard((ev + prior_events) / (exp + prior_hours + 1e-9), ev, float(exp))


# -------------------------------------------------------------------- rolling splits
@dataclass
class Fold:
    train_cutoff: int   # train labels/hazard may use outcomes known by this hour
    val_range: tuple    # origins in [lo, hi) used to fit calibration (earlier than test)
    val_cutoff: int     # hazard used for validation predictions is fit up to here
    test_range: tuple   # origins in [lo, hi)


def rolling_folds(first_test_start, last_origin, test_window, val_window, step=None) -> list[Fold]:
    """Expanding-window, time-ordered folds. For each fold:
        hazard for TEST   fit on data <= test_start
        calibrator        fit on validation origins [test_start - val_window, test_start),
                          whose hazard was fit on data <= test_start - val_window
        TEST origins      [test_start, test_start + test_window)
    """
    step = step or test_window
    folds, s = [], first_test_start
    while s + test_window <= last_origin + 1:
        folds.append(Fold(s, (s - val_window, s), s - val_window, (s, s + test_window)))
        s += step
    return folds


def known_by(labels: pd.DataFrame, cutoff: int) -> pd.DataFrame:
    """Rows whose outcome is fully determined by ``cutoff``: origin + horizon <= cutoff.

    Using ``resolved_at <= cutoff`` alone would keep early closures (y=0) while dropping
    still-pending successes (y=1), biasing training labels toward closure.
    """
    return labels[(labels["origin"] + labels["horizon"] <= cutoff) & labels["y_cont"].notna()]


def assert_no_leakage(train_labels: pd.DataFrame, cutoff: int):
    if len(train_labels) and (train_labels["origin"] + train_labels["horizon"]).max() > cutoff:
        raise AssertionError("training label resolves after the forecast origin")


# ----------------------------------------------------------------------- calibration
class PlattCalibrator:
    """Logistic recalibration on logit(p): p' = sigmoid(a*logit(p) + b).

    Fit on validation data that precedes the test origins. Falls back to identity when
    there are too few rows or only one class, instead of overfitting a thin pilot.
    """
    def __init__(self, min_n=200, min_each_class=20):
        self.min_n, self.min_each = min_n, min_each_class
        self.a, self.b, self.fitted = 1.0, 0.0, False

    @staticmethod
    def _logit(p):
        p = np.clip(p, 1e-6, 1 - 1e-6)
        return np.log(p / (1 - p))

    def fit(self, y, p):
        y = np.asarray(y, float); x = self._logit(np.asarray(p, float))
        if len(y) < self.min_n or min(y.sum(), len(y) - y.sum()) < self.min_each:
            return self
        w = np.array([1.0, 0.0])
        X = np.column_stack([x, np.ones_like(x)])
        for _ in range(50):  # Newton-Raphson with small ridge
            q = 1 / (1 + np.exp(-X @ w))
            g = X.T @ (q - y) + 1e-3 * (w - [1.0, 0.0])
            H = (X * (q * (1 - q))[:, None]).T @ X + 1e-3 * np.eye(2)
            step = np.linalg.solve(H, g); w -= step
            if np.abs(step).max() < 1e-8:
                break
        self.a, self.b, self.fitted = float(w[0]), float(w[1]), True
        return self

    def predict(self, p):
        return 1 / (1 + np.exp(-(self.a * self._logit(np.asarray(p, float)) + self.b)))


# ------------------------------------------------------------------------- metrics
def brier_score(y, p) -> float:
    y, p = np.asarray(y, float), np.asarray(p, float)
    return float(np.mean((p - y) ** 2))


def brier_skill_score(y, p, p_ref) -> float:
    """1 - Brier(p)/Brier(p_ref). >0 means better than the reference."""
    ref = brier_score(y, p_ref)
    return float("nan") if ref == 0 else 1.0 - brier_score(y, p) / ref


def reliability_table(y, p, n_bins=10, strategy="quantile") -> pd.DataFrame:
    """Per-bin mean prediction, observed rate, count and 95% Wilson interval."""
    y, p = np.asarray(y, float), np.asarray(p, float)
    if strategy == "quantile":
        edges = np.unique(np.quantile(p, np.linspace(0, 1, n_bins + 1)))
    else:
        edges = np.linspace(0, 1, n_bins + 1)
    idx = np.clip(np.searchsorted(edges, p, side="right") - 1, 0, max(len(edges) - 2, 0))
    rows = []
    for b in range(max(len(edges) - 1, 1)):
        m = idx == b
        n = int(m.sum())
        if n == 0:
            continue
        k, obs = y[m].sum(), y[m].mean()
        z = 1.96; den = 1 + z * z / n
        centre = (obs + z * z / (2 * n)) / den
        half = z * np.sqrt(obs * (1 - obs) / n + z * z / (4 * n * n)) / den
        rows.append((edges[b], edges[min(b + 1, len(edges) - 1)], n, p[m].mean(), obs, centre - half, centre + half))
    return pd.DataFrame(rows, columns=["bin_lo", "bin_hi", "n", "mean_pred", "obs_rate", "ci_lo", "ci_hi"])


def expected_calibration_error(table: pd.DataFrame) -> float:
    return float((table["n"] * (table["mean_pred"] - table["obs_rate"]).abs()).sum() / table["n"].sum())


def bootstrap_ci(y, p, groups, stat=brier_score, n_boot=500, seed=0):
    """Cluster bootstrap over ``groups`` (sections): rows from one section are correlated,
    so resample whole sections rather than rows."""
    y, p, groups = np.asarray(y, float), np.asarray(p, float), np.asarray(groups)
    rng = np.random.default_rng(seed)
    uniq = np.unique(groups)
    by = {g: np.flatnonzero(groups == g) for g in uniq}
    out = []
    for _ in range(n_boot):
        pick = np.concatenate([by[g] for g in rng.choice(uniq, len(uniq))])
        out.append(stat(y[pick], p[pick]))
    return tuple(np.percentile(out, [2.5, 97.5]))


def plot_reliability(models: dict, y, n_bins=10, strategy="quantile", title="", toy=False, ax=None):
    """Reliability diagram(s) with a count panel. ``models`` = {name: predictions}."""
    import matplotlib.pyplot as plt
    if ax is None:
        fig, (ax, axc) = plt.subplots(2, 1, figsize=(6, 7), gridspec_kw={"height_ratios": [3, 1]}, sharex=True)
    else:
        axc = None; fig = ax.figure
    ax.plot([0, 1], [0, 1], "k--", lw=1, label="perfect calibration")
    width = 0.8 / max(len(models), 1) / n_bins
    for k, (name, p) in enumerate(models.items()):
        t = reliability_table(y, p, n_bins, strategy)
        ece = expected_calibration_error(t)
        ax.errorbar(t["mean_pred"], t["obs_rate"], yerr=[t["obs_rate"] - t["ci_lo"], t["ci_hi"] - t["obs_rate"]],
                    marker="o", ms=4, lw=1.2, capsize=2, label=f"{name} (Brier {brier_score(y, p):.3f}, ECE {ece:.3f})")
        if axc is not None:
            axc.bar(t["mean_pred"] + (k - len(models) / 2) * width, t["n"], width=width, label=name)
    ax.set_ylabel("observed fraction that stayed open"); ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.set_title(("TOY DATA - NOT REAL PERFORMANCE\n" if toy else "") + title, fontsize=10, color="crimson" if toy else "black")
    ax.legend(fontsize=7, loc="upper left"); ax.grid(alpha=0.3)
    if axc is not None:
        axc.set_xlabel("mean predicted probability (quantile bins)"); axc.set_ylabel("rows per bin")
        axc.set_yscale("log"); axc.set_ylim(bottom=1); axc.grid(alpha=0.3)
        fig.tight_layout()
    return ax


# ------------------------------------------------------------------- rolling driver
def rolling_evaluation(panel, labels, folds, horizons, calibrate=True, max_gap_hours=3) -> pd.DataFrame:
    """Run the constant-hazard baseline (raw and optionally recalibrated) over folds.

    Returns one row per labelled test (section, origin, horizon) with columns
    fold, p_raw, p_cal, y_cont. All inputs to each prediction come from before the
    fold's test start; asserts enforce it.
    """
    out = []
    for k, f in enumerate(folds):
        lo, hi = f.test_range
        haz_test = fit_constant_hazard(panel, f.train_cutoff, max_gap_hours)
        haz_val = fit_constant_hazard(panel, f.val_cutoff, max_gap_hours)
        for h in horizons:
            L = labels[(labels["horizon"] == h) & labels["y_cont"].notna()]
            val = L[(L["origin"] >= f.val_range[0]) & (L["origin"] < f.val_range[1])]
            val = known_by(val, f.train_cutoff)  # val outcomes must be known before test starts
            assert_no_leakage(val, f.train_cutoff)
            cal = PlattCalibrator()
            if calibrate and len(val):
                cal.fit(val["y_cont"], np.full(len(val), haz_val.predict(h)))
            test = L[(L["origin"] >= lo) & (L["origin"] < hi)].copy()
            test["fold"] = k
            test["p_raw"] = float(haz_test.predict(h))
            test["p_cal"] = cal.predict(test["p_raw"].to_numpy()) if cal.fitted else test["p_raw"]
            test["cal_fitted"] = cal.fitted
            train = known_by(labels[labels["horizon"] == h], f.train_cutoff)
            assert_no_leakage(train, f.train_cutoff)
            test["p_train_rate"] = train["y_cont"].mean() if len(train) else np.nan
            out.append(test)
    return pd.concat(out, ignore_index=True)


# ------------------------------------------------------------------------ toy data
def simulate_toy_status(n_sections=150, n_days=90, seed=0, mean_days_to_close=14.0, mean_hours_to_reopen=36.0,
                        outage_prob_per_day=0.04, max_outage_hours=18):
    """TOY hourly open/closed chains with section-level hazard heterogeneity and random
    observation outages. Returns (obs DataFrame, true_hazards Series). Not real data."""
    rng = np.random.default_rng(seed)
    H = n_days * 24
    lam = rng.lognormal(np.log(1 / (24 * mean_days_to_close)), 0.9, n_sections)   # open->closed per hour
    mu = rng.lognormal(np.log(1 / mean_hours_to_reopen), 0.5, n_sections)         # closed->open per hour
    state = np.ones(n_sections, bool)
    S = np.empty((n_sections, H), bool)
    for t in range(H):
        S[:, t] = state
        u = rng.random(n_sections)
        state = np.where(state, u >= 1 - np.exp(-lam), u < 1 - np.exp(-mu))
    seen = np.ones_like(S)
    for i in range(n_sections):
        for d in range(n_days):
            if rng.random() < outage_prob_per_day:
                s = d * 24 + rng.integers(0, 24); seen[i, s:s + rng.integers(4, max_outage_hours + 1)] = False
    start = pd.Timestamp("2027-01-01", tz="UTC")
    ii, tt = np.nonzero(seen)
    obs = pd.DataFrame({"section": [f"TOY-{i:03d}" for i in ii],
                        "observed_at": start + pd.to_timedelta(tt, unit="h"),
                        "status": np.where(S[ii, tt], "open", "closed"),
                        "source": "toy_simulation", "is_demo": True})
    return obs, pd.Series(lam, index=[f"TOY-{i:03d}" for i in range(n_sections)])
