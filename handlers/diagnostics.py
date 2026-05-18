import json
from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

import texts
from database import queries
from engine.parser import OLTData
from engine.rules import evaluate, evaluate_led, compute_result_hash, Diagnosis
from keyboards import kb_resolved, kb_led_pwr, kb_led_pon, kb_led_los, kb_main_menu
from states import DiagnosticStates

router = Router()


def olt_data_from_db_row(row: dict) -> OLTData:
    macs = row.get("mac_addresses", "")
    mac_count = len(macs.split(",")) if macs else 0
    phase = row.get("phase_state", "working")

    return OLTData(
        onu_state="ready" if phase == "working" else "offline",
        phase_state=phase,
        mac_count=mac_count,
        speed_status=row.get("port_speed", "auto"),
        rx_power_dbm=float(row.get("rx_power", 0)),
        input_rate_pps=int(row.get("input_rate", 0)),
        output_rate_pps=int(row.get("output_rate", 0)),
        last_event=phase if phase in ('DyingGasp', 'LOSi') else None,
        raw_lines=[],
    )


async def _check_and_maybe_create_ticket(
        pool, client_id: int, issue_type: str, diagnoses: list[Diagnosis], user_ind: int = 0
) -> tuple[bool, int | None]:
    existing = await queries.get_open_ticket(pool, client_id)
    if existing:
        return False, existing["id"]

    diag_text = ", ".join([d.code for d in diagnoses])
    ticket_id = await queries.create_ticket(pool, client_id, issue_type, diag_text, user_ind)
    return True, ticket_id


async def _run_no_internet_diagnostic(callback: CallbackQuery, state: FSMContext, pool) -> None:
    await callback.message.answer(texts.DIAGNOSTIC_START)
    data = await state.get_data()
    client_id = data.get("client_id")
    client = await queries.get_client_by_id(pool, client_id)

    onu_row = await queries.get_onu_data(pool, client_id)
    if not onu_row:
        created, t_id = await _check_and_maybe_create_ticket(pool, client_id, "no_internet", [])
        await callback.message.answer(texts.NO_ONU_DATA + f"\n\nНомер заявки: #{t_id}")
        return

    olt = olt_data_from_db_row(onu_row)
    diagnoses = evaluate(olt, client["speed_limit"])

    if any(d.code == "ONU_OFFLINE" for d in diagnoses):
        await state.update_data(issue_type="no_internet")
        await state.set_state(DiagnosticStates.led_pwr_question)
        await callback.message.answer(texts.LED_INTRO, reply_markup=kb_led_pwr())
        return

    msg = "<b>Результати діагностики:</b>\n" + "\n".join(
        [texts.MESSAGES.get(d.message_key, "") for d in diagnoses if d.severity != 'info'])
    if "TRAFFIC" not in msg: msg += "\nУсі параметри в нормі."

    created, ticket_id = await _check_and_maybe_create_ticket(pool, client_id, "no_internet", diagnoses)
    msg += "\n\n" + texts.TICKET_CREATED.format(ticket_id=ticket_id) if created else "\n\n" + texts.TICKET_ALREADY_OPEN

    msg += texts.RESOLVED_QUESTION
    await state.set_state(DiagnosticStates.no_internet_result)
    await callback.message.answer(msg, reply_markup=kb_resolved())


@router.callback_query(F.data == "menu:no_internet")
async def no_internet_start(callback: CallbackQuery, state: FSMContext, pool) -> None:
    await callback.answer()
    await _run_no_internet_diagnostic(callback, state, pool)


@router.callback_query(F.data == "resolved:no", DiagnosticStates.no_internet_result)
async def no_internet_retry(callback: CallbackQuery, state: FSMContext, pool) -> None:
    await callback.answer()
    await _run_no_internet_diagnostic(callback, state, pool)


# ---------------------------------------------------------------------------
# LED indicator flow
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("led_pwr:"), DiagnosticStates.led_pwr_question)
async def led_pwr_answer(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    pwr = callback.data.split(":")[1]
    await state.update_data(led_pwr=pwr)
    await state.set_state(DiagnosticStates.led_pon_question)
    await callback.message.answer(texts.LED_PON_QUESTION, reply_markup=kb_led_pon())


@router.callback_query(F.data.startswith("led_pon:"), DiagnosticStates.led_pon_question)
async def led_pon_answer(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    pon = callback.data.split(":")[1]
    await state.update_data(led_pon=pon)
    await state.set_state(DiagnosticStates.led_los_question)
    await callback.message.answer(texts.LED_LOS_QUESTION, reply_markup=kb_led_los())


@router.callback_query(F.data.startswith("led_los:"), DiagnosticStates.led_los_question)
async def led_los_answer(callback: CallbackQuery, state: FSMContext, pool) -> None:
    await callback.answer()
    los = callback.data.split(":")[1]
    data = await state.get_data()
    pwr = data.get("led_pwr", "on")
    pon = data.get("led_pon", "on")
    client_id = data.get("client_id")

    diagnosis = evaluate_led(pwr, pon, los)
    msg = texts.MESSAGES.get(diagnosis.message_key, texts.LED_UNKNOWN)

    created, ticket_id = await _check_and_maybe_create_ticket(
        pool, callback.from_user.id, client_id, "no_internet", [diagnosis]
    )
    if ticket_id and not created:
        msg += "\n\n" + texts.TICKET_ALREADY_OPEN
    elif created and ticket_id:
        msg += "\n\n" + texts.TICKET_CREATED.format(ticket_id=ticket_id)

    msg += texts.RESOLVED_QUESTION
    await state.set_state(DiagnosticStates.led_result)
    await callback.message.answer(msg, reply_markup=kb_resolved())


@router.callback_query(F.data == "resolved:no", DiagnosticStates.led_result)
async def led_retry(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.update_data(led_pwr=None, led_pon=None)
    await state.set_state(DiagnosticStates.led_pwr_question)
    await callback.message.answer(texts.LED_INTRO, reply_markup=kb_led_pwr())


# ---------------------------------------------------------------------------
# Low Speed flow
# ---------------------------------------------------------------------------


def _build_diagnosis_text(diagnoses: list[Diagnosis]) -> str:
    issues = [texts.MESSAGES.get(d.message_key, "") for d in diagnoses if d.severity != 'info']

    msg = texts.DIAGNOSIS_HEADER
    if issues:
        msg += "\n\n".join(issues)
    else:
        msg += "Усі показники лінії в нормі."

    return msg


async def _run_low_speed_diagnostic(
        callback: CallbackQuery,
        state: FSMContext,
        pool,
) -> None:
    await callback.message.answer(texts.DIAGNOSTIC_START)

    data = await state.get_data()
    client_id = data.get("client_id")

    client = await queries.get_client_by_id(pool, client_id)

    if not client or not client.get("onu_id"):
        ticket_id = await queries.create_ticket(pool, client_id, "low_speed", "{}")
        await callback.message.answer(
            texts.NO_ONU_DATA + "\n\n" + texts.TICKET_CREATED.format(ticket_id=ticket_id)
        )
        return

    onu_row = await queries.get_onu_data(pool, client["onu_id"])
    if not onu_row:
        ticket_id = await queries.create_ticket(pool, client_id, "low_speed", "{}")
        await callback.message.answer(
            texts.NO_ONU_DATA + "\n\n" + texts.TICKET_CREATED.format(ticket_id=ticket_id)
        )
        return

    olt = olt_data_from_db_row(onu_row)
    diagnoses = evaluate(olt, client["tariff_speed"])

    msg = _build_diagnosis_text(diagnoses)
    msg += texts.LOW_SPEED_EXTRA

    created, ticket_id = await _check_and_maybe_create_ticket(
        pool, callback.from_user.id, client_id, "low_speed", diagnoses
    )
    if ticket_id and not created:
        msg += "\n\n" + texts.TICKET_ALREADY_OPEN
    elif created and ticket_id:
        msg += "\n\n" + texts.TICKET_CREATED.format(ticket_id=ticket_id)

    msg += texts.RESOLVED_QUESTION
    await state.set_state(DiagnosticStates.low_speed_result)
    await callback.message.answer(msg, reply_markup=kb_resolved())


@router.callback_query(F.data == "menu:low_speed")
async def low_speed_start(callback: CallbackQuery, state: FSMContext, pool) -> None:
    await callback.answer()
    await _run_low_speed_diagnostic(callback, state, pool)


@router.callback_query(F.data == "resolved:no", DiagnosticStates.low_speed_result)
async def low_speed_retry(callback: CallbackQuery, state: FSMContext, pool) -> None:
    await callback.answer()
    await _run_low_speed_diagnostic(callback, state, pool)


# ---------------------------------------------------------------------------
# Resolved (yes) — shared by all diagnostic states
# ---------------------------------------------------------------------------

@router.callback_query(
    F.data == "resolved:yes",
    StateFilter(
        DiagnosticStates.no_internet_result,
        DiagnosticStates.led_result,
        DiagnosticStates.low_speed_result,
    ),
)
async def resolved_yes(callback: CallbackQuery, state: FSMContext, pool) -> None:
    await callback.answer()
    data = await state.get_data()
    client_id = data.get("client_id")
    if client_id:
        await queries.close_ticket(pool, client_id)
    await state.clear()
    if client_id:
        await state.update_data(client_id=client_id)
    await callback.message.answer(texts.ISSUE_RESOLVED)
    await callback.message.answer(texts.MAIN_MENU, reply_markup=kb_main_menu())
