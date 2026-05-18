from aiogram import Router, F
from aiogram.types import CallbackQuery
from keyboards import kb_ontology_symptoms, kb_main_menu
from engine.ontology_engine import analyze_symptom

router = Router()


@router.callback_query(F.data == "menu:ontology")
async def start_ontology_guide(callback: CallbackQuery) -> None:
    await callback.answer()
    msg = (
        "<b>Розумний довідник несправностей</b>\n\n"
        "Цей розділ використовує семантичну онтологію мережі. "
        "Оберіть симптом, який ви спостерігаєте, і система за допомогою "
        "графа знань побудує логічний ланцюжок причини та вирішення:"
    )
    await callback.message.answer(msg, reply_markup=kb_ontology_symptoms())


@router.callback_query(F.data.startswith("onto:"))
async def process_ontology_symptom(callback: CallbackQuery) -> None:
    await callback.answer()
    symptom_id = callback.data.split(":")[1]

    # Викликаємо рушій онтології
    result_text = analyze_symptom(symptom_id)

    # Відправляємо результат і повертаємо кнопку в головне меню
    await callback.message.answer(result_text)
    await callback.message.answer("Повернутися до головного меню?", reply_markup=kb_main_menu())
