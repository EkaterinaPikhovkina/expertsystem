from decimal import Decimal

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

import texts
from database import queries
from keyboards import kb_main_menu, kb_unfreeze_confirm
from states import AccountStates

router = Router()


@router.callback_query(F.data == "menu:balance")
async def show_balance(callback: CallbackQuery, state: FSMContext, pool) -> None:
    await callback.answer()
    data = await state.get_data()
    client_id = data.get("client_id")
    if not client_id:
        await callback.message.answer(texts.CLIENT_NOT_FOUND)
        return

    client = await queries.get_client_by_id(pool, client_id)
    if not client:
        await callback.message.answer(texts.CLIENT_NOT_FOUND)
        return

    status_label = texts.STATUS_LABELS.get(client["status"], client["status"])
    await callback.message.answer(
        texts.BALANCE_INFO.format(
            contract_number=client["contract_number"],
            balance=float(client["balance"]),
            tariff_speed=client["speed_limit"],
            status_label=status_label,
        )
    )


@router.callback_query(F.data == "menu:unfreeze")
async def start_unfreeze(callback: CallbackQuery, state: FSMContext, pool) -> None:
    await callback.answer()
    data = await state.get_data()
    client_id = data.get("client_id")
    if not client_id:
        await callback.message.answer(texts.CLIENT_NOT_FOUND)
        return

    client = await queries.get_client_by_id(pool, client_id)
    if not client:
        await callback.message.answer(texts.CLIENT_NOT_FOUND)
        return

    if client["status"] not in ("frozen", "suspended"):
        await callback.message.answer("Ваш договір наразі активний. Розморозка не потрібна.")
        return

    fee = Decimal(str(client.get("tariff_price", 0)))
    balance = Decimal(str(client["balance"]))

    if balance < fee:
        await callback.message.answer(
            f"<b>Недостатньо коштів для відновлення послуги.</b>\n\n"
            f"Поточний баланс: <b>{balance:.2f} грн</b>\n"
            f"Вартість розморозки: <b>{fee:.2f} грн</b>\n\n"
            f"Будь ласка, поповніть рахунок на суму {(fee - balance):.2f} грн."
        )
        return

    await state.set_state(AccountStates.unfreeze_confirm)
    await state.update_data(monthly_fee=float(fee))
    await callback.message.answer(
        texts.UNFREEZE_PROMPT.format(fee=float(fee)),
        reply_markup=kb_unfreeze_confirm(fee),
    )


@router.callback_query(F.data == "unfreeze:confirm", AccountStates.unfreeze_confirm)
async def confirm_unfreeze(callback: CallbackQuery, state: FSMContext, pool) -> None:
    await callback.answer()
    data = await state.get_data()
    client_id = data.get("client_id")
    fee = Decimal(str(data.get("monthly_fee", 0)))

    await queries.mock_payment(pool, client_id, fee)
    await state.clear()
    await state.update_data(client_id=client_id)
    await callback.message.answer(texts.UNFREEZE_SUCCESS)
    await callback.message.answer(texts.MAIN_MENU, reply_markup=kb_main_menu())


@router.callback_query(F.data == "unfreeze:cancel", AccountStates.unfreeze_confirm)
async def cancel_unfreeze(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await state.get_data()
    client_id = data.get("client_id")
    await state.clear()
    if client_id:
        await state.update_data(client_id=client_id)
    await callback.message.answer(texts.UNFREEZE_CANCEL)
    await callback.message.answer(texts.MAIN_MENU, reply_markup=kb_main_menu())


@router.callback_query(F.data == "cancel")
async def cancel_any(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await state.get_data()
    client_id = data.get("client_id")
    await state.clear()
    if client_id:
        await state.update_data(client_id=client_id)
    await callback.message.answer(texts.MAIN_MENU, reply_markup=kb_main_menu())
