"""Hard gates for an externally valid, provider-backed backtest.

Preparing a packet is not the same as validating the production pipeline.  A
session bundle can contain clean prices and dated public evidence while still
using an in-session prediction, a survivorship-biased universe, an assumed
cost, or too few independent observations.  This module makes those gaps
explicit and fails closed.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any, Literal

from .session import SessionManifest, validate_manifest_panel

GateStatus = Literal["PASS", "FAIL", "BLOCKED"]


@dataclass(frozen=True)
class GateResult:
    name: str
    status: GateStatus
    observed: str
    requirement: str


@dataclass(frozen=True)
class ExternalValidationReport:
    session_dir: str
    gates: tuple[GateResult, ...]

    @property
    def status(self) -> GateStatus:
        if any(gate.status == "FAIL" for gate in self.gates):
            return "FAIL"
        if any(gate.status == "BLOCKED" for gate in self.gates):
            return "BLOCKED"
        return "PASS"

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "session_dir": self.session_dir,
            "gates": [asdict(gate) for gate in self.gates],
        }

    def to_markdown(self) -> str:
        lines = [
            "# External Backtest Validation",
            "",
            f"**Overall: {self.status}**",
            "",
            "| Gate | Status | Observed | Requirement |",
            "|---|---|---|---|",
        ]
        for gate in self.gates:
            lines.append(
                f"| {gate.name} | **{gate.status}** | {gate.observed} | {gate.requirement} |"
            )
        lines.extend(
            [
                "",
                (
                    "PASS is emitted only when every gate is PASS. BLOCKED means an external "
                    "artifact or authority is missing; FAIL means the supplied artifact "
                    "does not satisfy the contract."
                ),
            ]
        )
        return "\n".join(lines) + "\n"


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        raw = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    return raw if isinstance(raw, dict) else None


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _is_sha256(value: Any) -> bool:
    digest = str(value).lower()
    return len(digest) == 64 and all(char in "0123456789abcdef" for char in digest)


def _gate(
    name: str,
    status: GateStatus,
    observed: str,
    requirement: str,
) -> GateResult:
    return GateResult(name, status, observed, requirement)


def _packet_path(session_dir: Path, item: Any) -> Path | None:
    if not isinstance(item, dict) or not isinstance(item.get("packet"), str):
        return None
    relative = Path(item["packet"])
    path = (session_dir / relative).resolve()
    if (
        relative.is_absolute()
        or not relative.parts
        or relative.parts[0] != "packets"
        or not path.is_relative_to(session_dir.resolve())
    ):
        return None
    return path


def _read_packet(session_dir: Path, item: Any) -> dict[str, Any] | None:
    path = _packet_path(session_dir, item)
    if path is None:
        return None
    try:
        packet = _read_json(path)
    except (OSError, ValueError):
        return None
    if packet is None or not isinstance(packet.get("ticker_data"), dict):
        return None
    if not isinstance(packet.get("evidence_availability"), dict):
        return None
    return packet


def _packet_integrity_gate(
    session_dir: Path,
    manifest: dict[str, Any],
) -> GateResult:
    try:
        validate_manifest_panel(SessionManifest.model_validate(manifest))
    except ValueError as exc:
        return _gate(
            "point-in-time packet integrity",
            "FAIL",
            f"invalid manifest trial grid: {exc}",
            "the manifest must contain every declared ticker/date trial exactly once",
        )
    trials = manifest.get("trials")
    if not isinstance(trials, list) or not trials:
        return _gate(
            "point-in-time packet integrity",
            "FAIL",
            "manifest has no trials",
            "every trial must have an auditable packet",
        )

    invalid: list[str] = []
    covered = {"technical": 0, "fundamentals": 0, "sentiment": 0, "macro": 0}
    for item in trials:
        if not isinstance(item, dict):
            invalid.append("non-object trial")
            continue
        packet_rel = item.get("packet")
        if not packet_rel:
            invalid.append("missing packet path")
            continue
        packet_path = _packet_path(session_dir, item)
        if packet_path is None:
            invalid.append(f"invalid packet path: {packet_rel}")
            continue
        packet = _read_packet(session_dir, item)
        if packet is None:
            invalid.append(f"malformed or missing packet: {packet_rel}")
            continue
        try:
            as_of = date.fromisoformat(str(packet["as_of_date"]))
            expected_as_of = date.fromisoformat(str(item["as_of_date"]))
        except (KeyError, TypeError, ValueError):
            invalid.append(f"malformed packet: {packet_rel}")
            continue
        if (
            str(packet.get("ticker", "")).upper() != str(item["ticker"]).upper()
            or as_of != expected_as_of
            or str(packet.get("market", "")).upper() != str(manifest["market"]).upper()
        ):
            invalid.append(f"packet identity mismatch: {packet_rel}")
            continue
        if packet.get("do_not_use_future_prices") is not True:
            invalid.append(f"future-price flag: {packet_rel}")
        ticker_data = packet.get("ticker_data")
        bars = ticker_data.get("price_history") if isinstance(ticker_data, dict) else None
        try:
            valid_bars = isinstance(bars, list) and bool(bars) and all(
                isinstance(bar, dict)
                and date.fromisoformat(str(bar["date"])) <= as_of
                for bar in bars
            )
        except (KeyError, TypeError, ValueError):
            valid_bars = False
        if not valid_bars:
            invalid.append(f"future price bar: {packet_rel}")
        evidence = packet.get("evidence_availability", {})
        if not isinstance(evidence, dict):
            invalid.append(f"invalid evidence availability: {packet_rel}")
            continue
        for name in covered:
            if evidence.get(name) is True or (name == "technical" and bool(bars)):
                covered[name] += 1

    total = len(trials)
    missing = ", ".join(
        f"{name} {count}/{total}" for name, count in covered.items() if count != total
    )
    if invalid:
        return _gate(
            "point-in-time packet integrity",
            "FAIL",
            f"{len(invalid)} invalid packet(s); {missing or 'all evidence present'}",
            "all packet clocks and all four evidence classes must pass",
        )
    if missing:
        return _gate(
            "point-in-time packet integrity",
            "FAIL",
            missing,
            "technical, fundamentals, historical sentiment, and macro must be 100% covered",
        )
    return _gate(
        "point-in-time packet integrity",
        "PASS",
        f"{total}/{total} packets; all four evidence classes present",
        "all packet clocks and all four evidence classes must pass",
    )


def _news_source_gate(session_dir: Path, manifest: dict[str, Any]) -> GateResult:
    sources: set[str] = set()
    for item in manifest.get("trials", []):
        packet = _read_packet(session_dir, item)
        if packet is None:
            return _gate(
                "historical news source", "FAIL", "invalid or missing packet",
                "provider-versioned historical news coverage, with publication and first-available clocks",
            )
        sources.add(str(packet.get("evidence_availability", {}).get("sentiment_source")))
    if sources == {"historical_provider"}:
        return _gate(
            "historical news source",
            "PASS",
            "provider-versioned historical feed",
            "the same provider news contract used in production must be replayed",
        )
    return _gate(
        "historical news source",
        "BLOCKED",
        f"{', '.join(sorted(sources)) or 'none'}; SEC filing events are not a complete provider news feed",
        "provider-versioned historical news coverage, with publication and first-available clocks",
    )


def _metadata_gate(session_dir: Path, manifest: dict[str, Any]) -> GateResult:
    invalid: list[str] = []
    omitted = 0
    versioned = 0
    for item in manifest.get("trials", []):
        packet = _read_packet(session_dir, item)
        if packet is None:
            return _gate(
                "point-in-time metadata", "FAIL", "invalid or missing packet",
                "use versioned historical metadata or omit unversioned sector/industry",
            )
        ticker_data = packet.get("ticker_data", {})
        info = ticker_data.get("info", {})
        evidence = packet.get("evidence_availability", {})
        if not isinstance(info, dict):
            invalid.append(str(item.get("packet")))
            continue
        ticker_name = str(item.get("ticker", "")).upper().removesuffix(".KL")
        default_currency = "MYR" if str(manifest.get("market", "")).upper() == "MY" else "USD"
        extra_metadata = bool(
            info.get("sector")
            or info.get("industry")
            or info.get("name") not in (None, "", ticker_name)
            or info.get("currency") not in (None, "", default_currency)
        )
        if extra_metadata:
            if evidence.get("metadata_source") != "historical_replay":
                invalid.append(str(item.get("packet")))
            else:
                versioned += 1
        else:
            omitted += 1
    if invalid:
        return _gate(
            "point-in-time metadata",
            "FAIL",
            f"unversioned metadata present in {len(invalid)} packet(s)",
            "use versioned historical metadata or omit unversioned company attributes",
        )
    return _gate(
        "point-in-time metadata",
        "PASS",
        f"{omitted} packet(s) fail-closed; {versioned} versioned packet(s)",
        "use versioned historical metadata or omit unversioned company attributes",
    )


def _macro_source_gate(session_dir: Path, manifest: dict[str, Any]) -> GateResult:
    sources: set[str] = set()
    for item in manifest.get("trials", []):
        packet = _read_packet(session_dir, item)
        if packet is None:
            return _gate(
                "historical macro source", "FAIL", "invalid or missing packet",
                "macro observations must carry observation and first-available dates",
            )
        sources.add(str(packet.get("evidence_availability", {}).get("macro_source")))
    if sources and sources != {"not_configured"}:
        return _gate(
            "historical macro source",
            "PASS",
            f"dated replay source(s): {', '.join(sorted(sources))}",
            "macro observations must carry observation and first-available dates",
        )
    return _gate(
        "historical macro source",
        "FAIL",
        "no dated macro source",
        "macro observations must carry observation and first-available dates",
    )


def _provider_gate(session_dir: Path, manifest_path: Path, manifest: dict[str, Any]) -> GateResult:
    metadata = _read_json(session_dir / "provider_run.json")
    if metadata is None:
        return _gate(
            "production provider run",
            "BLOCKED",
            "provider_run.json missing; current manifest is in-session",
            "authenticated provider invocation bound to exact predictions and score",
        )
    required = ("provider", "model", "run_id", "packet_manifest_sha256", "prediction_count")
    missing = [key for key in required if metadata.get(key) in (None, "")]
    if missing:
        return _gate(
            "production provider run",
            "FAIL",
            f"missing {', '.join(missing)}",
            "real provider, model, run id, packet hash, and one prediction per trial",
        )
    expected_hash = _sha256(manifest_path)
    if metadata["packet_manifest_sha256"] != expected_hash:
        return _gate(
            "production provider run",
            "FAIL",
            "provider packet hash does not match session manifest",
            "predictions must be paired with this exact packet set",
        )
    expected_count = len(manifest.get("trials", []))
    if int(metadata["prediction_count"]) != expected_count:
        return _gate(
            "production provider run",
            "FAIL",
            f"{metadata['prediction_count']} predictions for {expected_count} trials",
            "one provider prediction per trial",
        )
    # These fields are self-declared JSON. Until a provider invocation records
    # verifiable prediction/prompt provenance and the scorer binds to it, the
    # metadata cannot authenticate a production model run.
    return _gate(
        "production provider run",
        "BLOCKED",
        (
            f"metadata only: {metadata['provider']} / {metadata['model']} / "
            f"{metadata['run_id']}; provider invocation is unverified"
        ),
        "authenticated provider invocation bound to exact predictions and score",
    )


def _universe_gate(session_dir: Path, manifest: dict[str, Any]) -> GateResult:
    metadata = _read_json(session_dir / "universe.json")
    if metadata is None:
        return _gate(
            "survivorship-safe universe",
            "BLOCKED",
            "universe.json missing; current fixed ticker list is not enough",
            "hashed source extract and point-in-time membership for every trial",
        )
    required = (
        "universe_id",
        "membership_source",
        "membership_source_url",
        "membership_as_of_policy",
        "security_id_scheme",
        "selection_policy",
        "source_extract_sha256",
        "membership_records",
        "membership_records_sha256",
        "return_treatment",
        "tickers",
    )
    missing = [key for key in required if not metadata.get(key)]
    if missing or metadata.get("survivorship_bias_control") is not True:
        return _gate(
            "survivorship-safe universe",
            "FAIL",
            f"missing {', '.join(missing) or 'survivorship_bias_control=true'}",
            "hashed source extract and point-in-time membership for every trial",
        )

    if metadata.get("schema_version") != 1:
        return _gate(
            "survivorship-safe universe",
            "FAIL",
            f"unsupported schema_version={metadata.get('schema_version')!r}",
            "universe.json schema_version 1",
        )

    if not str(metadata["membership_source_url"]).startswith("https://"):
        return _gate(
            "survivorship-safe universe",
            "FAIL",
            "membership_source_url must be an HTTPS source reference",
            "auditable source and dated membership evidence",
        )

    for key in ("source_extract_sha256", "membership_records_sha256"):
        if not _is_sha256(metadata[key]):
            return _gate(
                "survivorship-safe universe",
                "FAIL",
                f"{key} is not a SHA-256 digest",
                "hashed source extract and point-in-time membership for every trial",
            )

    expected = set(str(ticker).upper() for ticker in manifest.get("tickers", []))
    observed = set(str(ticker).upper() for ticker in metadata.get("tickers", []))
    if not expected or observed != expected:
        return _gate(
            "survivorship-safe universe",
            "FAIL",
            "universe tickers are missing or do not exactly match the session manifest",
            "the validated universe must be explicit and match the session",
        )

    records = metadata.get("membership_records")
    if not isinstance(records, list):
        return _gate(
            "survivorship-safe universe",
            "FAIL",
            "membership_records must be an array",
            "one source-backed membership row per ticker and as-of date",
        )
    canonical_records = json.dumps(records, sort_keys=True, separators=(",", ":"))
    records_digest = hashlib.sha256(canonical_records.encode("utf-8")).hexdigest()
    if records_digest != str(metadata["membership_records_sha256"]).lower():
        return _gate(
            "survivorship-safe universe",
            "FAIL",
            "membership_records_sha256 does not match membership_records",
            "membership evidence must be immutable and hash-linked",
        )

    covered: set[tuple[str, str]] = set()
    invalid_records: list[str] = []
    for record in records:
        if not isinstance(record, dict):
            invalid_records.append("non-object membership row")
            continue
        ticker = str(record.get("ticker", "")).upper()
        as_of = str(record.get("as_of_date", ""))
        security_id = str(record.get("security_id", ""))
        if not ticker or not security_id or record.get("member") is not True:
            invalid_records.append(f"invalid membership row for {ticker or '<missing ticker>'}")
            continue
        try:
            date.fromisoformat(as_of)
        except ValueError:
            invalid_records.append(f"invalid as_of_date for {ticker}")
            continue
        key = (ticker, as_of)
        if key in covered:
            invalid_records.append(f"duplicate membership row for {ticker} @ {as_of}")
        covered.add(key)

    expected_trials = {
        (str(item.get("ticker", "")).upper(), str(item.get("as_of_date", "")))
        for item in manifest.get("trials", [])
        if isinstance(item, dict)
    }
    missing_trials = expected_trials - covered
    unexpected_trials = covered - expected_trials
    if invalid_records or missing_trials or unexpected_trials:
        detail = invalid_records[0] if invalid_records else ""
        if missing_trials:
            ticker, as_of = sorted(missing_trials)[0]
            detail = f"no PIT membership row for {ticker} @ {as_of}"
        elif unexpected_trials:
            ticker, as_of = sorted(unexpected_trials)[0]
            detail = f"membership row is outside the session for {ticker} @ {as_of}"
        return _gate(
            "survivorship-safe universe",
            "FAIL",
            detail,
            "one source-backed membership row per ticker and as-of date",
        )

    return_treatment = metadata.get("return_treatment")
    required_return_fields = (
        "source",
        "field",
        "data_sha256",
        "includes_distributions",
        "includes_delisting_returns",
        "includes_merger_consideration",
        "missing_return_policy",
    )
    if not isinstance(return_treatment, dict) or any(
        return_treatment.get(key) in (None, "") for key in required_return_fields
    ):
        return _gate(
            "survivorship-safe universe",
            "FAIL",
            "return_treatment lacks source, hashed data, or terminal-return policy",
            "documented dividend, delisting, merger, and missing-return treatment",
        )
    if (
        any(
            return_treatment.get(key) is not True
            for key in (
                "includes_distributions",
                "includes_delisting_returns",
                "includes_merger_consideration",
            )
        )
        or return_treatment.get("missing_return_policy") != "fail_closed"
    ):
        return _gate(
            "survivorship-safe universe",
            "FAIL",
            "return_treatment omits terminal value or permits silent missing returns",
            "include distributions/delisting/merger value and fail closed on missing returns",
        )
    if not _is_sha256(return_treatment["data_sha256"]):
        return _gate(
            "survivorship-safe universe",
            "FAIL",
            "return_treatment.data_sha256 is not a SHA-256 digest",
            "hashed total-return data with terminal-event coverage",
        )

    return _gate(
        "survivorship-safe universe",
        "PASS",
        f"{metadata['universe_id']}; {len(expected_trials)} dated memberships; terminal-return policy declared",
        "hashed point-in-time membership and explicit total-return treatment",
    )


def _terminal_return_provenance_gate(
    session_dir: Path,
    score_path: Path | None,
) -> GateResult:
    metadata = _read_json(session_dir / "universe.json")
    if metadata is None:
        return _gate(
            "scored terminal-return provenance",
            "BLOCKED",
            "universe.json missing",
            "scored returns must be tied to the declared total-return data hash",
        )
    if score_path is None:
        return _gate(
            "scored terminal-return provenance",
            "BLOCKED",
            "scored report missing",
            "scored returns must be tied to the declared total-return data hash",
        )
    payload = _read_json(score_path) or {}
    result = payload.get("result", {})
    settings = result.get("settings", {}) if isinstance(result, dict) else {}
    settings = settings if isinstance(settings, dict) else {}
    provenance = settings.get("terminal_return_provenance", {})
    provenance = provenance if isinstance(provenance, dict) else {}
    treatment = metadata.get("return_treatment", {})
    treatment = treatment if isinstance(treatment, dict) else {}
    keys = (
        "source",
        "field",
        "data_sha256",
        "includes_distributions",
        "includes_delisting_returns",
        "includes_merger_consideration",
        "missing_return_policy",
    )
    if any(treatment.get(key) in (None, "") for key in keys):
        return _gate(
            "scored terminal-return provenance",
            "FAIL",
            "universe return_treatment is incomplete",
            "scored returns must use the hashed source that includes distributions and terminal value",
        )
    if (
        any(
            treatment.get(key) is not True
            for key in (
                "includes_distributions",
                "includes_delisting_returns",
                "includes_merger_consideration",
            )
        )
        or treatment.get("missing_return_policy") != "fail_closed"
        or not _is_sha256(treatment.get("data_sha256"))
    ):
        return _gate(
            "scored terminal-return provenance",
            "FAIL",
            "universe return_treatment does not satisfy terminal-return requirements",
            "scored returns must use the hashed source that includes distributions and terminal value",
        )
    if not isinstance(provenance, dict) or any(
        provenance.get(key) != treatment.get(key) for key in keys
    ):
        return _gate(
            "scored terminal-return provenance",
            "FAIL",
            "score does not attest to the exact declared return data and policy",
            "scored returns must use the hashed source that includes distributions and terminal value",
        )
    return _gate(
        "scored terminal-return provenance",
        "PASS",
        f"{provenance['source']} / {provenance['field']} / {provenance['data_sha256'][:12]}",
        "scored returns must use the hashed source that includes distributions and terminal value",
    )


def _cost_gate(session_dir: Path) -> GateResult:
    metadata = _read_json(session_dir / "cost_model.json")
    if metadata is None:
        return _gate(
            "execution cost calibration",
            "BLOCKED",
            "cost_model.json missing; bps is only an assumption",
            "externally calibrated spread, slippage, commission, and benchmark parity",
        )
    required = ("one_way_bps", "method", "source")
    missing = [key for key in required if metadata.get(key) in (None, "")]
    if (
        missing
        or metadata.get("calibrated") is not True
        or metadata.get("same_for_benchmark") is not True
    ):
        return _gate(
            "execution cost calibration",
            "FAIL",
            f"missing {', '.join(missing) or 'calibrated=true and same_for_benchmark=true'}",
            "externally calibrated spread, slippage, commission, and benchmark parity",
        )
    return _gate(
        "execution cost calibration",
        "PASS",
        f"{metadata['one_way_bps']} bps/side from {metadata['source']}",
        "externally calibrated spread, slippage, commission, and benchmark parity",
    )


def _score_path(session_dir: Path, explicit: Path | None) -> Path | None:
    if explicit is not None:
        return explicit if explicit.exists() else None
    for candidate in (session_dir / "score.json", session_dir / "backtest_report.json"):
        if candidate.exists():
            return candidate
    return None


def _scored_panel_gate(score_path: Path | None, manifest: dict[str, Any]) -> GateResult:
    requirement = "one complete scored outcome per frozen (ticker, as-of) trial"
    if score_path is None:
        return _gate("scored panel completeness", "BLOCKED", "scored report missing", requirement)
    payload = _read_json(score_path) or {}
    result = payload.get("result")
    trials = result.get("trials") if isinstance(result, dict) else None
    expected = manifest.get("trials")
    if not isinstance(trials, list) or not isinstance(expected, list):
        return _gate("scored panel completeness", "FAIL", "trial list missing", requirement)

    expected_keys = sorted(
        (str(item.get("ticker", "")).upper(), str(item.get("as_of_date", "")))
        for item in expected
        if isinstance(item, dict)
    )
    observed_keys = sorted(
        (str(item.get("ticker", "")).upper(), str(item.get("as_of_date", "")))
        for item in trials
        if isinstance(item, dict)
    )
    if len(expected_keys) != len(expected) or observed_keys != expected_keys:
        return _gate(
            "scored panel completeness",
            "FAIL",
            f"scored {len(observed_keys)} keys; manifest requires {len(expected)} exact keys",
            requirement,
        )

    for item in trials:
        key = f"{item['ticker']} @ {item['as_of_date']}"
        if item.get("error") is not None:
            return _gate("scored panel completeness", "FAIL", f"errored: {key}", requirement)
        for field in ("entry_price", "exit_price", "realized_return"):
            value = item.get(field)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
                return _gate("scored panel completeness", "FAIL", f"invalid {field}: {key}", requirement)
            if field != "realized_return" and value <= 0:
                return _gate("scored panel completeness", "FAIL", f"invalid {field}: {key}", requirement)
        for field in ("entry_date", "exit_date"):
            try:
                date.fromisoformat(item[field])
            except (KeyError, TypeError, ValueError):
                return _gate("scored panel completeness", "FAIL", f"invalid {field}: {key}", requirement)

    return _gate(
        "scored panel completeness", "PASS", f"{len(trials)}/{len(expected)} complete", requirement
    )


def _score_gates(
    score_path: Path | None,
    *,
    min_effective_n: float,
) -> tuple[GateResult, GateResult, GateResult]:
    if score_path is None:
        blocked = _gate(
            "effective sample",
            "BLOCKED",
            "scored report missing",
            f"portfolio_overlap_clustered_v1 effective n >= {min_effective_n:g}",
        )
        return (
            blocked,
            _gate(
                "strict long-hold benchmark",
                "BLOCKED",
                "scored report missing",
                "same window, universe, timing, and costs; pipeline must beat strict hold",
            ),
            _gate(
                "paired strict-hold alpha interval",
                "BLOCKED",
                "scored report missing",
                "lower 95% time-block-bootstrap bound of paired log excess must be > 0",
            ),
        )
    payload = _read_json(score_path) or {}
    report = payload.get("report", {})
    report = report if isinstance(report, dict) else {}
    portfolio = payload.get("portfolio", {})
    portfolio = portfolio if isinstance(portfolio, dict) else {}
    strategies = portfolio.get("strategies", [])
    pipeline = (
        next(
            (
                item
                for item in strategies
                if isinstance(item, dict) and item.get("strategy") == "overall"
            ),
            None,
        )
        if isinstance(strategies, list)
        else None
    )
    effective_n_basis = pipeline.get("effective_n_basis") if pipeline else None
    effective_n = pipeline.get("effective_n") if pipeline else None
    numeric_effective_n = (
        float(effective_n)
        if isinstance(effective_n, (int, float)) and not isinstance(effective_n, bool)
        else None
    )
    if effective_n_basis != "portfolio_overlap_clustered_v1":
        sample_gate = _gate(
            "effective sample",
            "BLOCKED",
            f"unrecognized or missing effective_n_basis={effective_n_basis!r}",
            f"effective_n_basis=portfolio_overlap_clustered_v1 and portfolio effective n >= {min_effective_n:g}",
        )
    elif numeric_effective_n is None or not math.isfinite(numeric_effective_n):
        sample_gate = _gate(
            "effective sample",
            "FAIL",
            f"invalid or missing overall portfolio effective_n={effective_n!r}",
            f"effective_n_basis=portfolio_overlap_clustered_v1 and portfolio effective n >= {min_effective_n:g}",
        )
    elif numeric_effective_n < min_effective_n:
        sample_gate = _gate(
            "effective sample",
            "FAIL",
            f"effective n={numeric_effective_n:.2f}",
            f"effective_n_basis=portfolio_overlap_clustered_v1 and portfolio effective n >= {min_effective_n:g}",
        )
    else:
        sample_gate = _gate(
            "effective sample",
            "PASS",
            f"effective n={numeric_effective_n:.2f}",
            f"effective_n_basis=portfolio_overlap_clustered_v1 and portfolio effective n >= {min_effective_n:g}",
        )

    benchmark = portfolio.get("benchmark_strategy")
    beaten = portfolio.get("benchmark_beaten")
    promotion_ready = portfolio.get("promotion_ready")
    if benchmark != "buy_and_hold":
        benchmark_gate = _gate(
            "strict long-hold benchmark",
            "FAIL",
            f"benchmark={benchmark!r}",
            "same window, universe, timing, and costs; pipeline must beat strict hold",
        )
    elif beaten is not True or promotion_ready is not True:
        benchmark_gate = _gate(
            "strict long-hold benchmark",
            "FAIL",
            f"benchmark_beaten={beaten!r}, promotion_ready={promotion_ready!r}",
            "same window, universe, timing, and costs; pipeline must beat strict hold",
        )
    else:
        benchmark_gate = _gate(
            "strict long-hold benchmark",
            "PASS",
            "pipeline beats buy_and_hold and promotion gate is true",
            "same window, universe, timing, and costs; pipeline must beat strict hold",
        )
    interval = pipeline.get("strict_hold_log_excess_ci_95") if pipeline else None
    parsed_interval: tuple[float, float] | None = None
    if isinstance(interval, (list, tuple)) and len(interval) == 2:
        try:
            low, high = float(interval[0]), float(interval[1])
            if math.isfinite(low) and math.isfinite(high) and low <= high:
                parsed_interval = (low, high)
        except (TypeError, ValueError):
            pass
    if parsed_interval is None:
        interval_gate = _gate(
            "paired strict-hold alpha interval",
            "FAIL" if interval is not None else "BLOCKED",
            "malformed paired interval"
            if interval is not None
            else "overall pipeline has no paired interval",
            "lower 95% time-block-bootstrap bound of paired log excess must be > 0",
        )
    elif parsed_interval[0] <= 0:
        interval_gate = _gate(
            "paired strict-hold alpha interval",
            "FAIL",
            f"95% paired log-excess interval=[{parsed_interval[0]:.4f}, {parsed_interval[1]:.4f}]",
            "lower 95% time-block-bootstrap bound of paired log excess must be > 0",
        )
    else:
        interval_gate = _gate(
            "paired strict-hold alpha interval",
            "PASS",
            f"95% paired log-excess interval=[{parsed_interval[0]:.4f}, {parsed_interval[1]:.4f}]",
            "lower 95% time-block-bootstrap bound of paired log excess must be > 0",
        )
    return sample_gate, benchmark_gate, interval_gate


def validate_session_bundle(
    session_dir: Path,
    *,
    score_report: Path | None = None,
    min_effective_n: float = 30.0,
) -> ExternalValidationReport:
    """Evaluate every external-validation gate without mutating the bundle."""

    manifest_path = session_dir / "manifest.json"
    manifest = _read_json(manifest_path)
    if manifest is None:
        return ExternalValidationReport(
            str(session_dir),
            (
                _gate(
                    "session manifest",
                    "FAIL",
                    "manifest.json missing",
                    "a sealed session manifest is required",
                ),
            ),
        )

    scored_path = _score_path(session_dir, score_report)
    sample_gate, benchmark_gate, paired_interval_gate = _score_gates(
        scored_path,
        min_effective_n=min_effective_n,
    )
    gates = (
        _packet_integrity_gate(session_dir, manifest),
        _metadata_gate(session_dir, manifest),
        _news_source_gate(session_dir, manifest),
        _macro_source_gate(session_dir, manifest),
        _provider_gate(session_dir, manifest_path, manifest),
        _universe_gate(session_dir, manifest),
        _terminal_return_provenance_gate(
            session_dir,
            scored_path,
        ),
        _cost_gate(session_dir),
        _scored_panel_gate(scored_path, manifest),
        sample_gate,
        benchmark_gate,
        paired_interval_gate,
    )
    return ExternalValidationReport(str(session_dir), gates)
