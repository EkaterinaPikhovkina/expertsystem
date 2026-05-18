"""Rule-based inference engine for network diagnostics."""

import hashlib
from dataclasses import dataclass

from engine.parser import OLTData


@dataclass
class Diagnosis:
    code: str           # machine-readable key, e.g. "SPEED_DEGRADED"
    message_key: str    # key into texts.MESSAGES
    severity: str       # 'info' | 'warn' | 'critical'
    next_step: str      # 'none' | 'led_poll' | 'ticket'


def evaluate(olt: OLTData, tariff_speed: int) -> list[Diagnosis]:
    """
    Apply all inference rules (categories A-F) to produce a list of Diagnosis.
    Pure function — no I/O, no side effects.
    """
    results: list[Diagnosis] = []

    # --- Category A: ONU status ---
    is_online = (olt.onu_state == "ready" and olt.phase_state == "working")

    if not is_online:
        results.append(Diagnosis(
            code="ONU_OFFLINE",
            message_key="onu_offline",
            severity="critical",
            next_step="led_poll",
        ))
        return results  # skip B-F when ONU is offline

    results.append(Diagnosis(
        code="ONU_ONLINE",
        message_key="onu_online",
        severity="info",
        next_step="none",
    ))

    # --- Category B: MAC address count ---
    if olt.mac_count == 0:
        results.append(Diagnosis(
            code="NO_MAC",
            message_key="no_mac",
            severity="warn",
            next_step="none",
        ))
    elif olt.mac_count == 1:
        results.append(Diagnosis(
            code="ONE_MAC",
            message_key="one_mac",
            severity="info",
            next_step="none",
        ))
    elif olt.mac_count == 2:
        results.append(Diagnosis(
            code="TWO_MAC",
            message_key="two_mac",
            severity="warn",
            next_step="none",
        ))
    else:
        results.append(Diagnosis(
            code="LOOP_MAC",
            message_key="loop_mac",
            severity="critical",
            next_step="none",
        ))

    # --- Category C: Port speed ---
    if olt.speed_status == "full-1000":
        results.append(Diagnosis(
            code="SPEED_OK_1000",
            message_key="speed_ok_1000",
            severity="info",
            next_step="none",
        ))
    elif olt.speed_status == "full-100" and tariff_speed <= 100:
        results.append(Diagnosis(
            code="SPEED_OK_100",
            message_key="speed_ok_100",
            severity="info",
            next_step="none",
        ))
    elif olt.speed_status == "full-100" and tariff_speed > 100:
        results.append(Diagnosis(
            code="SPEED_DEGRADED",
            message_key="speed_degraded",
            severity="warn",
            next_step="none",
        ))
    elif olt.speed_status == "full-10":
        results.append(Diagnosis(
            code="SPEED_CRITICAL",
            message_key="speed_critical",
            severity="critical",
            next_step="none",
        ))

    # --- Category D: Signal level (never show dBm to user) ---
    if olt.rx_power_dbm > -31.0:
        results.append(Diagnosis(
            code="SIGNAL_OK",
            message_key="signal_ok",
            severity="info",
            next_step="none",
        ))
    else:
        results.append(Diagnosis(
            code="SIGNAL_WEAK",
            message_key="signal_weak",
            severity="warn",
            next_step="none",
        ))

    # --- Category E: Traffic ---
    if olt.input_rate_pps > 0 or olt.output_rate_pps > 0:
        results.append(Diagnosis(
            code="TRAFFIC_PRESENT",
            message_key="traffic_present",
            severity="info",
            next_step="none",
        ))
    else:
        results.append(Diagnosis(
            code="NO_TRAFFIC",
            message_key="no_traffic",
            severity="info",
            next_step="none",
        ))

    # --- Category F: Last event ---
    if olt.last_event == "DyingGasp":
        results.append(Diagnosis(
            code="EVENT_POWER",
            message_key="event_power",
            severity="warn",
            next_step="none",
        ))
    elif olt.last_event == "LOSi":
        results.append(Diagnosis(
            code="EVENT_LOS",
            message_key="event_los",
            severity="warn",
            next_step="none",
        ))

    return results


def evaluate_led(pwr_state: str, pon_state: str, los_state: str) -> Diagnosis:
    """
    Apply Category G (LED indicator) rules.
    pwr_state: 'on' | 'off' | 'blinking'
    pon_state: 'on' | 'off' | 'blinking'
    los_state: 'red' | 'off'
    """
    if pwr_state in ("off", "blinking"):
        return Diagnosis(
            code="LED_POWER_FAIL",
            message_key="led_power_fail",
            severity="critical",
            next_step="ticket",
        )
    if pwr_state == "on" and los_state == "red":
        return Diagnosis(
            code="LED_LOS_FAIL",
            message_key="led_los_fail",
            severity="critical",
            next_step="ticket",
        )
    if pwr_state == "on" and pon_state == "blinking" and los_state == "off":
        return Diagnosis(
            code="LED_AUTH_RETRY",
            message_key="led_auth_retry",
            severity="warn",
            next_step="ticket",
        )
    return Diagnosis(
        code="LED_UNKNOWN",
        message_key="led_unknown",
        severity="warn",
        next_step="ticket",
    )


def compute_result_hash(diagnoses: list[Diagnosis]) -> str:
    """SHA-256 of sorted diagnosis codes — used to detect identical consecutive runs."""
    codes = "|".join(sorted(d.code for d in diagnoses))
    return hashlib.sha256(codes.encode()).hexdigest()
