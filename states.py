from aiogram.fsm.state import State, StatesGroup


class AuthStates(StatesGroup):
    waiting_for_contract = State()
    waiting_for_address = State()
    confirming_address = State()


class DiagnosticStates(StatesGroup):
    no_internet_result = State()
    led_pwr_question = State()
    led_pon_question = State()
    led_los_question = State()
    led_result = State()
    low_speed_result = State()


class AccountStates(StatesGroup):
    unfreeze_confirm = State()