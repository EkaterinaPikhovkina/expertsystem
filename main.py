import os
from dotenv import load_dotenv
import asyncio
import logging

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage

from database import db_query

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

logging.basicConfig(level=logging.INFO)


class BotStates(StatesGroup):
    waiting_contract = State()
    main_menu = State()
    polling_lamps = State()
    checking_status = State()


def get_main_menu():
    buttons = [
        [InlineKeyboardButton(text="Немає інтернету", callback_data="no_internet")],
        [InlineKeyboardButton(text="Низька швидкість", callback_data="low_speed")],
        [InlineKeyboardButton(text="Мій рахунок", callback_data="my_account")],
        [InlineKeyboardButton(text="Розморозити договір", callback_data="unfreeze")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_solve_kb():
    buttons = [
        [InlineKeyboardButton(text="Вирішено", callback_data="solved")],
        [InlineKeyboardButton(text="Не допомогло", callback_data="not_solved")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await message.answer("Вітаємо! Будь ласка, введіть номер Вашого договору")
    await state.set_state(BotStates.waiting_contract)


@dp.message(BotStates.waiting_contract)
async def auth(message: types.Message, state: FSMContext):
    contract = message.text.strip()
    client = db_query(
        "SELECT c.*, t.price, t.name as t_name FROM clients c JOIN tariffs t ON c.tariff_id = t.id WHERE c.contract_number = %s",
        (contract,), fetch=True)

    if not client:
        await message.answer("Договір не знайдено. Спробуйте ще раз")
        return

    client = client[0]
    await state.update_data(client=client)

    # Перевірка білінгу
    if client['balance'] < 0:
        await message.answer(
            f"Доступ обмежено через заборгованість.\nВаш баланс: {client['balance']} грн.\nПоповніть рахунок для відновлення.")
        return

    if client['status'] in ['frozen', 'suspended']:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="Активувати послугу", callback_data="unfreeze")]])
        await message.answer(
            f"Ваш договір {client['status'] == 'frozen' and 'заморожений' or 'призупинений'}.\nНатисніть кнопку для активації.",
            reply_markup=kb)
        return

    await message.answer(f"Чим я можу допомогти?", reply_markup=get_main_menu())
    await state.set_state(BotStates.main_menu)


@dp.callback_query(F.data.in_(["no_internet", "low_speed"]))
async def start_diag(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    client = data['client']
    issue = callback.data

    # Імітація запиту до OLT
    onu = db_query("SELECT * FROM onu_simulation WHERE client_id = %s", (client['id'],), fetch=True)
    if not onu:
        await callback.message.answer("Дані з обладнання не отримані. Спробуйте пізніше.")
        return

    onu = onu[0]
    results = []
    advice_code = "TRAFFIC_OK"

    # ЕКСПЕРТНА СИСТЕМА (ПРАВИЛА)
    # 1. Стан ONU
    if onu['phase_state'] != 'working':
        if onu['phase_state'] == 'DyingGasp':
            results.append("Оптичний термінал вимкнено (немає живлення).")
        else:
            results.append("Втрата оптичного сигналу (LOSi).")

        # Перехід до ламп
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="LOS горить червоним", callback_data="lamp_los")],
            [InlineKeyboardButton(text="PON мигає", callback_data="lamp_pon")],
            [InlineKeyboardButton(text="PWR не горить", callback_data="lamp_pwr")]
        ])
        await callback.message.answer("\n".join(results) + "\n\nЯка індикація на вашому терміналі?", reply_markup=kb)
        return

    # 2. МАК-адреси
    macs = onu['mac_addresses'].split(',') if onu['mac_addresses'] else []
    if len(macs) == 0:
        advice_code = "NO_MAC"
    elif len(macs) > 2:
        advice_code = "MAC_MANY"

    # 3. Сигнал
    if onu['rx_power'] < -31:
        advice_code = "SIGNAL_LOW"

    # 4. Порт
    if client['tariff_id'] == 2 and onu['port_speed'] == 'full-100':  # Гігабітний тариф, але лінк 100
        advice_code = "PORT_SPEED_100"

    # Отримання тексту рекомендації
    advice = db_query("SELECT * FROM recommendations WHERE trigger_code = %s", (advice_code,), fetch=True)[0]

    # Збереження для перевірки на повтор
    last_diag = f"{onu['phase_state']}|{onu['port_speed']}|{onu['rx_power']}"
    if data.get('last_diag') == last_diag:
        # Створення тікета (повторна діагностика)
        db_query("INSERT INTO tickets (client_id, issue_type, diag_summary) VALUES (%s, %s, %s)",
                 (client['id'], issue, f"RETRY: {last_diag}"), commit=True)
        await callback.message.answer(
            "Діагностика вдруге показала ті ж самі дані. Я створив заявку для техніка, він зв'яжеться з вами.")
    else:
        await state.update_data(last_diag=last_diag)
        await callback.message.answer(f"🔍 **{advice['title']}**\n\n{advice['advice_text']}",
                                      reply_markup=get_solve_kb(), parse_mode="Markdown")


@dp.callback_query(F.data == "solved")
async def solved(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Радий був допомогти! Бажаємо гарного зв'язку.", reply_markup=get_main_menu())


@dp.callback_query(F.data == "not_solved")
async def not_solved(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Спробуйте ще раз виконати рекомендації. Зараз я запущу повторну перевірку...")
    await asyncio.sleep(2)
    await start_diag(callback, state)


@dp.callback_query(F.data == "unfreeze")
async def unfreeze(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    client = data['client']

    if client['balance'] < client['price']:
        await callback.message.answer(
            f"Недостатньо коштів. Для розморозки покладіть на баланс {client['price']} грн.\nВаш баланс: {client['balance']} грн.")
    else:
        db_query("UPDATE clients SET status = 'active', balance = balance - %s WHERE id = %s", (0.00, client['id']),
                 commit=True)
        await callback.message.answer("Договір активовано! Приємного користування.")
        await auth(callback.message, state)  # Оновити статус в сесії


@dp.callback_query(F.data == "my_account")
async def my_account(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    cl = data['client']
    await callback.message.answer(
        f"Договір: {cl['contract_number']}\nБаланс: {cl['balance']} грн\nТариф: {cl['t_name']}\nАдреса: {cl['address']}",
        reply_markup=get_main_menu())


@dp.callback_query(F.data.startswith("lamp_"))
async def lamp_logic(callback: types.CallbackQuery, state: FSMContext):
    lamp = callback.data
    data = await state.get_data()
    client = data['client']

    responses = {
        "lamp_pwr": "Проблема з блоком живлення. Спробуйте іншу розетку. Якщо не допоможе — потрібна заміна терміналу.",
        "lamp_los": "Це означає фізичний обрив кабелю. Я створюю тікет на виїзд майстра.",
        "lamp_pon": "Термінал бачить сигнал, але не може авторизуватись. Спробуйте вимкнути його з розетки на 5 хв."
    }

    # Якщо LOS або PWR - створюємо тікет відразу
    if lamp in ["lamp_los", "lamp_pwr"]:
        db_query(
            "INSERT INTO tickets (client_id, issue_type, diag_summary, user_indication) VALUES (%s, 'no_internet', 'Lamp Problem', %s)",
            (client['id'], 1), commit=True)

    await callback.message.answer(responses[lamp], reply_markup=get_main_menu())


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
