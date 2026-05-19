"""Smoke：確保各模組能 import，題庫 YAML 能載入。"""


def test_app_imports():
    import app.main  # noqa: F401


def test_question_bank_loads():
    from app.graph.explore.question_bank import load_bank

    bank = load_bank()
    assert len(bank.stages) == 5
    assert bank.stage(1).seeds, "stage 1 should have seeds"


def test_graph_state_schema():
    from app.graph.shared.state import GraphState

    s = GraphState(session_id="x", user_id="u", bu="產險", sme_role="核保 SME")
    assert s.mode == "explore"
    assert s.stage == 1
