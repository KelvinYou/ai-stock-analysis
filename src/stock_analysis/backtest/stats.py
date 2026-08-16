"""Small-sample statistics for backtest scoring.

Every function here exists to answer one question: **is this number
distinguishable from luck?** A backtest over 12 trials that reports a 62% hit
rate is reporting noise, and a point estimate with no interval around it reads
as an edge whether or not it is one.

Implemented from scratch rather than pulling in scipy: the whole point is
honest behaviour in the small-sample regime, which rules out the normal
approximations that would make a lightweight dependency sufficient. A real
Student-t tail is ~40 lines; scipy is ~30MB.

Three families live here:

- **Interval estimation** — Wilson intervals for hit rates, Fisher-z intervals
  for the information coefficient. Both behave at small n where the textbook
  normal approximation produces intervals running past 0 or 1.
- **Sample independence** — `effective_sample_size` discounts overlapping
  holding periods. Backtest trials spaced weekly with a 30-day horizon share
  23 days of price path; treating them as
  independent understates variance and inflates every significance figure
  downstream.
- **Selection bias** — `probabilistic_sharpe_ratio` and
  `deflated_sharpe_ratio` price in the fact that reporting the best of N
  strategies is not the same as reporting one strategy chosen in advance.

References: López de Prado, *Advances in Financial Machine Learning*, ch. 4
(sample uniqueness) and ch. 8 & 14 (PSR/DSR); Bailey & López de Prado (2014),
"The Deflated Sharpe Ratio".
"""
from __future__ import annotations

import math
from datetime import date
from statistics import NormalDist

# Euler–Mascheroni constant, used in the expected-maximum-Sharpe estimator.
_EULER_GAMMA = 0.5772156649015329

_NORM = NormalDist()

__all__ = [
    "deflated_sharpe_ratio",
    "effective_sample_size",
    "expected_max_sharpe",
    "fisher_ci",
    "kurtosis",
    "probabilistic_sharpe_ratio",
    "skewness",
    "t_test_vs_zero",
    "wilson_interval",
]


# ----------------------------------------------------------------------
# Moments
# ----------------------------------------------------------------------
def skewness(values: list[float]) -> float | None:
    """Sample skewness (Fisher-Pearson, biased form)."""
    n = len(values)
    if n < 3:
        return None
    mean = sum(values) / n
    m2 = sum((v - mean) ** 2 for v in values) / n
    m3 = sum((v - mean) ** 3 for v in values) / n
    if m2 <= 0:
        return None
    return m3 / m2**1.5


def kurtosis(values: list[float]) -> float | None:
    """Sample kurtosis, **not** excess: a normal distribution returns 3.0.

    The PSR formula below is written against non-excess kurtosis; returning the
    excess form here would silently shift every PSR by (3/4)·SR².
    """
    n = len(values)
    if n < 4:
        return None
    mean = sum(values) / n
    m2 = sum((v - mean) ** 2 for v in values) / n
    m4 = sum((v - mean) ** 4 for v in values) / n
    if m2 <= 0:
        return None
    return m4 / m2**2


# ----------------------------------------------------------------------
# Interval estimation
# ----------------------------------------------------------------------
def wilson_interval(hits: int, n: int, z: float = 1.96) -> tuple[float, float] | None:
    """Wilson score interval for a binomial proportion.

    Preferred over the normal approximation `p ± z·√(p(1-p)/n)`, which at the
    sample sizes a backtest produces can hand back intervals extending below 0
    or above 1 — and collapses to zero width when p hits 0 or 1, which is
    exactly backwards.
    """
    if n <= 0:
        return None
    p = hits / n
    denom = 1.0 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denom
    half = z / denom * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2))
    return (max(0.0, centre - half), min(1.0, centre + half))


def fisher_ci(r: float, n: int, z: float = 1.96) -> tuple[float, float] | None:
    """Confidence interval for a Pearson correlation via Fisher z-transform.

    Used for the information coefficient, whose sampling distribution is badly
    skewed near ±1 — the untransformed interval would be symmetric and wrong.
    """
    if n < 4 or abs(r) >= 1.0:
        return None
    zr = math.atanh(r)
    se = 1.0 / math.sqrt(n - 3)
    return (math.tanh(zr - z * se), math.tanh(zr + z * se))


# ----------------------------------------------------------------------
# Sample independence
# ----------------------------------------------------------------------
def effective_sample_size(windows: list[tuple[str, date, date]]) -> float:
    """Discount overlapping holding periods to an independent-trial count.

    `windows` is a list of `(group_key, start, end)` — group_key being whatever
    makes two positions share a price path, normally the ticker.

    A trial concurrent with `c` trials (itself included) contributes `1/c`
    rather than 1. Weekly trials on one ticker at a 30-day horizon collapse
    from 5 nominal trials to roughly 1 independent one, which is the honest
    denominator for any t-statistic computed over them.

    This is a per-trial simplification of López de Prado's average-uniqueness
    weighting, which computes concurrency bar-by-bar within each window. The
    simplified form is coarser but moves the number in the same direction and
    needs no bar-level data.

    Cross-sectional dependence is **not** captured: three tech tickers analysed
    on the same date are close to one bet on one sector, but this function will
    count them as three. Treat the result as an upper bound on independence.
    """
    if not windows:
        return 0.0

    by_group: dict[str, list[tuple[date, date]]] = {}
    for key, start, end in windows:
        by_group.setdefault(key, []).append((start, end))

    total = 0.0
    for spans in by_group.values():
        for start, end in spans:
            concurrency = sum(1 for s, e in spans if start <= e and s <= end)
            total += 1.0 / concurrency if concurrency else 0.0
    return total


# ----------------------------------------------------------------------
# Hypothesis testing
# ----------------------------------------------------------------------
def _betacf(a: float, b: float, x: float, itmax: int = 300, eps: float = 3e-16) -> float:
    """Continued-fraction expansion for the incomplete beta function."""
    tiny = 1e-30
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < tiny:
        d = tiny
    d = 1.0 / d
    h = d
    for m in range(1, itmax + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


def _betainc(a: float, b: float, x: float) -> float:
    """Regularized incomplete beta I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    log_beta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    front = math.exp(log_beta + a * math.log(x) + b * math.log1p(-x))
    # Converges fast only on one side of the mode; use the symmetry
    # I_x(a,b) = 1 - I_{1-x}(b,a) on the other. `front` is symmetric in (a,b).
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def student_t_two_sided_p(t: float, df: float) -> float | None:
    """Two-sided p-value for a t-statistic. Exact, not normal-approximated."""
    if df <= 0:
        return None
    return _betainc(df / 2.0, 0.5, df / (df + t * t))


def t_test_vs_zero(
    values: list[float], n_eff: float | None = None
) -> tuple[float | None, float | None]:
    """One-sample t-test of mean = 0, returning `(t, two_sided_p)`.

    Pass `n_eff` to run the test on the uniqueness-adjusted sample size instead
    of `len(values)`. With overlapping trials the nominal count is the wrong
    denominator and produces a t-statistic inflated by roughly √(n/n_eff).
    """
    clean = [v for v in values if v is not None and not math.isnan(v)]
    n = len(clean)
    if n < 2:
        return None, None
    mean = sum(clean) / n
    var = sum((v - mean) ** 2 for v in clean) / (n - 1)
    if var <= 0:
        return None, None
    n_use = n_eff if n_eff and n_eff > 1 else float(n)
    t = mean / math.sqrt(var / n_use)
    return t, student_t_two_sided_p(t, n_use - 1)


# ----------------------------------------------------------------------
# Selection bias
# ----------------------------------------------------------------------
def probabilistic_sharpe_ratio(
    observed_sr: float,
    n: int,
    skew: float | None,
    kurt: float | None,
    benchmark_sr: float = 0.0,
) -> float | None:
    """Probability that the true Sharpe exceeds `benchmark_sr`.

    Corrects the Sharpe's standard error for non-normal returns: negative skew
    and fat tails both inflate a naive Sharpe, and trading strategy returns
    reliably have both. `observed_sr` must be per-observation, matching the
    non-annualised Sharpe the scorer computes.
    """
    if n < 2:
        return None
    g3 = 0.0 if skew is None else skew
    g4 = 3.0 if kurt is None else kurt
    denom_sq = 1.0 - g3 * observed_sr + ((g4 - 1.0) / 4.0) * observed_sr**2
    if denom_sq <= 0:
        return None
    z = (observed_sr - benchmark_sr) * math.sqrt(n - 1) / math.sqrt(denom_sq)
    return _NORM.cdf(z)


def expected_max_sharpe(n_strategies: int, sr_variance: float) -> float | None:
    """Expected maximum Sharpe across `n_strategies` with **no** real edge.

    The benchmark a winning strategy has to clear before "it beat the others"
    means anything. Search hard enough over strategies with zero true skill and
    one of them posts a good Sharpe by construction.
    """
    if n_strategies < 2 or sr_variance <= 0:
        return None
    sr_std = math.sqrt(sr_variance)
    a = _NORM.inv_cdf(1.0 - 1.0 / n_strategies)
    b = _NORM.inv_cdf(1.0 - 1.0 / (n_strategies * math.e))
    return sr_std * ((1.0 - _EULER_GAMMA) * a + _EULER_GAMMA * b)


def deflated_sharpe_ratio(
    observed_sr: float,
    n: int,
    skew: float | None,
    kurt: float | None,
    n_strategies: int,
    sr_variance: float,
) -> float | None:
    """PSR measured against the expected best-of-N under the null.

    Reading: a DSR of 0.95 means the strategy's Sharpe survives the knowledge
    that it was the winner of `n_strategies` attempts. Below ~0.95 the result
    is consistent with selection bias — which is the default explanation when
    several strategies are scored and the best one gets written up.
    """
    benchmark = expected_max_sharpe(n_strategies, sr_variance)
    if benchmark is None:
        return None
    return probabilistic_sharpe_ratio(observed_sr, n, skew, kurt, benchmark_sr=benchmark)
