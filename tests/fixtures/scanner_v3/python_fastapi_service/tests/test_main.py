from src.main import app


def test_app_import():
    assert app.title == "FastAPI" or app.title is not None
