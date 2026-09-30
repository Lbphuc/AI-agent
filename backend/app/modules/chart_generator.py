"""Module O4 — Chart Generator.

Chuyen ket qua tinh toan (ExecutionResult, tu O3b) thanh ChartSpec de
frontend render bang Plotly/Recharts/Chart.js.

KHONG goi LLM — tai buoc nay, loai phan tich (trend/comparison/...) da
duoc O2 xac dinh ro va so lieu da duoc O3 tinh san, nen chi can mot anh
xa tat dinh (deterministic mapping): "trend" -> line chart,
"comparison" -> bar chart... Khac voi VISGENERATOR cua LIDA (von dung
LLM de ho tro NHIEU ngu phap truc quan hoa bat ky), o day pham vi bieu
do duoc gioi han co chu dich (2 loai: line, bar) nen rule-based nhanh
hon, re hon va khong co rui ro LLM chon sai loai bieu do.

Tuan 5: thay stub bang cai dat that.
"""
from __future__ import annotations

import logging

from ..schemas import AnalysisTask, ChartSpec, ChartType, ExecutionResult, TaskResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Anh xa loai task -> loai bieu do
# ---------------------------------------------------------------------------
_TASK_TYPE_TO_CHART: dict[str, ChartType] = {
    "trend": "line",
    "comparison": "bar",
    "growth_rate": "bar",
}


# ---------------------------------------------------------------------------
# Tieu de bieu do — template tat dinh, KHONG can LLM
# ---------------------------------------------------------------------------
def _build_title(task: AnalysisTask) -> str:
    """Sinh tieu de bieu do tu task.type va task.metric/group_by.

    Tat dinh hoan toan, khong goi LLM — loai phan tich da biet tu O2.
    """
    if task.type == "trend":
        return f"Xu huong {task.metric} theo thoi gian"
    if task.type == "comparison":
        return f"So sanh {task.metric} theo {task.group_by}"
    if task.type == "growth_rate":
        verb = "giam" if task.find == "min" else "tang"
        return f"Chi nhanh {verb} manh nhat — {task.metric} theo {task.group_by}"
    return task.metric  # phong ho — khong nen xay ra vi type da Literal-validated


# ---------------------------------------------------------------------------
# Ham xay ChartSpec tu 1 TaskResult
# ---------------------------------------------------------------------------
def _build_chart(task: AnalysisTask, execution: ExecutionResult) -> ChartSpec | None:
    """Xay ChartSpec tu 1 (task, execution) da thanh cong.

    Tra None thay vi raise neu thieu du lieu — voi AnalysisGoal nhieu
    task, 1 task loi khong nen lam hong bieu do cua cac task khac.

    Args:
        task: AnalysisTask xac dinh loai phan tich va ten cot.
        execution: ExecutionResult da execution.success=True.

    Returns:
        ChartSpec neu du lieu hop le, None neu thieu key hoac rong.
    """
    chart_type = _TASK_TYPE_TO_CHART[task.type]

    # Key trong execution.results phai trung voi task.type (dung theo
    # expected_outputs cua O3a: "trend", "comparison", "growth_rate")
    data_key = task.type
    data = execution.results.get(data_key)

    if not isinstance(data, dict) or not data:
        logger.warning(
            "ExecutionResult thieu key '%s' hoac rong. Nhan duoc: %s",
            data_key, list(execution.results.keys()),
        )
        return None

    # highlight_x: ten category can to noi bat (chi co o growth_rate)
    # Lay tu execution.results["target"] — da duoc O3a san xuat theo scaffold
    highlight_x: str | None = None
    if task.type == "growth_rate":
        highlight_x = execution.results.get("target")
        if highlight_x is not None and not isinstance(highlight_x, str):
            highlight_x = str(highlight_x)

    return ChartSpec(
        chart_type=chart_type,
        title=_build_title(task),
        x=list(data.keys()),
        series={task.metric: [float(v) for v in data.values()]},
        highlight_x=highlight_x,
    )


# ---------------------------------------------------------------------------
# Ham chinh — API cong khai cua module O4
# ---------------------------------------------------------------------------
def generate_charts(task_results: list[TaskResult]) -> list[ChartSpec]:
    """Sinh danh sach ChartSpec tu tat ca TaskResult thanh cong.

    KHONG goi LLM — anh xa tat dinh toan bo.

    Xu ly loi theo tung phan (partial failure): neu 1 task loi (execution.
    success=False hoac thieu du lieu), bieu do cua task do bi bo qua
    (log warning) nhung cac task con lai van duoc xu ly binh thuong. Day
    la lua chon thiet ke co chu dich — nguoi dung van nhan duoc ket qua
    mot phan thay vi mat trang toan bo chi vi 1 task loi.

    Args:
        task_results: danh sach TaskResult tu orchestrator, moi phan tu
            la 1 cap (AnalysisTask, ExecutionResult) tuong ung.

    Returns:
        list[ChartSpec]: co the rong neu tat ca task deu loi hoac thieu
        du lieu. Tang goi (orchestrator/API) chiu trach nhiem thong bao
        "khong tao duoc bieu do nao" cho nguoi dung.
    """
    charts: list[ChartSpec] = []

    for tr in task_results:
        if not tr.execution.success:
            logger.warning(
                "Bo qua ve bieu do cho task loi: type=%r, error=%s",
                tr.task.type, tr.execution.error,
            )
            continue

        chart = _build_chart(tr.task, tr.execution)
        if chart is not None:
            charts.append(chart)
        else:
            logger.warning("_build_chart tra None cho task: type=%r", tr.task.type)

    return charts
