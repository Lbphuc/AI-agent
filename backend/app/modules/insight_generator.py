"""Module O5 — Insight Generator.

Nhan cau hoi goc + so lieu DA TINH SAN (TaskResult, tu O3b), viet
nhan xet (insight) bang ngon ngu tu nhien tieng Viet, tra loi truc
tiep cau hoi nguoi dung.

BAT BUOC goi API LLM — day thuan la bai toan sinh ngon ngu tu nhien
(NLG), khong the viet bang luat co dinh.

NGUYEN TAC QUAN TRONG (giam hallucination so lieu): chi dua SO LIEU
DA TINH (ket qua tu TaskResult) vao prompt, KHONG dua DataFrame tho
— LLM chi duoc dien giai so lieu co san, khong duoc tu suy luan hoac
tinh toan so moi.

Tu danh gia chat luong (confidence_score): su dung ky thuat doi chieu
so (numeric accuracy) — tat dinh, khong goi LLM, gia nhu mien phi.
Chi la heuristic tham khao (muc 2 trong ke hoach Tuan 6), khong phai
cong chan cung. Script do chat luong offline o Tuan 6 (SEVQ) la tang
thu hai day du hon.

Tuan 6: thay stub bang cai dat that.
"""
from __future__ import annotations

import logging
import re

from ..llm_client import LLMClient
from ..schemas import InsightResult, TaskResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Loi tuy chinh
# ---------------------------------------------------------------------------

class InsightGenerationError(Exception):
    """Raise khi KHONG CON task nao thanh cong de viet nhan xet.

    Khac voi 1 phan that bai (chi log warning, van xu ly phan con lai).
    Chi raise khi tat ca task deu loi — khi do khong co du lieu de viet gi.
    """


# ---------------------------------------------------------------------------
# Helper: format 1 TaskResult thanh van ban de doc cho LLM
# ---------------------------------------------------------------------------

def _format_task_result(tr: TaskResult) -> str:
    """Dinh dang ket qua 1 task thanh doan van ban cho LLM doc.

    Chi dua so da tinh vao — khong co gi tu DataFrame tho.
    """
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


# ---------------------------------------------------------------------------
# Helper: xay prompt
# ---------------------------------------------------------------------------

def _build_prompt(question: str, task_results: list[TaskResult]) -> str:
    """Xay prompt gui LLM — chi chua so lieu da tinh, khong chua DataFrame."""
    data_blocks = "\n\n".join(_format_task_result(tr) for tr in task_results)
    return (
        "Ban la mot chuyen gia phan tich du lieu kinh doanh. Duoi day la\n"
        "cau hoi cua nguoi dung va so lieu DA DUOC TINH SAN chinh xac bang\n"
        "cong cu thong ke (khong phai do ban tinh) -- CHI duoc dung dung cac\n"
        "con so nay, TUYET DOI KHONG bia them so lieu moi hoac tu suy dien\n"
        "con so khac.\n\n"
        f"Cau hoi: \"{question}\"\n\n"
        f"So lieu da tinh:\n{data_blocks}\n\n"
        "Viet mot doan nhan xet ngan gon (2-4 cau), bang tieng Viet tu nhien,\n"
        "tra loi truc tiep cau hoi tren. Neu co nhieu phan so lieu, hay ket\n"
        "hop chung mot cach mach lac. Chi tra ve doan van, khong them tieu de\n"
        "hay markdown."
    )


# ---------------------------------------------------------------------------
# Helper: doi chieu so lieu — heuristic tat dinh, khong goi LLM
# ---------------------------------------------------------------------------

_NUMBER_PATTERN = re.compile(r"-?\d+(?:[.,]\d+)?")


def _extract_numbers(text: str) -> list[float]:
    """Trich so tu text, ho tro ca dau '.' va ',' lam phan thap phan."""
    numbers: list[float] = []
    for raw in _NUMBER_PATTERN.findall(text):
        try:
            numbers.append(float(raw.replace(",", ".")))
        except ValueError:
            continue
    return numbers


def _collect_known_values(task_results: list[TaskResult]) -> set[float]:
    """Tap hop toan bo gia tri so that trong ket qua tinh toan.

    Day la 'nguon su that' de doi chieu voi so LLM viet trong insight.
    Chi lay gia tri trong dict du lieu (task.type key), bo qua cac
    field phu (target, ...) de tranh dem trung.
    """
    known: set[float] = set()
    for tr in task_results:
        for key, value in tr.execution.results.items():
            if isinstance(value, dict):
                for v in value.values():
                    if isinstance(v, (int, float)):
                        known.add(float(v))
            elif isinstance(value, (int, float)):
                known.add(float(value))
    return known


def _numeric_accuracy_score(
    insight_text: str,
    task_results: list[TaskResult],
    tolerance: float = 0.5,
) -> float:
    """Tinh ti le so trong insight khop voi so lieu that (heuristic).

    Doi chieu theo gia tri tuyet doi: LLM thuong viet "giam 35.56%" ma
    khong co dau tru, trong khi du lieu that la -35.56. Viec dung abs()
    phan anh dung y dinh: LLM co nhac den con so dung, chi khac ve ky hieu.

    Ghi chu gioi han (quan trong de bao cao):
    - "Tang gap doi" (khong co so) khong bi doi chieu.
    - So "12" (thang) co the trung hop voi gia tri nao do.
    - Nen coi day la TIN HIEU THAM KHAO re tien, khong phai cong chan cung.

    Returns:
        float trong [0.0, 1.0]: 1.0 neu khong co gi de doi chieu (edge case).
    """
    known = _collect_known_values(task_results)
    mentioned = _extract_numbers(insight_text)
    if not known or not mentioned:
        return 1.0  # khong co gi de doi chieu -> khong co gi de sai
    # So sanh abs() de xu ly "giam 35.56" (am trong data, duong trong text)
    known_abs = {abs(k) for k in known}
    matched = sum(
        1 for m in mentioned if any(abs(abs(m) - ka) <= tolerance for ka in known_abs)
    )
    return round(matched / len(mentioned), 2)



# ---------------------------------------------------------------------------
# Ham chinh — API cong khai cua module O5
# ---------------------------------------------------------------------------

def generate_insight(
    question: str,
    task_results: list[TaskResult],
    llm: LLMClient,
) -> InsightResult:
    """Sinh nhan xet ngon ngu tu nhien tu so lieu da tinh.

    Chi xu ly cac task thanh cong (execution.success=True). 1 task loi
    khong chan insight cua cac task con lai — giong nguyen tac da ap dung
    o O4 (Chart Generator, Tuan 5).

    Args:
        question: cau hoi goc cua nguoi dung (nguyen van).
        task_results: ket qua tung task tu orchestrator.
        llm: LLMClient thuc (GeminiClient/ClaudeClient) hoac gia lap (test).

    Returns:
        InsightResult voi insight_text va confidence_score heuristic.

    Raises:
        InsightGenerationError: neu KHONG CO task nao thanh cong.
    """
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

    prompt = _build_prompt(question, successful)
    insight_text = llm.complete_text(prompt)

    confidence = _numeric_accuracy_score(insight_text, successful)
    logger.info("Insight confidence_score=%.2f", confidence)

    return InsightResult(insight_text=insight_text, confidence_score=confidence)
