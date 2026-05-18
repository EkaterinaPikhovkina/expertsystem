import json
import os

ONTOLOGY_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ontology.json")


def load_ontology() -> dict:
    with open(ONTOLOGY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_symptoms() -> list[tuple[str, str]]:
    onto = load_ontology()
    return [(node_id, data["name"])
            for node_id, data in onto["nodes"].items()
            if data["type"] == "Symptom"]


def analyze_symptom(symptom_id: str) -> str:
    onto = load_ontology()
    nodes = onto["nodes"]
    edges = onto["edges"]

    if symptom_id not in nodes:
        return "Симптом не знайдено в базі знань."

    symptom_name = nodes[symptom_id]["name"]

    # Знаходимо обладнання (affects)
    affected_eq = [e["target"] for e in edges if e["source"] == symptom_id and e["relation"] == "affects"]

    # Знаходимо причини (caused_by)
    causes = [e["target"] for e in edges if e["source"] == symptom_id and e["relation"] == "caused_by"]

    # Знаходимо рішення для цих причин (mitigated_by, solved_by)
    actions_set = set()
    for cause in causes:
        actions_set.update(
            [e["target"] for e in edges if e["source"] == cause and e["relation"] in ("mitigated_by", "solved_by")])

    actions = list(actions_set)

    # Формування тексту результату
    eq_text = ", ".join([nodes[eq]["name"] for eq in affected_eq]) or "Не визначено"
    cause_text = ", ".join([nodes[c]["name"] for c in causes]) or "Не визначено"
    action_text = "\n".join([f"• {nodes[a]['name']}" for a in actions]) or "Відсутні"

    report = (
        f"<b>Аналіз за базою знань (онтологією)</b>\n\n"
        f"<b>Обраний симптом:</b> {symptom_name}\n\n"
        f"<b>Пов'язане обладнання:</b> {eq_text}\n"
        f"<b>Імовірна причина:</b> {cause_text}\n\n"
        f"<b>Рекомендовані дії:</b>\n{action_text}\n\n"
        f"<b>Як бот зробив цей висновок (логіка графа):</b>\n"
        f"<i>Система знайшла вузол <b>[{symptom_name}]</b>. "
        f"Через зв'язок типу 'affects' знайдено обладнання <b>[{eq_text}]</b>. "
        f"Через зв'язок 'caused_by' знайдена першопричина <b>[{cause_text}]</b>. "
        f"Далі рушій перейшов від причини через зв'язки 'mitigated_by/solved_by', "
        f"щоб запропонувати вам відповідні дії.</i>"
    )

    return report
