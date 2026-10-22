"""Module O5 — Insight Generator.

Nhan cau hoi goc + so lieu DA TINH SAN (TaskResult, tu O3b), viet
nhan xet (insight) bang ngon ngu tu nhien tieng Viet, tra loi truc
tiep cau hoi nguoi dung.
"""
from __future__ import annotations

import logging
import re

from ..llm_client import LLMClient
from ..schemas import AnalysisGoal, InsightResult, TaskResult

logger = logging.getLogger(__name__)


class InsightGenerationError(Exception):
    """Raise khi KHONG CON task nao thanh cong de viet nhan xet."""


def _format_task_result(tr: TaskResult) -> str:
    """Dinh dang ket qua 1 task thanh doan van ban cho LLM doc."""
    task, execution = tr.task, tr.execution
    header = f"[{task.type}] {task.metric}"
    if task.group_by:
        header += f" theo {task.group_by}"

    lines = [header]

    data = execution.results.get(task.type, {})
    if isinstance(data, dict):
        for label, value in data.items():
            if isinstance(value, (int, float)):
                lines.append(f"  {label}: {value:.2f}")
            else:
                lines.append(f"  {label}: {value}")

    target = execution.results.get("target")
    if target is not None:
        verb = "thap nhat" if task.find == "min" else "cao nhat"
        lines.append(f"  (Gia tri {verb}: {target})")

    return "\n".join(lines)


def _build_prompt(question: str, task_results: list[TaskResult], goal: AnalysisGoal | None = None) -> str:
    """Xay prompt gui LLM — chi chua so lieu da tinh, khong chua DataFrame."""
    data_blocks = "\n\n".join(_format_task_result(tr) for tr in task_results)

    goal_guidance = ""
    if goal and goal.objective == "contribution_to_change":
        goal_guidance = (
            "\nLƯU Ý CỰC KỲ QUAN TRỌNG VỀ MỤC TIÊU CÂU HỎI:\n"
            "- Câu hỏi hỏi về yếu tố đóng góp vào THAY ĐỔI / BIẾN ĐỘNG doanh số (thuộc phần Chẩn đoán bên dưới).\n"
            "- Các số liệu ở đây chỉ là tổng quy mô doanh số tĩnh để làm bối cảnh tham khảo ban đầu.\n"
            "- TUYỆT ĐỐI KHÔNG nhận định nhóm có quy mô doanh số lớn nhất là 'đóng góp nhiều nhất vào thay đổi'!\n"
            "- Hãy nêu rõ: Đây là tổng quy mô doanh số theo danh mục làm cơ sở nền tảng, còn mức độ đóng góp làm tăng/giảm doanh số cụ thể được phân tích chi tiết trong phần Chẩn đoán bên dưới.\n"
        )
    elif goal and goal.objective in ("top_decliners", "top_growers"):
        goal_guidance = (
            "\nLƯU Ý VỀ MỤC TIÊU CÂU HỎI:\n"
            "- Người dùng đang tìm nhóm tăng trưởng hoặc sụt giảm mạnh nhất. "
            "Hãy trả lời trực tiếp nhóm nào tăng/giảm mạnh nhất kèm đúng con số trong dữ liệu.\n"
        )

    return (
        "Ban la mot chuyen gia phan tich du lieu kinh doanh. Duoi day la\n"
        "cau hoi cua nguoi dung va so lieu DA DUOC TINH SAN chinh xac bang\n"
        "cong cu thong ke (khong phai do ban tinh) -- CHI duoc dung dung cac\n"
        "con so nay, TUYET DOI KHONG bia them so lieu moi hoac tu suy dien\n"
        "con so khac.\n\n"
        f"Cau hoi: \"{question}\"\n\n"
        f"So lieu da tinh:\n{data_blocks}\n\n"
        f"{goal_guidance}"
        "QUY TAC VIET NHAN XET:\n"
        "1. Viet mot doan nhan xet ngan gon (2-4 cau), bang tieng Viet tu nhien.\n"
        "2. Neu cau hoi hoi ve tuong lai / du bao / nguyen nhan / de xuat / dong gop: Hay tap trung tom tat\n"
        "   quy mo tong the va cac moc bien dong chinh (ky cao nhat, ky thap nhat, ky dau, ky cuoi) trong du lieu da tinh tren de lam co so nen tang.\n"
        "   TUYET DOI KHONG tu choi tra loi hoac tuyen bo rang 'he thong khong the du bao'.\n"
        "3. Giu nguyen chinh xac ten nhom/nhan nhu trong so lieu, khong them dau hay doi cach viet so voi du lieu goc.\n"
        "4. CHI trich dan DUNG CON SO CHINH XAC co trong bang so lieu tren, TUYET DOI KHONG tu lam tron hoac viet so uoc luong nhu 'hon 40000', 'tren 80000', 'duoi 100'.\n"
        "5. Chi tra ve doan van thuan tuy, khong them tieu de hay markdown."
    )


_NUMBER_PATTERN = re.compile(r"-?\d+(?:[.,]\d+)*")


def _extract_numbers(text: str) -> list[float]:
    """Trich so tu text, ho tro ca dau '.' va ',' lam phan thap phan hoac ngan phan."""
    numbers: list[float] = []
    for raw in _NUMBER_PATTERN.findall(text):
        try:
            clean = raw
            if "." in clean and "," in clean:
                clean = clean.replace(".", "").replace(",", ".")
            elif "," in clean:
                clean = clean.replace(",", ".")
            numbers.append(float(clean))
        except ValueError:
            continue
    return numbers


def _collect_known_values(task_results: list[TaskResult]) -> set[float]:
    """Tap hop toan bo gia tri so that trong ket qua tinh toan."""
    known: set[float] = set()
    for tr in task_results:
        for key, value in tr.execution.results.items():
            if isinstance(value, dict):
                numeric_vals = []
                for v in value.values():
                    if isinstance(v, (int, float)):
                        fv = float(v)
                        known.add(fv)
                        numeric_vals.append(fv)
                if numeric_vals:
                    known.add(round(sum(numeric_vals), 2))
                    known.add(round(sum(numeric_vals) / len(numeric_vals), 2))
            elif isinstance(value, (int, float)):
                known.add(float(value))
    return known


_IGNORE_TOKEN_PATTERN = re.compile(
    r"(?:\b20\d{2}[-/]\d{1,2}(?:[-/]\d{1,2})?\b|\b\d{1,2}/\d{1,2}/20\d{2}\b|"
    r"(?:năm|tháng|kỳ|quý)\s+20\d{2}(?:[-/]\d{1,2})?\b|"
    r"(?:tháng|quý)\s+\d{1,2}(?:\s*[/\-]\s*20\d{2})?\b|"
    r"\b\d{1,2}\s+(?:tháng|kỳ|quý|năm|nhóm|chi nhánh|danh mục)\b|"
    r"(?:hơn|trên|dưới|khoảng|xấp xỉ|gần|ngưỡng(?:\s+trên|\s+dưới)?|mức\s+hơn|mức\s+trên|mức\s+dưới)\s+[-+]?\d+(?:[.,]\d+)*)",
    re.IGNORECASE,
)


def _numeric_accuracy_score(
    insight_text: str,
    task_results: list[TaskResult],
    tolerance: float = 0.5,
) -> float:
    """Tinh ti le so trong insight khop voi so lieu that (heuristic).
    Bo qua cac con so chi ngay thang / nam / so ky va cac cum uoc luong tron ('hon 40000', 'tren 80000')
    de tranh canh bao gia khi cac con so chinh xac da khop 100%.
    """
    known = _collect_known_values(task_results)
    cleaned_text = _IGNORE_TOKEN_PATTERN.sub(" ", insight_text)
    mentioned = _extract_numbers(cleaned_text)
    if not known or not mentioned:
        return 1.0
    known_abs = {abs(k) for k in known}
    matched = sum(
        1
        for m in mentioned
        if any(
            abs(abs(m) - ka) <= max(tolerance, ka * 0.01)
            for ka in known_abs
        )
    )
    return round(matched / len(mentioned), 2)


def generate_insight(
    question: str,
    task_results: list[TaskResult],
    llm: LLMClient,
    goal: AnalysisGoal | None = None,
) -> InsightResult:
    """Sinh nhan xet ngon ngu tu nhien tu so lieu da tinh."""
    successful = [tr for tr in task_results if tr.execution.success]

    if not successful:
        raise InsightGenerationError(
            "Khong co ket qua tinh toan thanh cong nao de viet nhan xet."
        )

    if len(successful) < len(task_results):
        logger.warning(
            "%d/%d task that bai — chi viet insight tu %d task con lai.",
            len(task_results) - len(successful),
            len(task_results),
            len(successful),
        )

    prompt = _build_prompt(question, successful, goal)
    insight_text = llm.complete_text(prompt).replace("**", "")

    confidence = _numeric_accuracy_score(insight_text, successful)
    logger.info("Insight confidence_score=%.2f", confidence)

    return InsightResult(insight_text=insight_text, confidence_score=confidence)