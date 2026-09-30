"""Kiểm thử module O3b (Sandbox Executor).

Kiểm tra tất cả các lớp phòng thủ theo thứ tự:
- Lớp 1 (AST): import, hàm nguy hiểm, dunder attribute
- Lớp 2 (multiprocessing): timeout vòng lặp vô hạn
- execute(): code hợp lệ chạy đúng, cú pháp sai trả lỗi không crash

Lưu ý về timeout test: dùng timeout=2s thay vì mặc định 10s để test không chạy lâu.
Spawn context cần thêm vài giây khởi động — nếu CI quá chậm, có thể bỏ mark timeout.
"""
from __future__ import annotations

import pandas as pd
import pytest

from backend.app.modules.sandbox_executor import (
    UnsafeCodeError,
    _static_safety_check,
    execute,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def sample_df() -> pd.DataFrame:
    return pd.DataFrame({
        "Thang": ["2026-01", "2026-02", "2026-03"],
        "Chi_nhanh": ["Ha Noi", "TP.HCM", "Da Nang"],
        "Doanh_thu_trieu_vnd": [100, 200, 150],
    })


# ---------------------------------------------------------------------------
# Lớp 1 — Kiểm tra tĩnh AST (_static_safety_check)
# ---------------------------------------------------------------------------

class TestStaticSafetyCheck:
    def test_safe_code_passes(self):
        """Code hợp lệ không chứa gì cấm → không raise."""
        code = "def analyze(df):\n    return {'trend': df.groupby('Thang')['x'].sum()}"
        _static_safety_check(code)  # Không raise = pass

    def test_blocks_import_os(self):
        """import os bị chặn ngay ở Lớp 1, không được thực thi."""
        code = "import os\ndef analyze(df):\n    return {}"
        with pytest.raises(UnsafeCodeError, match="import"):
            _static_safety_check(code)

    def test_blocks_from_import(self):
        """from sys import path cũng bị chặn."""
        code = "from sys import path\ndef analyze(df):\n    return {}"
        with pytest.raises(UnsafeCodeError, match="import"):
            _static_safety_check(code)

    def test_blocks_eval_call(self):
        """Gọi eval() bị chặn."""
        code = "def analyze(df):\n    eval('1+1')\n    return {}"
        with pytest.raises(UnsafeCodeError, match="eval"):
            _static_safety_check(code)

    def test_blocks_exec_call(self):
        """Gọi exec() bị chặn."""
        code = "def analyze(df):\n    exec('x=1')\n    return {}"
        with pytest.raises(UnsafeCodeError, match="exec"):
            _static_safety_check(code)

    def test_blocks_open_call(self):
        """Gọi open() bị chặn."""
        code = "def analyze(df):\n    f = open('/etc/passwd')\n    return {}"
        with pytest.raises(UnsafeCodeError, match="open"):
            _static_safety_check(code)

    def test_blocks_dunder_attribute_class(self):
        """Truy cập __class__ bị chặn — đây là bước đầu của nhiều kỹ thuật bypass."""
        code = "def analyze(df):\n    t = df.__class__\n    return {}"
        with pytest.raises(UnsafeCodeError, match="__class__"):
            _static_safety_check(code)

    def test_blocks_dunder_attribute_bases(self):
        """Truy cập __bases__ bị chặn."""
        code = "def analyze(df):\n    x = object.__bases__\n    return {}"
        with pytest.raises(UnsafeCodeError, match="__bases__"):
            _static_safety_check(code)

    def test_blocks_dunder_subclasses(self):
        """Truy cập __subclasses__ bị chặn."""
        code = "def analyze(df):\n    x = ().__class__.__bases__[0].__subclasses__()\n    return {}"
        with pytest.raises(UnsafeCodeError):
            _static_safety_check(code)

    def test_syntax_error_raises_syntax_error_not_unsafe(self):
        """Cú pháp sai → SyntaxError (không phải UnsafeCodeError)."""
        code = "def analyze(df\n    return {}"
        with pytest.raises(SyntaxError):
            _static_safety_check(code)


# ---------------------------------------------------------------------------
# execute() — code hợp lệ
# ---------------------------------------------------------------------------

class TestExecuteValidCode:
    def test_execute_trend_code(self, sample_df):
        """Code trend hợp lệ → ExecutionResult(success=True) với kết quả đúng."""
        code = """\
def analyze(df):
    trend = df.groupby("Thang")["Doanh_thu_trieu_vnd"].sum()
    return {"trend": trend.to_dict()}
"""
        result = execute(code, sample_df)
        assert result.success is True
        assert "trend" in result.results
        assert result.error is None

    def test_execute_comparison_code(self, sample_df):
        """Code comparison trả về dict hợp lệ."""
        code = """\
def analyze(df):
    comp = df.groupby("Chi_nhanh")["Doanh_thu_trieu_vnd"].sum()
    return {"comparison": comp.to_dict()}
"""
        result = execute(code, sample_df)
        assert result.success is True
        assert "comparison" in result.results

    def test_execute_growth_rate_code(self, sample_df):
        """Code growth_rate với 2 key."""
        code = """\
def analyze(df):
    grouped = df.groupby("Chi_nhanh")["Doanh_thu_trieu_vnd"].sum()
    pct = (grouped / grouped.sum() * 100).round(2)
    target = pct.idxmin()
    return {"growth_rate": pct.to_dict(), "target": target}
"""
        result = execute(code, sample_df)
        assert result.success is True
        assert "growth_rate" in result.results
        assert "target" in result.results

    def test_execute_returns_error_on_syntax_error(self, sample_df):
        """Cú pháp sai → success=False, không crash tiến trình chính."""
        code = "def analyze(df\n    return {}"
        result = execute(code, sample_df)
        assert result.success is False
        assert result.error is not None

    def test_execute_returns_error_when_analyze_not_defined(self, sample_df):
        """Code không có hàm analyze() → success=False."""
        code = "x = 42"
        result = execute(code, sample_df)
        assert result.success is False
        assert "analyze" in result.error.lower()

    def test_execute_returns_error_on_runtime_exception(self, sample_df):
        """Lỗi runtime trong analyze() → success=False, không crash."""
        code = """\
def analyze(df):
    raise ValueError("Lỗi cố tình")
"""
        result = execute(code, sample_df)
        assert result.success is False
        assert result.error is not None


# ---------------------------------------------------------------------------
# Lớp 1 ngăn execute — UnsafeCodeError trước khi spawn process
# ---------------------------------------------------------------------------

class TestExecuteBlockedByAST:
    def test_execute_raises_unsafe_code_error_for_import(self, sample_df):
        """import os → UnsafeCodeError raised TRƯỚC khi tiến trình được tạo."""
        code = "import os\ndef analyze(df):\n    return {}"
        with pytest.raises(UnsafeCodeError):
            execute(code, sample_df)

    def test_execute_raises_unsafe_code_error_for_dunder(self, sample_df):
        """Truy cập __class__ → UnsafeCodeError."""
        code = "def analyze(df):\n    t = df.__class__\n    return {}"
        with pytest.raises(UnsafeCodeError):
            execute(code, sample_df)


# ---------------------------------------------------------------------------
# Lớp 2 — Timeout vòng lặp vô hạn
# ---------------------------------------------------------------------------

class TestExecuteTimeout:
    def test_infinite_loop_times_out(self, sample_df):
        """Vòng lặp vô hạn bị terminate() sau timeout.

        Dùng timeout=2s để test nhanh hơn (mặc định 10s).
        Spawn context cần ~1-2s khởi động, nên 2s là đủ phân biệt.
        """
        code = """\
def analyze(df):
    while True:
        pass
"""
        result = execute(code, sample_df, timeout=2)
        assert result.success is False
        assert "timeout" in result.error.lower() or "thời gian" in result.error.lower()
