"""Main menu — re-entry point for users who are already authorised."""

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

import texts
from keyboards import kb_main_menu

router = Router()


@router.callback_query(F.data == "menu:main")
async def main_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await state.get_data()
    client_id = data.get("client_id")
    await state.clear()
    if client_id:
        await state.update_data(client_id=client_id)
    await callback.message.answer(texts.MAIN_MENU, reply_markup=kb_main_menu())
