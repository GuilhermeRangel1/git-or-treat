from app.schemas.chat_visualization import ChatVisualPoint
from app.services.visual_reading import build_visual_reading


def points(values):
    return [
        ChatVisualPoint(observation_id=f"row_{i}", label=f"2026-{i:02d}", value=v)
        for i, v in enumerate(values, 1)
    ]


def test_reading_reconciles_change_and_peak_without_claiming_cause():
    reading = build_visual_reading(
        points([100, 120, 110]), kind="line", unit="R$", precision=2
    )
    assert "aumento de R$ 10,00" in reading.summary
    assert "10,00%" in reading.summary
    assert "R$ 120,00, em Fev/2026" in reading.summary
    assert reading.observation_ids == ("row_1", "row_2", "row_3")


def test_zero_base_has_no_percentage_and_ranking_is_not_share():
    zero = build_visual_reading(points([0, 10]), kind="bars", unit="kWh", precision=2)
    assert "%" not in zero.summary
    assert "aumento de 10,00 kWh" in zero.summary
    ranking = build_visual_reading(
        points([2, 4, 3]), kind="horizontal", unit="h/UC", precision=6
    )
    assert "4,000000 h/UC" in ranking.summary
    assert "não representa participação" in ranking.summary
    assert "%" not in ranking.summary
