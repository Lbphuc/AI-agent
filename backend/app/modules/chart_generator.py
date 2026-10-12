"""Module O4 — Chart Generator.

Chuyen ket qua tinh toan (ExecutionResult, tu O3b) thanh ChartSpec de
frontend render bang Plotly/Recharts/Chart.js.

KHONG goi LLM — tai buoc nay, loai phan tich (trend/comparison/...) da
duoc O2 xac dinh ro va so lieu da duoc O3 tinh san, nen chi can mot anh
xa tat dinh (deterministic mapping).

Tuan 5: thay stub bang cai dat that (2 loai bieu do: line, bar).
Tuan 8 (Tier 1): Mo rong len 5 loai bieu do + co che chart_hint.
  - chart_hint tu O2 la goi y NGU NGHIA (LLM biet truoc khi co du lieu that).
  - Cac luat tat dinh trong _pick_chart_type la quyet dinh DUA TREN DU LIEU THAT
    (chi biet sau khi O3 chay xong) — triet ly nhat quan voi time_scope o O2.
"""
from __future__ import annotations

import logging

from ..schemas import AnalysisTask, ChartSpec, ChartType, ExecutionResult, TaskResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Bang mac dinh va nguong an toan
# ---------------------------------------------------------------------------
_DEFAULT_CHART: dict[str, ChartType] = {
    "trend": "line",
    "comparison": "bar",
    "growth_rate": "bar",
}

_MAX_PIE_SLICES = 6       # vuot nguong nay, pie kho doc -> fallback bar
_MIN_POINTS_FOR_LINE = 5  # duoi nguong nay, line/area trong yeu -> doi sang bar
_LONG_LABEL_THRESHOLD = 12  # ky tu -> vuot nguong, bar doc thay bar dung


# ---------------------------------------------------------------------------
# Tieu de bieu do — template tat dinh, KHONG can LLM
# ---------------------------------------------------------------------------


def _pick_chart_type(task: AnalysisTask, x: list[str]) -> ChartType:
    """Ket hop goi y ngu nghia tu LLM (chart_hint) voi cac luat tat dinh.

    Thu tu uu tien:
    1. chart_hint tu O2 (LLM dua ra truoc khi co du lieu) la diem bat dau.
    2. Luat an toan tuyet doi (growth_rate + pie -> bo qua pie).
    3. Luat an toan pie qua nhieu lat -> fallback bar.
    4. Luat dem diem thoi gian: qua it diem, line/area trong yeu -> bar.
    5. Luat do do dai nhan: nhan dai -> bar_horizontal.

    Args:
        task: AnalysisTask co the co chart_hint.
        x: danh sach nhan truc X da biet (tu O3 chay xong).

    Returns:
        ChartType da duoc quyet dinh cuoi cung.
    """
    chart_type: ChartType = task.chart_hint or _DEFAULT_CHART[task.type]  # type: ignore[assignment]

    # Luat an toan 1 (tuyet doi): growth_rate co the am — pie vo nghia
    if task.type == "growth_rate" and chart_type == "pie":
        logger.warning("Bo qua goi y 'pie' cho growth_rate (co the co gia tri am)")
        chart_type = "bar"

    # Luat an toan 2: pie qua nhieu lat se kho doc
    if chart_type == "pie" and len(x) > _MAX_PIE_SLICES:
        logger.info(
            "Bo qua goi y 'pie' (%d muc > %d gioi han), dung bar",
            len(x), _MAX_PIE_SLICES,
        )
        chart_type = "bar"

    # Luat tat dinh 3: qua it diem thoi gian, line/area trong yeu
    if task.type == "trend" and chart_type in ("line", "area") and len(x) < _MIN_POINTS_FOR_LINE:
        chart_type = "bar"

    # Luat tat dinh 4: nhan danh muc dai -> bar ngang de de doc
    if chart_type == "bar" and any(len(label) > _LONG_LABEL_THRESHOLD for label in x):
        chart_type = "bar_horizontal"

    return chart_type


from .business_terms import resolve_column_display


def _build_title(task: AnalysisTask) -> str:
    """Sinh tiêu đề biểu đồ từ task.type và tên cột đã Việt hóa (A6)."""
    metric_disp, _ = resolve_column_display(task.metric)
    group_disp, _ = resolve_column_display(task.group_by) if task.group_by else ("", None)

    if task.type == "trend":
        return f"Xu hướng {metric_disp} theo thời gian"
    if task.type == "comparison":
        return f"So sánh {metric_disp} theo {group_disp}"
    if task.type == "growth_rate":
        verb = "giảm" if task.find == "min" else "tăng"
        prefix = f"{group_disp} " if group_disp else ""
        return f"{prefix}{verb} mạnh nhất — {metric_disp}"
    return metric_disp


# ---------------------------------------------------------------------------
# Ham xay ChartSpec tu 1 TaskResult
# ---------------------------------------------------------------------------
def _build_chart(task: AnalysisTask, execution: ExecutionResult) -> ChartSpec | None:
    """Xay ChartSpec tu 1 (task, execution) da thanh cong.

    Tra None thay vi raise neu thieu du lieu — voi AnalysisGoal nhieu
    task, 1 task loi khong nen lam hong bieu do cua cac task khac.
    """
    data_key = task.type
    data = execution.results.get(data_key)

    if not isinstance(data, dict) or not data:
        logger.warning(
            "ExecutionResult thieu key '%s' hoac rong. Nhan duoc: %s",
            data_key, list(execution.results.keys()),
        )
        return None

    x = [str(k) for k in data.keys()]
    chart_type = _pick_chart_type(task, x)

    highlight_x: str | None = None
    if task.type == "growth_rate":
        highlight_x = execution.results.get("target")
        if highlight_x is not None and not isinstance(highlight_x, str):
            highlight_x = str(highlight_x)

    series_vals: list[float] = []
    for v in data.values():
        try:
            val_float = float(v)
            series_vals.append(0.0 if (val_float != val_float) else val_float)
        except (ValueError, TypeError):
            series_vals.append(0.0)

    metric_disp, unit = resolve_column_display(task.metric)

    return ChartSpec(
        chart_type=chart_type,
        title=_build_title(task),
        x=x,
        series={task.metric: series_vals},
        highlight_x=highlight_x,
        display_name=metric_disp,
        unit=unit,
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
