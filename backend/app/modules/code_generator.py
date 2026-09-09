"""Module O3a — Analysis Code Generator.

Nhận AnalysisGoal (từ O2) + DataProfile (từ O1), sinh mã pandas để
tính toán các chỉ số cần thiết (tổng theo tháng, tăng trưởng theo
nhóm...).

BẮT BUỘC gọi API LLM (Claude), dùng kỹ thuật "fill-in-the-middle" với
code scaffold cố định (tương tự VISGENERATOR của LIDA, Dibia 2023) —
LLM chỉ điền phần thân hàm `analyze(df) -> dict`, KHÔNG được sinh tự do
toàn bộ chương trình, nhằm giới hạn phạm vi và tăng an toàn khi thực
thi ở module O3b (Sandbox Executor).

Cài đặt dự kiến ở Tuần 4 — xem docs/SRS.md (FR-05).
"""
from __future__ import annotations

from ..schemas import AnalysisGoal, CodeGenResult, DataProfile

# Khung mã cố định (code scaffold) - LLM chỉ điền phần <STUB>.
CODE_SCAFFOLD = '''
def analyze(df):
    """<STUB> - LLM dien logic tinh toan dua tren AnalysisGoal."""
    results = {}
    <STUB>
    return results
'''


def generate(goal: AnalysisGoal, profile: DataProfile) -> CodeGenResult:
    """Sinh mã pandas để thực thi ở Sandbox Executor.

    Raises:
        NotImplementedError: chưa cài đặt (dự kiến Tuần 4).
    """
    raise NotImplementedError(
        "Code Generator se duoc cai dat o Tuan 4 - can thiet ke code "
        "scaffold + prompt fill-in-the-middle (xem docs/SRS.md FR-05)."
    )
