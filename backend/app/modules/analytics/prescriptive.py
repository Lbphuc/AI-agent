"""Module analytics/prescriptive.py.

Cap 3 — De xuat chien luoc (Prescriptive Analytics).
Ket hop:
1. Dung FactSheet toan dien: Mo ta + Chan doan + Du bao (neu co).
2. Goi LLM sinh khuyen nghi bat buoc trich dan fact_ids.
3. Kiem chung qua verify.py (loai khuyen nghi bia so/khong can cu).
4. Retry toi da 1 lan neu toan bo khuyen nghi bi loai.
5. Tra ve ket qua trung thuc (neu van rong thi bao chua du bang chung).
"""
from __future__ import annotations

import json
import logging
from typing import Optional
import pandas as pd

from ...llm_client import LLMClient
from ...schemas import AnalysisGoal, DataProfile, DeepenResponse, Fact, Recommendation, Section
from .diagnostic import run_diagnostic
from .forecast import run_forecast
from .verify import verify_all_recommendations

logger = logging.getLogger(__name__)


def run_prescriptive(
    df: pd.DataFrame,
    profile: DataProfile,
    goal: AnalysisGoal,
    llm: Optional[LLMClient] = None,
) -> DeepenResponse:
    """Chay phan tich de xuat chien luoc voi bo kiem chung nghiem ngat."""
    warnings: list[str] = []
    all_facts: list[Fact] = []
    evidence_sections: list[Section] = []

    # 1. Chay chan doan lay can cu
    try:
        diag_sec, diag_facts = run_diagnostic(df, profile, goal, llm=None)  # Dien giai tat dinh de tiet kiem LLM
        evidence_sections.append(diag_sec)
        all_facts.extend(diag_facts)
        warnings.extend(diag_sec.warnings)
    except Exception as exc:
        logger.warning("Loi khi tinh chan doan lam can cu: %s", exc)
        warnings.append(f"Không tính được phần chẩn đoán: {exc}")

    # 2. Chay du bao lay can cu (neu co the)
    try:
        fc_sec, fc_facts = run_forecast(df, profile, goal, h=3, llm=None)
        if fc_facts:
            evidence_sections.append(fc_sec)
            all_facts.extend(fc_facts)
            warnings.extend(fc_sec.warnings)
        else:
            warnings.extend(fc_sec.warnings)
    except Exception as exc:
        logger.info("Bo qua phan du bao lam can cu: %s", exc)

    if not all_facts:
        return DeepenResponse(
            level="prescriptive",
            sections=[],
            recommendations=[],
            facts=[],
            warnings=["Không có đủ dữ kiện thực tế để đưa ra đề xuất chiến lược."],
        )

    # 3. Xay dung prompt cho LLM
    recommendations: list[Recommendation] = []
    if llm:
        facts_prompt_list = "\n".join(f"[{f.id}] {f.text}" for f in all_facts)
        prompt = (
            "Bạn là chuyên viên phân tích kinh doanh cấp cao. Dưới đây là DANH SÁCH SỰ THẬT ĐÃ ĐƯỢC TÍNH TOÁN CHÍNH XÁC:\n"
            f"{facts_prompt_list}\n\n"
            "Quy tắc bắt buộc:\n"
            "- Tối đa 3 khuyến nghị hành động, trả về duy nhất JSON object theo định dạng:\n"
            '  {"recommendations": [\n'
            '    {\n'
            '      "title": "Tiêu đề ngắn gọn",\n'
            '      "action": "Hành động cụ thể cần làm",\n'
            '      "rationale": "Lý do và căn cứ từ số liệu",\n'
            '      "fact_ids": ["F1", "F2"],\n'
            '      "priority": "cao" | "trung bình" | "thấp",\n'
            '      "caveat": "Điều kiện cần kiểm chứng (chưa biết chi phí, biên lợi nhuận, đối thủ...)"\n'
            '    }\n'
            '  ]}\n'
            "- Mỗi khuyến nghị PHẢI trích ít nhất một fact_id có trong danh sách trên và nêu đúng tên thực thể.\n"
            "- CHỈ được dùng các con số xuất hiện trong các fact đã trích; TUYỆT ĐỐI KHÔNG tự tạo ra con số mới.\n"
            "- Không khẳng định nguyên nhân chắc chắn; dùng từ ngữ thận trọng: 'cần rà soát/thử nghiệm/tối ưu'.\n"
            "- Nếu trích dẫn số liệu dự báo (có chữ ƯỚC TÍNH), BẮT BUỘC ghi rõ 'ước tính' hoặc 'dự kiến'.\n"
            "- BẮT BUỘC có trường 'caveat' nêu rõ điều cần kiểm chứng thêm.\n"
            "- Nếu không đủ bằng chứng vững chắc, trả về: {\"recommendations\": []}.\n"
            "JSON:"
        )

        # Lan goi 1
        raw_recs = _call_llm_for_recommendations(prompt, llm)
        valid_recs, rej_reasons = verify_all_recommendations(raw_recs, all_facts)

        # Retry toi da 1 lan neu co khuyen nghi bi loai va con 0 khuyen nghi hop le
        if not valid_recs and raw_recs:
            logger.info("Retry 1 lan cho prescriptive vi tat ca khuyen nghi bi loai: %s", rej_reasons)
            retry_prompt = (
                f"{prompt}\n\n"
                "LƯU Ý: Lần sinh trước đã bị bộ kiểm chứng từ chối vì các lỗi sau:\n"
                + "\n".join(f"- {r}" for r in rej_reasons)
                + "\nHãy sửa lại chính xác theo các lỗi trên, đảm bảo chỉ trích số thật từ FactSheet."
            )
            raw_recs_2 = _call_llm_for_recommendations(retry_prompt, llm)
            valid_recs, rej_reasons_2 = verify_all_recommendations(raw_recs_2, all_facts)
            warnings.extend(rej_reasons_2)
        else:
            warnings.extend(rej_reasons)

        recommendations = valid_recs

    if not recommendations:
        warnings.append("Chưa đủ bằng chứng số liệu vững chắc để đưa ra đề xuất chiến lược cụ thể.")

    return DeepenResponse(
        level="prescriptive",
        sections=evidence_sections,
        recommendations=recommendations,
        facts=all_facts,
        warnings=warnings,
    )


def _call_llm_for_recommendations(prompt: str, llm: LLMClient) -> list[Recommendation]:
    """Goi complete_json va parse thanh danh sach Recommendation."""
    try:
        data = llm.complete_json(prompt)
        if isinstance(data, dict) and "recommendations" in data:
            raw_list = data["recommendations"]
        elif isinstance(data, list):
            raw_list = data
        else:
            return []

        recs = []
        for item in raw_list:
            if isinstance(item, dict):
                try:
                    recs.append(
                        Recommendation(
                            title=str(item.get("title", "")),
                            action=str(item.get("action", "")),
                            rationale=str(item.get("rationale", "")),
                            fact_ids=[str(f) for f in item.get("fact_ids", [])],
                            priority=item.get("priority", "trung bình") if item.get("priority") in ("cao", "trung bình", "thấp") else "trung bình",
                            caveat=str(item.get("caveat", "")),
                        )
                    )
                except Exception:
                    continue
        return recs
    except Exception as exc:
        logger.warning("Loi khi goi LLM complete_json cho prescriptive: %s", exc)
        return []
