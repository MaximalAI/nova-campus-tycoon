"""Smoke test: the project structure is in place and the modules import."""


def test_modules_import():
    import db
    import logic

    assert logic is not None
    assert db is not None
