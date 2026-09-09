"""Module O3b — Sandbox Executor.

Thực thi mã do O3a (Code Generator) sinh ra, trong một môi trường CÔ
LẬP (sandbox): không truy cập mạng, không truy cập file hệ thống ngoài
DataFrame được truyền vào. Có cơ chế bắt lỗi và cho phép gọi lại O3a
để tự sinh mã mới nếu thực thi thất bại, tối đa `max_attempts` lần
(tương tự cơ chế lọc lỗi nhiều tầng của VISGENERATOR trong LIDA).

ĐÂY LÀ LOGIC KỸ THUẬT THUẦN TÚY — KHÔNG gọi LLM. Tuyệt đối không giao
việc thực thi mã cho LLM tự làm.

Cài đặt dự kiến ở Tuần 4 — xem docs/SRS.md (FR-06, NFR-02 bảo mật).
"""
from __future__ import annotations

import pandas as pd

from ..schemas import ExecutionResult


def execute(code: str, df: pd.DataFrame, max_attempts: int = 3) -> ExecutionResult:
    """Thực thi mã phân tích trong sandbox.

    Raises:
        NotImplementedError: chưa cài đặt (dự kiến Tuần 4).

    Ghi chú thiết kế (để triển khai sau):
        - Chạy trong subprocess riêng, giới hạn quyền (không import os/
          sys/socket...), hoặc container Docker cô lập.
        - Giới hạn thời gian thực thi (timeout) để tránh vòng lặp vô hạn.
        - Nếu lỗi, trả lỗi về cho O3a để sinh lại, đếm số lần thử
          (attempts) và dừng khi vượt max_attempts.
    """
    raise NotImplementedError(
        "Sandbox Executor se duoc cai dat o Tuan 4 - can thiet ke co "
        "che co lap va gioi han quyen thuc thi (xem docs/SRS.md FR-06)."
    )
