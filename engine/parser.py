"""CLI output parser for simulated ZTE OLT commands."""

import re
from dataclasses import dataclass, field

_FLAGS = re.IGNORECASE | re.MULTILINE

_RE_ONU_STATE = re.compile(r"^\s*State\s*:\s*(ready|offline)", _FLAGS)
_RE_PHASE_STATE = re.compile(r"^\s*Phase\s+state\s*:\s*(working|standby)", _FLAGS)
_RE_MAC = re.compile(r"Mac\s*:\s*([0-9a-f]{4}\.[0-9a-f]{4}\.[0-9a-f]{4})", _FLAGS)
_RE_SPEED = re.compile(r"Speed\s+status\s*:\s*(full-(?:1000|100|10))", _FLAGS)
_RE_RX = re.compile(r"Rx\s*:\s*(-?\d+\.\d+)\s*\(dbm\)", _FLAGS)
_RE_INPUT_RATE = re.compile(r"Input\s+rate\s*:\s*(\d+)\s*pps", _FLAGS)
_RE_OUTPUT_RATE = re.compile(r"Output\s+rate\s*:\s*(\d+)\s*pps", _FLAGS)
_RE_EVENT = re.compile(r"(DyingGasp|LOSi)", _FLAGS)


@dataclass
class OLTData:
    onu_state: str  # 'ready' | 'offline'
    phase_state: str  # 'working' | 'standby'
    mac_count: int
    speed_status: str  # 'full-1000' | 'full-100' | 'full-10'
    rx_power_dbm: float
    input_rate_pps: int
    output_rate_pps: int
    last_event: str | None  # 'DyingGasp' | 'LOSi' | None
    raw_lines: list[str] = field(default_factory=list)


def _first(pattern: re.Pattern, text: str, default: str) -> str:
    m = pattern.search(text)
    return m.group(1).lower() if m else default


def parse_olt_output(raw: str) -> OLTData:
    """Parse a concatenated ZTE OLT CLI response string into OLTData."""
    onu_state = _first(_RE_ONU_STATE, raw, "offline")
    phase_state = _first(_RE_PHASE_STATE, raw, "standby")
    speed = _first(_RE_SPEED, raw, "full-1000")

    mac_matches = _RE_MAC.findall(raw)
    mac_count = len(mac_matches)

    rx_m = _RE_RX.search(raw)
    rx_power = float(rx_m.group(1)) if rx_m else -25.0

    in_m = _RE_INPUT_RATE.search(raw)
    out_m = _RE_OUTPUT_RATE.search(raw)
    input_rate = int(in_m.group(1)) if in_m else 0
    output_rate = int(out_m.group(1)) if out_m else 0

    event_matches = _RE_EVENT.findall(raw)
    last_event = event_matches[-1] if event_matches else None

    lines = [l.strip() for l in raw.splitlines() if l.strip()]
    raw_lines = lines[-2:] if len(lines) >= 2 else lines

    return OLTData(
        onu_state=onu_state,
        phase_state=phase_state,
        mac_count=mac_count,
        speed_status=speed,
        rx_power_dbm=rx_power,
        input_rate_pps=input_rate,
        output_rate_pps=output_rate,
        last_event=last_event,
        raw_lines=raw_lines,
    )


def olt_data_from_db_row(row: dict) -> OLTData:
    """Construct OLTData directly from a MySQL row dict (no regex required)."""
    return OLTData(
        onu_state=row["onu_state"],
        phase_state=row["phase_state"],
        mac_count=int(row["mac_count"]),
        speed_status=row["speed_status"],
        rx_power_dbm=float(row["rx_power_dbm"]),
        input_rate_pps=int(row["input_rate_pps"]),
        output_rate_pps=int(row["output_rate_pps"]),
        last_event=row.get("last_event"),
        raw_lines=[],
    )
