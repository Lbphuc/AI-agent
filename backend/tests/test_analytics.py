"""Kiem thu toan dien cho Phan tich sau 3 cap & Mode Pills (analytics package).

Bao gom:
1. compute_availability & resolve_levels tren doanh_thu.csv va kinh_doanh_36thang.csv.
2. diagnostic: tim dung driver Da Nang (-279) va Da Nang x Dien tu (-381), tuong quan trong chuoi r ~ 0.46.
3. forecast: guard tu choi < 15 ky, chon mo hinh co mua tren 36 thang, dai bat dinh conformal.
4. verify: bo kiem chung bat fake ID, bia so, thieu caveat, khang dinh tuyet doi.
5. Endpoints: /profile tra availability, /interpret tra InterpretResponse, /analyze nhan goal, /deepen.
"""
from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.modules import data_profiler, question_interpreter
from backend.app.modules.analytics import (
    compute_availability,
    resolve_levels,
    run_diagnostic,
    run_forecast,
    run_prescriptive,
    verify_all_recommendations,
    verify_recommendation,
)
from backend.app.schemas import (
    AnalysisGoal,
    AnalysisTask,
    Fact,
    ModeAvailability,
    Recommendation,
)

SAMPLE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "samples"
DOANH_THU_CSV = SAMPLE_DIR / "doanh_thu.csv"
KINH_DOANH_36THANG_CSV = SAMPLE_DIR / "kinh_doanh_36thang.csv"


@pytest.fixture(scope="module")
def df_36m() -> pd.DataFrame:
    assert KINH_DOANH_36THANG_CSV.exists(), "kinh_doanh_36thang.csv chua duoc sinh"
    return pd.read_csv(KINH_DOANH_36THANG_CSV, encoding="utf-8-sig")


@pytest.fixture(scope="module")
def df_12m() -> pd.DataFrame:
    assert DOANH_THU_CSV.exists(), "doanh_thu.csv khong ton tai"
    return pd.read_csv(DOANH_THU_CSV)


# ===========================================================================
# 1. Test Availability & Resolve Levels
# ===========================================================================

def test_availability_doanh_thu_12_periods(df_12m: pd.DataFrame):
    """Tren doanh_thu.csv (12 ky): forecast phai bi khoa voi ly do 'hien co 12'."""
    prof = data_profiler.profile(df_12m)
    avail, freq, n_per = compute_availability(df_12m, prof)

    assert avail["descriptive"].available is True
    assert avail["diagnostic"].available is True
    assert avail["forecast"].available is False
    assert "15" in (avail["forecast"].reason or "")
    assert "12" in (avail["forecast"].reason or "")
    # Prescriptive kha dung vi diagnostic kha dung
    assert avail["prescriptive"].available is True


def test_availability_kinh_doanh_36_periods(df_36m: pd.DataFrame):
    """Tren kinh_doanh_36thang.csv (36 ky): ca 4 cap deu kha dung."""
    prof = data_profiler.profile(df_36m)
    avail, freq, n_per = compute_availability(df_36m, prof)

    assert avail["descriptive"].available is True
    assert avail["diagnostic"].available is True
    assert avail["forecast"].available is True
    assert avail["prescriptive"].available is True
    assert freq == "monthly"
    assert n_per == 36


def test_resolve_levels_table():
    """Kiem thu 8 truong hop hop nhat mode, goal.levels va do kha dung tu de xuat."""
    all_ok = {
        "descriptive": ModeAvailability(available=True),
        "diagnostic": ModeAvailability(available=True),
        "forecast": ModeAvailability(available=True),
        "prescriptive": ModeAvailability(available=True),
    }
    fc_blocked = {
        "descriptive": ModeAvailability(available=True),
        "diagnostic": ModeAvailability(available=True),
        "forecast": ModeAvailability(available=False, reason="Thiếu kỳ dữ liệu"),
        "prescriptive": ModeAvailability(available=True),
    }

    # 1. auto + [descriptive] -> [descriptive], khong thong bao
    lvls, notices = resolve_levels("auto", ["descriptive"], all_ok)
    assert lvls == ["descriptive"]
    assert len(notices) == 0

    # 2. auto + [descriptive, forecast] khi forecast ✗ -> [descriptive] + thong bao bo qua co ly do
    lvls, notices = resolve_levels("auto", ["descriptive", "forecast"], fc_blocked)
    assert lvls == ["descriptive"]
    assert any(n.kind == "skipped" and n.level == "forecast" for n in notices)

    # 3. diagnostic + [descriptive] -> [descriptive, diagnostic]
    lvls, notices = resolve_levels("diagnostic", ["descriptive"], all_ok)
    assert lvls == ["descriptive", "diagnostic"]

    # 4. descriptive + [descriptive, diagnostic] -> [descriptive, diagnostic] + thong bao da them
    lvls, notices = resolve_levels("descriptive", ["descriptive", "diagnostic"], all_ok)
    assert lvls == ["descriptive", "diagnostic"]
    assert any(n.kind == "added" and n.level == "diagnostic" for n in notices)

    # 5. forecast + [descriptive] khi forecast ✗ -> [descriptive] + thong bao bo qua
    lvls, notices = resolve_levels("forecast", ["descriptive"], fc_blocked)
    assert lvls == ["descriptive"]
    assert any(n.kind == "skipped" and n.level == "forecast" for n in notices)

    # 6. prescriptive + diagnostic ✓, forecast ✗ -> [descriptive, diagnostic, prescriptive] + thong bao bo qua forecast
    lvls, notices = resolve_levels("prescriptive", ["descriptive"], fc_blocked)
    assert lvls == ["descriptive", "diagnostic", "prescriptive"]
    assert any(n.kind == "skipped" and n.level == "forecast" for n in notices)

    # 7. prescriptive khi ca hai ✗ -> [descriptive] + thong bao
    both_blocked = {
        "descriptive": ModeAvailability(available=True),
        "diagnostic": ModeAvailability(available=False, reason="Thiếu nhóm"),
        "forecast": ModeAvailability(available=False, reason="Thiếu kỳ"),
        "prescriptive": ModeAvailability(available=False),
    }
    lvls, notices = resolve_levels("prescriptive", ["descriptive"], both_blocked)
    assert lvls == ["descriptive"]
    assert any(n.kind == "skipped" and n.level == "prescriptive" for n in notices)

    # 8. mode la / trung lap -> coi nhu auto, khong trung lap cap
    lvls, _ = resolve_levels("unknown_mode", ["descriptive", "descriptive"], all_ok)
    assert lvls == ["descriptive"]


# ===========================================================================
# 2. Test Diagnostic
# ===========================================================================

def test_diagnostic_drivers_on_36m(df_36m: pd.DataFrame):
    """Chan doan phai tim dung driver Da Nang (-279) va (Da Nang, Dien tu) (-381)."""
    prof = data_profiler.profile(df_36m)
    goal = AnalysisGoal(
        question="Vì sao doanh thu Đà Nẵng giảm?",
        time_scope="last_12_months",
        tasks=[
            AnalysisTask(type="growth_rate", metric="Doanh_thu_trieu_vnd", group_by="Chi_nhanh", find="min")
        ],
    )

    section, facts = run_diagnostic(df_36m, prof, goal, llm=None)
    assert section.level == "diagnostic"
    assert len(facts) >= 3

    # Kiem tra driver Da Nang
    dn_fact = next((f for f in facts if f.entity == "Đà Nẵng" and f.kind == "contribution"), None)
    assert dn_fact is not None
    # Delta cua Da Nang gan -279 (±3%)
    assert abs(dn_fact.value - (-279.0)) < 10.0

    # Kiem tra drill-down Da Nang x Dien tu
    sub_driver_fact = next((f for f in facts if f.kind == "driver"), None)
    assert sub_driver_fact is not None
    assert "Điện tử" in (sub_driver_fact.entity or "")
    assert abs(sub_driver_fact.value - (-381.0)) < 15.0

    # Kiem tra tuong quan marketing trong tung chuoi r ~ 0.46 (±0.15)
    mkt_corr = next((f for f in facts if f.kind == "correlation" and "marketing" in f.text.lower()), None)
    assert mkt_corr is not None
    assert 0.30 <= mkt_corr.value <= 0.65
    # Khong duoc lay r gop ~ 0.83 lam ket qua
    assert mkt_corr.value < 0.75


# ===========================================================================
# 3. Test Forecast
# ===========================================================================

def test_forecast_guard_rejects_under_15_periods(df_12m: pd.DataFrame):
    """Guard phai tu choi du bao tren du lieu < 15 ky."""
    prof = data_profiler.profile(df_12m)
    goal = AnalysisGoal(
        question="Dự báo doanh thu quý tới",
        time_scope="last_12_months",
        tasks=[AnalysisTask(type="trend", metric="Doanh_thu_trieu_vnd")],
    )

    section, facts = run_forecast(df_12m, prof, goal, h=3, llm=None)
    assert len(facts) == 0
    assert len(section.warnings) > 0
    assert any("15" in w for w in section.warnings)


def test_forecast_seasonality_and_band_on_36m(df_36m: pd.DataFrame):
    """Tren 36 thang co mua vu ro: mo hinh co mua vu thang, MAPE < 6%, dai 80% hop le."""
    prof = data_profiler.profile(df_36m)
    goal = AnalysisGoal(
        question="Dự báo doanh thu 3 tháng tới",
        time_scope="last_12_months",
        tasks=[AnalysisTask(type="trend", metric="Doanh_thu_trieu_vnd")],
    )

    section, facts = run_forecast(df_36m, prof, goal, h=3, llm=None)
    assert section.level == "forecast"
    assert len(facts) >= 4  # 1 model fact + 3 forecast facts

    model_fact = next(f for f in facts if f.id == "F_FC_MODEL")
    # MAPE phai tot < 8%
    assert model_fact.value < 8.0

    # 3 diem du bao
    fc_facts = [f for f in facts if f.estimate and f.id.startswith("F_FC_")]
    assert len(fc_facts) == 3

    # Kiem tra bieu do co band va forecast_from
    assert len(section.charts) == 1
    chart = section.charts[0]
    assert chart.band is not None
    assert "lower" in chart.band and "upper" in chart.band
    assert chart.forecast_from == "2026-01"

    # lower <= forecast <= upper
    lowers = [v for v in chart.band["lower"] if v is not None]
    uppers = [v for v in chart.band["upper"] if v is not None]
    fcs = [v for v in chart.series["Dự báo"] if v is not None]

    for low, fc, up in zip(lowers, fcs, uppers):
        assert low <= fc <= up
        assert low >= 0.0


# ===========================================================================
# 4. Test Verification Engine
# ===========================================================================

def test_verify_recommendations():
    """Kiem thu bo loc tat dinh verify: bat fake ID, so bia, thieu caveat."""
    facts = [
        Fact(id="F1", kind="total", metric="Doanh thu", value=1419.0, text="Tổng doanh thu tăng 1.419 triệu VNĐ."),
        Fact(id="F2", kind="contribution", entity="Đà Nẵng", metric="Doanh thu", value=-279.0, text="Đà Nẵng giảm 279 triệu VNĐ."),
        Fact(id="F3", kind="forecast", entity="Tổng", metric="Doanh thu", value=1909.0, estimate=True, text="(ƯỚC TÍNH) Doanh thu kỳ tới đạt 1.909 triệu VNĐ."),
    ]
    facts_map = {f.id: f for f in facts}

    # 1. Hop le
    good_rec = Recommendation(
        title="Tối ưu chi nhánh Đà Nẵng",
        action="Rà soát hoạt động chi nhánh Đà Nẵng sau mức giảm 279 triệu VNĐ",
        rationale="Đà Nẵng là yếu tố kéo giảm mạnh nhất theo F2",
        fact_ids=["F2"],
        priority="cao",
        caveat="Cần kiểm chứng biên lợi nhuận thực tế và chi phí mặt bằng.",
    )
    ok, reason = verify_recommendation(good_rec, facts_map)
    assert ok is True

    # 2. Fake fact_id
    fake_id_rec = Recommendation(
        title="Đề xuất",
        action="Hành động",
        rationale="Lý do",
        fact_ids=["F99"],
        priority="cao",
        caveat="Caveat kiểm chứng",
    )
    ok, reason = verify_recommendation(fake_id_rec, facts_map)
    assert ok is False
    assert "F99" in (reason or "")

    # 3. So bia dat (hallucination)
    fake_num_rec = Recommendation(
        title="Đầu tư thêm",
        action="Bổ sung ngân sách 500 triệu VNĐ cho Đà Nẵng",
        rationale="Vì Đà Nẵng giảm 279 triệu VNĐ",
        fact_ids=["F2"],
        priority="cao",
        caveat="Cần kiểm chứng ngân sách.",
    )
    ok, reason = verify_recommendation(fake_num_rec, facts_map)
    assert ok is False
    assert "500" in (reason or "")

    # 4. Thieu caveat
    no_caveat_rec = Recommendation(
        title="Đề xuất",
        action="Đà Nẵng giảm 279 triệu",
        rationale="Dựa trên F2",
        fact_ids=["F2"],
        priority="cao",
        caveat="",
    )
    ok, reason = verify_recommendation(no_caveat_rec, facts_map)
    assert ok is False
    assert "caveat" in (reason or "").lower()

    # 5. So du bao estimate=True nhung khong ghi 'uoc tinh'
    no_est_rec = Recommendation(
        title="Kế hoạch quý tới",
        action="Chuẩn bị hàng cho doanh thu 1909 triệu của Tổng",
        rationale="Dựa trên F3",
        fact_ids=["F3"],
        priority="trung bình",
        caveat="Cần kiểm chứng nhu cầu thị trường.",
    )
    ok, reason = verify_recommendation(no_est_rec, facts_map)
    assert ok is False
    assert "ước tính" in (reason or "")

    # 6. Khang dinh nguyen nhan tuyet doi
    absolute_rec = Recommendation(
        title="Đề xuất",
        action="Khắc phục vấn đề tại Đà Nẵng giảm 279",
        rationale="Chắc chắn do quản lý yếu kém theo F2",
        fact_ids=["F2"],
        priority="cao",
        caveat="Cần kiểm chứng nhân sự.",
    )
    ok, reason = verify_recommendation(absolute_rec, facts_map)
    assert ok is False
    assert "tuyệt đối" in (reason or "")


# ===========================================================================
# 5. Test API Endpoints
# ===========================================================================

@pytest.fixture
def client(monkeypatch) -> TestClient:
    class MockGemini:
        model_name = "Mock-Gemini"

        def complete_json(self, prompt: str) -> dict:
            return {
                "time_scope": "last_12_months",
                "levels": ["descriptive", "diagnostic"],
                "tasks": [
                    {"type": "growth_rate", "metric": "Doanh_thu_trieu_vnd", "group_by": "Chi_nhanh", "find": "min"}
                ],
            }

        def complete_text(self, prompt: str) -> str:
            return "Đà Nẵng là chi nhánh giảm mạnh nhất trong kỳ phân tích."

    import backend.app.main as main_mod
    monkeypatch.setattr(main_mod, "GeminiClient", MockGemini)
    return TestClient(app)


def test_api_profile_returns_availability(client: TestClient):
    """POST /profile phai tra kem availability va frequency."""
    with open(KINH_DOANH_36THANG_CSV, "rb") as f:
        resp = client.post("/profile", files={"file": ("data.csv", f, "text/csv")})
    assert resp.status_code == 200
    data = resp.json()
    assert "availability" in data
    assert data["availability"]["forecast"]["available"] is True
    assert data["n_periods"] == 36


def test_api_interpret_returns_interpret_response(client: TestClient):
    """POST /interpret phai tra InterpretResponse co goal, levels, notices."""
    with open(KINH_DOANH_36THANG_CSV, "rb") as f:
        resp = client.post(
            "/interpret",
            files={"file": ("data.csv", f, "text/csv")},
            data={"question": "Vì sao doanh thu Đà Nẵng giảm?", "mode": "diagnostic"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "goal" in data
    assert "levels" in data
    assert "diagnostic" in data["levels"]
    assert "goal_summary" in data


def test_api_analyze_with_validated_goal_bypasses_o2(client: TestClient):
    """POST /analyze nhan goal truyen vao, khong loi va tra AnalyzeResponse."""
    goal = {
        "question": "Xu hướng doanh thu theo tháng?",
        "time_scope": "last_12_months",
        "tasks": [{"type": "trend", "metric": "Doanh_thu_trieu_vnd"}],
        "levels": ["descriptive"],
    }
    with open(KINH_DOANH_36THANG_CSV, "rb") as f:
        resp = client.post(
            "/analyze",
            files={"file": ("data.csv", f, "text/csv")},
            data={"question": goal["question"], "goal": json.dumps(goal)},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["goal"]["tasks"][0]["metric"] == "Doanh_thu_trieu_vnd"
    assert "deepen" in data["meta"]


def test_api_analyze_with_invalid_goal_rejects_422(client: TestClient):
    """POST /analyze voi goal tham chieu cot la phai bi chan 422."""
    fake_goal = {
        "question": "Test",
        "time_scope": "last_12_months",
        "tasks": [{"type": "trend", "metric": "Cot_Khong_Ton_Tai_12345"}],
    }
    with open(KINH_DOANH_36THANG_CSV, "rb") as f:
        resp = client.post(
            "/analyze",
            files={"file": ("data.csv", f, "text/csv")},
            data={"question": "Test", "goal": json.dumps(fake_goal)},
        )
    assert resp.status_code == 422


def test_api_deepen_diagnostic_and_forecast(client: TestClient):
    """POST /deepen chay doc lap tung cap diagnostic va forecast."""
    goal = {
        "question": "Vì sao doanh thu thay đổi?",
        "time_scope": "last_12_months",
        "tasks": [{"type": "growth_rate", "metric": "Doanh_thu_trieu_vnd", "group_by": "Chi_nhanh", "find": "min"}],
    }
    with open(KINH_DOANH_36THANG_CSV, "rb") as f:
        resp_diag = client.post(
            "/deepen",
            files={"file": ("data.csv", f, "text/csv")},
            data={"goal": json.dumps(goal), "level": "diagnostic"},
        )
    assert resp_diag.status_code == 200
    diag_data = resp_diag.json()
    assert diag_data["level"] == "diagnostic"
    assert len(diag_data["sections"]) == 1
    assert len(diag_data["facts"]) > 0

    with open(KINH_DOANH_36THANG_CSV, "rb") as f:
        resp_fc = client.post(
            "/deepen",
            files={"file": ("data.csv", f, "text/csv")},
            data={"goal": json.dumps(goal), "level": "forecast"},
        )
    assert resp_fc.status_code == 200
    fc_data = resp_fc.json()
    assert fc_data["level"] == "forecast"
    assert len(fc_data["sections"]) == 1
