"""Prueba de humo del arranque visual sin depender de una API activa."""

from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_streamlit_dashboard_starts_with_safety_message():
    script = Path(__file__).parents[2] / "frontend" / "app.py"
    app = AppTest.from_file(script).run(timeout=10)

    assert not app.exception
    assert app.title[0].value == "IAviso Seguro"
    assert "revisión profesional" in app.warning[0].value
    assert app.sidebar.radio[0].value == "Nuevo aviso"
    assert app.text_area[0].label == "Descripción del riesgo"
