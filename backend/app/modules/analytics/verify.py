"""Module analytics/verify.py.

Bo kiem chung tat dinh cho de xuat chien luoc (Citation-grounded Verification).
Kiem tra:
1. JSON hop le, co caveat, <= 3 khuyen nghi.
2. fact_ids ton tai 100% trong FactSheet, it nhat 1 ID.
3. So trong action/rationale phai khop voi gia tri cua cac fact da duoc trich dan.
4. It nhat 1 ten thuc the cua fact da trich xuat hien trong loi van.
5. Trich fact estimate=True thi bat buoc co tu 'uoc tinh / du kien'.
6. Chan cac tu khang dinh nhan qua tuyet doi ('chac chan do', 'nguyen nhan duy nhat').
"""
from __future__ import annotations

import logging
import re
import unicodedata
from typing import Optional, Union
from ...schemas import Fact, Recommendation

logger = logging.getLogger(__name__)

FORBIDDEN_CAUSAL_PHRASES = [
    "chắc chắn do",
    "nguyên nhân duy nhất",
    "hoàn toàn do",
    "chắc chắn là do",
    "khẳng định do",
]

ESTIMATE_KEYWORDS = ["ước tính", "dự kiến", "dự báo", "khoảng", "khoảng tin cậy", "dự tính", "ước đạt"]


def _strip_accents(s: str) -> str:
    """Xoa dau tieng Viet de so khop khong phan biet hoa thuong va dau."""
    return "".join(
        c for c in unicodedata.normalize("NFD", s.lower())
        if unicodedata.category(c) != "Mn"
    )


def _extract_numbers(text: str) -> list[float]:
    """Trich xuat moi con so tu van ban tieng Viet/tieng Anh.

    Ho tro cac dang:
    - 1.419 hoac 1419
    - 1.250,5 hoac 1250.5
    - 6,7% hoac 6.7%
    - -279 hoac −279
    """
    normalized = text.replace("−", "-")
    tokens = re.findall(r"[-+]?\d+(?:[.,]\d+)?%?", normalized)
    results = []
    for tok in tokens:
        clean = tok.rstrip("%")
        # Xu ly dinh dang Viet Nam 1.419,5 -> 1419.5
        if "." in clean and "," in clean:
            clean = clean.replace(".", "").replace(",", ".")
        elif "," in clean:
            clean = clean.replace(",", ".")
        elif "." in clean:
            # 1.419 -> neu la 3 chu so sau dau cham thi co the la dau phan cach hang nghin
            parts = clean.split(".")
            if len(parts) == 2 and len(parts[1]) == 3 and int(parts[0]) > 0:
                clean = parts[0] + parts[1]
        try:
            val = float(clean)
            results.append(val)
        except ValueError:
            continue
    return results


def _numbers_match(n1: float, n2: float, tol_pct: float = 0.05) -> bool:
    """Kiem tra hai con so co khop nhau khong voi dung sai lam tron."""
    abs_diff = abs(n1 - n2)
    if abs_diff < 0.5:
        return True
    if abs(n2) > 1e-4:
        pct_err = abs_diff / abs(n2)
        if pct_err <= tol_pct:
            return True
    return False


def verify_recommendation(
    rec: Recommendation,
    facts_map: Union[dict[str, Fact], list[Fact]],
) -> tuple[bool, Optional[str]]:
    """Kiem chung tat dinh 1 Recommendation.

    Tra ve (is_valid, rejection_reason).
    """
    if isinstance(facts_map, list):
        facts_map = {f.id: f for f in facts_map}

    # 1. Kiem tra caveat
    if not rec.caveat or len(rec.caveat.strip()) < 5:
        return False, "Thiếu trường 'caveat' bắt buộc (điều kiện cần kiểm chứng bên ngoài)."

    # 2. Kiem tra fact_ids
    if not rec.fact_ids:
        return False, "Khuyến nghị không trích dẫn bất kỳ fact_id nào."

    cited_facts: list[Fact] = []
    for fid in rec.fact_ids:
        if fid not in facts_map:
            return False, f"fact_id '{fid}' không tồn tại trong danh sách sự thật."
        cited_facts.append(facts_map[fid])

    combined_text = f"{rec.title} {rec.action} {rec.rationale}"
    combined_norm = _strip_accents(combined_text)

    # 3. Kiem tra tu khang dinh nhan qua tuyet doi
    for phrase in FORBIDDEN_CAUSAL_PHRASES:
        if phrase in combined_text.lower():
            return False, f"Khuyến nghị dùng từ khẳng định nguyên nhân tuyệt đối '{phrase}', vi phạm quy tắc thận trọng."

    # 4. Kiem tra fact estimate=True
    has_estimate = any(f.estimate for f in cited_facts)
    if has_estimate:
        has_est_keyword = any(kw in combined_norm for kw in [_strip_accents(k) for k in ESTIMATE_KEYWORDS])
        if not has_est_keyword:
            return False, "Khuyến nghị trích dẫn số liệu dự báo nhưng không ghi rõ 'ước tính' hoặc 'dự kiến'."

    # 5. Kiem tra ten thuc the
    entity_found = False
    for f in cited_facts:
        if not f.entity:
            entity_found = True
            break
        ent_norm = _strip_accents(str(f.entity))
        # Kiem tra ca ten day du hoac tung tu quan trong
        if ent_norm in combined_norm:
            entity_found = True
            break
        for part in ent_norm.split():
            if len(part) >= 3 and part in combined_norm:
                entity_found = True
                break
        if entity_found:
            break

    if not entity_found:
        return False, "Khuyến nghị không nhắc tới tên thực thể/đối tượng trong các fact đã trích dẫn."

    # 6. Kiem tra con so trong loi van
    extracted_nums = _extract_numbers(combined_text)
    allowed_values: list[float] = []
    for f in cited_facts:
        allowed_values.append(f.value)
        allowed_values.append(abs(f.value))
        # Doc them cac so xuat hien trong fact.text
        allowed_values.extend(_extract_numbers(f.text))

    for num in extracted_nums:
        # Bo qua cac so qua nho nhu so 1, 2, 3 (co the la buoc 1, thang 2...)
        if abs(num) <= 3.0:
            continue
        # Kiem tra xem num co khop voi so nao trong allowed_values khong
        matched = any(_numbers_match(num, allowed_v) for allowed_v in allowed_values)
        if not matched:
            return False, f"Con số '{num}' trong khuyến nghị không khớp với bất kỳ số nào trong các fact được trích dẫn."

    return True, None


def verify_all_recommendations(
    recommendations: list[Recommendation],
    facts: list[Fact],
) -> tuple[list[Recommendation], list[str]]:
    """Kiem chung toan bo danh sach khuyen nghi, loai cac khuyen nghi vi pham."""
    facts_map = {f.id: f for f in facts}
    valid_recs: list[Recommendation] = []
    rejection_reasons: list[str] = []

    for r in recommendations[:3]:  # Toi da 3 khuyen nghi
        ok, reason = verify_recommendation(r, facts_map)
        if ok:
            valid_recs.append(r)
        else:
            rejection_reasons.append(f"Loại '{r.title}': {reason}")

    return valid_recs, rejection_reasons
