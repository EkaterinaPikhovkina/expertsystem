from decimal import Decimal

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from engine.ontology_engine import get_symptoms


def _kb(*rows: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    """Helper: rows is list of lists of (text, callback_data)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t, callback_data=c) for t, c in row]
            for row in rows
        ]
    )


def kb_auth_choice() -> InlineKeyboardMarkup:
    return _kb(
        [("Номер договору", "auth:contract")],
        [("Адреса проживання", "auth:address")],
    )


def kb_confirm_address() -> InlineKeyboardMarkup:
    return _kb(
        [("Так, це моя адреса", "addr:yes")],
        [("Ні, шукати іншу", "addr:no")]
    )


def kb_main_menu() -> InlineKeyboardMarkup:
    return _kb(
        [("Немає інтернету", "menu:no_internet")],
        [("Низька швидкість",  "menu:low_speed")],
        [("Мій рахунок",       "menu:balance")],
        [("Розморозка договору", "menu:unfreeze")],
        [("🔍 Розумний довідник", "menu:ontology")]
    )


def kb_resolved() -> InlineKeyboardMarkup:
    return _kb(
        [("Так, проблему вирішено", "resolved:yes")],
        [("Ні, спробувати ще раз",  "resolved:no")],
    )


def kb_led_pwr() -> InlineKeyboardMarkup:
    return _kb(
        [("Горить (зелений/синій)", "led_pwr:on")],
        [("Не горить", "led_pwr:off")],
        [("Мигає", "led_pwr:blinking")],
    )


def kb_led_pon() -> InlineKeyboardMarkup:
    return _kb(
        [("Горить постійно",  "led_pon:on")],
        [("Не горить",         "led_pon:off")],
        [("Мигає",             "led_pon:blinking")],
    )


def kb_led_los() -> InlineKeyboardMarkup:
    return _kb(
        [("Горить червоним", "led_los:red")],
        [("Не горить", "led_los:off")],
    )


def kb_unfreeze_confirm(fee: Decimal) -> InlineKeyboardMarkup:
    return _kb(
        [("Підтвердити", "unfreeze:confirm")],
        [("Скасувати", "unfreeze:cancel")],
    )


def kb_frozen_account() -> InlineKeyboardMarkup:
    return _kb(
        [("Активувати послугу", "menu:unfreeze")],
    )


def kb_cancel() -> InlineKeyboardMarkup:
    return _kb([("Скасувати", "cancel")])


def kb_ontology_symptoms() -> InlineKeyboardMarkup:
    """Генерує клавіатуру динамічно на основі файлу онтології."""
    symptoms = get_symptoms()
    rows = [[(name, f"onto:{sym_id}")] for sym_id, name in symptoms]
    rows.append([("Назад до меню", "cancel")])
    return _kb(*rows)


def kb_bottom_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="Головне меню"),
                KeyboardButton(text="Знайти інший договір")
            ]
        ],
        resize_keyboard=True,
        is_persistent=True
    )