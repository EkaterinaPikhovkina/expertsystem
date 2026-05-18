from aiogram import Router, F
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

import texts
from database import queries
from keyboards import kb_auth_choice, kb_main_menu, kb_frozen_account, kb_confirm_address, kb_bottom_menu
from states import AuthStates, AccountStates

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Вітаємо у службі технічної підтримки!", reply_markup=kb_bottom_menu())
    await message.answer(texts.WELCOME, reply_markup=kb_auth_choice())


@router.message(F.text == "Головне меню", StateFilter("*"))
async def btn_bottom_main_menu(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    client_id = data.get("client_id")

    await state.clear()

    if client_id:
        await state.update_data(client_id=client_id)
        await message.answer(texts.MAIN_MENU, reply_markup=kb_main_menu())
    else:
        await message.answer(texts.WELCOME, reply_markup=kb_auth_choice())


@router.message(F.text == "Знайти інший договір", StateFilter("*"))
async def btn_bottom_change_contract(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Введіть дані для пошуку іншого договору.", reply_markup=kb_bottom_menu())
    await message.answer(texts.WELCOME, reply_markup=kb_auth_choice())


@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if data.get("client_id"):
        await message.answer(texts.MAIN_MENU, reply_markup=kb_main_menu())
    else:
        await message.answer("Будь ласка, спочатку авторизуйтесь.", reply_markup=kb_auth_choice())


@router.callback_query(F.data == "auth:contract")
async def ask_contract(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(AuthStates.waiting_for_contract)
    await callback.message.answer(texts.ENTER_CONTRACT)


@router.callback_query(F.data == "auth:address")
async def ask_address(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(AuthStates.waiting_for_address)
    await callback.message.answer(texts.ENTER_ADDRESS)


@router.message(AuthStates.waiting_for_contract)
async def handle_contract(message: Message, state: FSMContext, pool) -> None:
    contract = message.text.strip() if message.text else ""
    client = await queries.get_client_by_contract(pool, contract)
    await _process_client(message, state, client)


@router.message(AuthStates.waiting_for_address)
async def handle_address(message: Message, state: FSMContext, pool) -> None:
    address = message.text.strip() if message.text else ""
    client = await queries.get_client_by_address(pool, address)

    if not client:
        await message.answer(texts.CLIENT_NOT_FOUND)
        return

    # Підтвердження адреси
    await state.update_data(found_client=client)
    await state.set_state(AuthStates.confirming_address)
    await message.answer(f"Знайдено адресу: <b>{client['address']}</b>\n\nЦе ваша адреса?",
                         reply_markup=kb_confirm_address())


@router.callback_query(F.data == "addr:yes", AuthStates.confirming_address)
async def confirm_address_yes(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    client = data.get("found_client")
    await _process_client(callback.message, state, client)


@router.callback_query(F.data == "addr:no", AuthStates.confirming_address)
async def confirm_address_no(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(AuthStates.waiting_for_address)
    await callback.message.answer(texts.ENTER_ADDRESS)


async def _process_client(message: Message, state: FSMContext, client: dict | None) -> None:
    if not client:
        await message.answer(texts.CLIENT_NOT_FOUND)
        return

    if float(client["balance"]) < 0:
        await state.clear()
        await message.answer(texts.DEBT.format(balance=float(client["balance"])))
        return

    if client["status"] in ("frozen", "suspended"):
        await state.set_state(AccountStates.unfreeze_confirm)
        await state.update_data(
            client_id=client["id"],
            contract_number=client["contract_number"],
            tariff_price=float(client["tariff_price"]),
        )
        await message.answer(texts.FROZEN, reply_markup=kb_frozen_account())
        return

    await state.clear()
    await state.update_data(
        client_id=client["id"],
        contract_number=client["contract_number"],
    )
    await message.answer(
        f"Вітаємо! Договір <b>{client['contract_number']}</b>.\n\n" + texts.MAIN_MENU,
        reply_markup=kb_main_menu(),
    )
