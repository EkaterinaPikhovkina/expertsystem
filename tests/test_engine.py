"""Unit tests for engine/parser.py and engine/rules.py."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from engine.parser import OLTData, parse_olt_output, olt_data_from_db_row
from engine.rules import evaluate, evaluate_led, compute_result_hash, Diagnosis


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _codes(diagnoses: list[Diagnosis]) -> list[str]:
    return [d.code for d in diagnoses]


# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------

SAMPLE_CLI = """
  State: ready
  Phase state: working
  Mac: 6464.4a59.5630
  Speed status: full-1000
  Rx:-25.372(dbm)
  Input rate: 43 pps
  Output rate: 173 pps
"""

SAMPLE_CLI_OFFLINE = """
  State: offline
  Phase state: standby
  Rx:-33.100(dbm)
  Input rate: 0 pps
  Output rate: 0 pps
  LOSi
"""

SAMPLE_CLI_MULTI_MAC = """
  State: ready
  Phase state: working
  Mac: 1111.2222.3333
  Mac: aaaa.bbbb.cccc
  Mac: dead.beef.cafe
  Speed status: full-100
  Rx:-28.500(dbm)
  Input rate: 0 pps
  Output rate: 0 pps
  DyingGasp
"""


class TestParser:
    def test_basic_online(self):
        d = parse_olt_output(SAMPLE_CLI)
        assert d.onu_state == "ready"
        assert d.phase_state == "working"
        assert d.mac_count == 1
        assert d.speed_status == "full-1000"
        assert d.rx_power_dbm == pytest.approx(-25.372)
        assert d.input_rate_pps == 43
        assert d.output_rate_pps == 173
        assert d.last_event is None

    def test_offline_with_los_event(self):
        d = parse_olt_output(SAMPLE_CLI_OFFLINE)
        assert d.onu_state == "offline"
        assert d.mac_count == 0
        assert d.last_event == "LOSi"
        assert d.input_rate_pps == 0

    def test_multi_mac_and_dying_gasp(self):
        d = parse_olt_output(SAMPLE_CLI_MULTI_MAC)
        assert d.mac_count == 3
        assert d.last_event == "DyingGasp"
        assert d.speed_status == "full-100"

    def test_raw_lines_populated(self):
        d = parse_olt_output(SAMPLE_CLI)
        assert len(d.raw_lines) == 2

    def test_missing_fields_use_defaults(self):
        d = parse_olt_output("State: ready\nPhase state: working")
        assert d.rx_power_dbm == -25.0
        assert d.mac_count == 0
        assert d.speed_status == "full-1000"

    def test_db_row_conversion(self):
        row = {
            "onu_id": "gpon-onu_1/1/1:1",
            "onu_state": "ready",
            "phase_state": "working",
            "mac_count": 1,
            "speed_status": "full-1000",
            "rx_power_dbm": -25.372,
            "input_rate_pps": 43,
            "output_rate_pps": 173,
            "last_event": None,
        }
        d = olt_data_from_db_row(row)
        assert d.onu_state == "ready"
        assert d.mac_count == 1
        assert d.rx_power_dbm == pytest.approx(-25.372)


# ---------------------------------------------------------------------------
# Rules tests
# ---------------------------------------------------------------------------

def _make_olt(**kwargs) -> OLTData:
    defaults = dict(
        onu_state="ready",
        phase_state="working",
        mac_count=1,
        speed_status="full-1000",
        rx_power_dbm=-25.0,
        input_rate_pps=100,
        output_rate_pps=200,
        last_event=None,
        raw_lines=[],
    )
    defaults.update(kwargs)
    return OLTData(**defaults)


class TestRules:
    # --- ONU status ---
    def test_onu_online(self):
        olt = _make_olt()
        codes = _codes(evaluate(olt, 100))
        assert "ONU_ONLINE" in codes
        assert "ONU_OFFLINE" not in codes

    def test_onu_offline_stops_further_rules(self):
        olt = _make_olt(onu_state="offline", phase_state="standby")
        result = evaluate(olt, 100)
        codes = _codes(result)
        assert codes == ["ONU_OFFLINE"]
        assert len(result) == 1

    def test_onu_ready_standby_is_offline(self):
        olt = _make_olt(onu_state="ready", phase_state="standby")
        codes = _codes(evaluate(olt, 100))
        assert "ONU_OFFLINE" in codes

    # --- MAC rules ---
    def test_no_mac(self):
        olt = _make_olt(mac_count=0)
        assert "NO_MAC" in _codes(evaluate(olt, 100))

    def test_one_mac(self):
        olt = _make_olt(mac_count=1)
        assert "ONE_MAC" in _codes(evaluate(olt, 100))

    def test_two_mac(self):
        olt = _make_olt(mac_count=2)
        assert "TWO_MAC" in _codes(evaluate(olt, 100))

    def test_loop_mac(self):
        olt = _make_olt(mac_count=5)
        assert "LOOP_MAC" in _codes(evaluate(olt, 100))

    # --- Speed rules ---
    def test_speed_ok_1000(self):
        olt = _make_olt(speed_status="full-1000")
        assert "SPEED_OK_1000" in _codes(evaluate(olt, 1000))

    def test_speed_ok_100_at_100_tariff(self):
        olt = _make_olt(speed_status="full-100")
        assert "SPEED_OK_100" in _codes(evaluate(olt, 100))

    def test_speed_degraded_100_at_500_tariff(self):
        olt = _make_olt(speed_status="full-100")
        assert "SPEED_DEGRADED" in _codes(evaluate(olt, 500))

    def test_speed_critical(self):
        olt = _make_olt(speed_status="full-10")
        assert "SPEED_CRITICAL" in _codes(evaluate(olt, 100))

    # --- Signal rules ---
    def test_signal_ok(self):
        olt = _make_olt(rx_power_dbm=-25.0)
        assert "SIGNAL_OK" in _codes(evaluate(olt, 100))

    def test_signal_weak(self):
        olt = _make_olt(rx_power_dbm=-32.0)
        assert "SIGNAL_WEAK" in _codes(evaluate(olt, 100))

    def test_signal_boundary_exactly_minus31(self):
        olt = _make_olt(rx_power_dbm=-31.0)
        assert "SIGNAL_WEAK" in _codes(evaluate(olt, 100))

    # --- Traffic rules ---
    def test_traffic_present(self):
        olt = _make_olt(input_rate_pps=50, output_rate_pps=100)
        assert "TRAFFIC_PRESENT" in _codes(evaluate(olt, 100))

    def test_no_traffic(self):
        olt = _make_olt(input_rate_pps=0, output_rate_pps=0)
        assert "NO_TRAFFIC" in _codes(evaluate(olt, 100))

    def test_only_output_traffic_counts(self):
        olt = _make_olt(input_rate_pps=0, output_rate_pps=50)
        assert "TRAFFIC_PRESENT" in _codes(evaluate(olt, 100))

    # --- Event rules ---
    def test_event_dying_gasp(self):
        olt = _make_olt(last_event="DyingGasp")
        assert "EVENT_POWER" in _codes(evaluate(olt, 100))

    def test_event_losi(self):
        olt = _make_olt(last_event="LOSi")
        assert "EVENT_LOS" in _codes(evaluate(olt, 100))

    def test_no_event(self):
        olt = _make_olt(last_event=None)
        codes = _codes(evaluate(olt, 100))
        assert "EVENT_POWER" not in codes
        assert "EVENT_LOS" not in codes

    # --- LED rules ---
    def test_led_power_off(self):
        d = evaluate_led("off", "on", "off")
        assert d.code == "LED_POWER_FAIL"

    def test_led_power_blinking(self):
        d = evaluate_led("blinking", "on", "off")
        assert d.code == "LED_POWER_FAIL"

    def test_led_los_red(self):
        d = evaluate_led("on", "on", "red")
        assert d.code == "LED_LOS_FAIL"

    def test_led_pon_blinking_auth(self):
        d = evaluate_led("on", "blinking", "off")
        assert d.code == "LED_AUTH_RETRY"

    # --- Hash ---
    def test_hash_is_deterministic(self):
        diags = evaluate(_make_olt(), 100)
        assert compute_result_hash(diags) == compute_result_hash(diags)

    def test_different_diagnoses_different_hash(self):
        d1 = evaluate(_make_olt(rx_power_dbm=-25.0), 100)
        d2 = evaluate(_make_olt(rx_power_dbm=-35.0), 100)
        assert compute_result_hash(d1) != compute_result_hash(d2)


# ---------------------------------------------------------------------------
# Integration: full scenario walk-through
# ---------------------------------------------------------------------------

class TestScenarios:
    def test_scenario_contract_100001(self):
        """ONU online, 1 MAC, full-1000, good signal, traffic present → all OK."""
        olt = _make_olt(
            mac_count=1, speed_status="full-1000",
            rx_power_dbm=-25.372, input_rate_pps=43, output_rate_pps=173,
        )
        codes = _codes(evaluate(olt, 100))
        assert "ONU_ONLINE" in codes
        assert "ONE_MAC" in codes
        assert "SPEED_OK_1000" in codes
        assert "SIGNAL_OK" in codes
        assert "TRAFFIC_PRESENT" in codes

    def test_scenario_contract_100002(self):
        """ONU offline with LOSi → only ONU_OFFLINE, next_step=led_poll."""
        olt = _make_olt(onu_state="offline", phase_state="standby", last_event="LOSi")
        result = evaluate(olt, 200)
        assert len(result) == 1
        assert result[0].code == "ONU_OFFLINE"
        assert result[0].next_step == "led_poll"

    def test_scenario_contract_100004(self):
        """full-100 at 500 Mbps tariff → SPEED_DEGRADED."""
        olt = _make_olt(
            mac_count=0, speed_status="full-10",
            rx_power_dbm=-26.5, input_rate_pps=200, output_rate_pps=150,
        )
        codes = _codes(evaluate(olt, 500))
        assert "SPEED_CRITICAL" in codes

    def test_scenario_speed_100_at_500mbps(self):
        olt = _make_olt(speed_status="full-100")
        codes = _codes(evaluate(olt, 500))
        assert "SPEED_DEGRADED" in codes
