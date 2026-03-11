"""
Phase 258 — Multi-Language Support Foundation (i18n)
=====================================================

Language pack loader and template resolver for multi-language support.

Supported languages: en, th, ja, zh, es, ko, he
"""
from __future__ import annotations

import re
from typing import Literal

SUPPORTED_LANGUAGES = {"en", "th", "ja", "zh", "es", "ko", "he"}

Language = Literal["en", "th", "ja", "zh", "es", "ko", "he"]

# ---------------------------------------------------------------------------
# Language Pack Data
# ---------------------------------------------------------------------------

_PACKS: dict[str, dict[str, str]] = {
    "en": {
        # Error messages
        "error.not_found":           "Resource not found.",
        "error.unauthorized":        "Authentication required.",
        "error.forbidden":           "You do not have permission to perform this action.",
        "error.validation":          "Invalid request data.",
        "error.conflict":            "A conflicting resource already exists.",
        "error.internal":            "An internal error occurred. Please try again.",
        "error.rate_limited":        "Too many requests. Please wait and try again.",
        # Notification templates (variable: {task_id}, {property}, {urgency}, {channel})
        "notify.task_assigned":      "Task {task_id} assigned at {property}. Urgency: {urgency}.",
        "notify.task_escalated":     "ESCALATION: Task {task_id} at {property} requires immediate attention.",
        "notify.sla_breach":         "SLA breach: Task {task_id} at {property} — acknowledgement overdue.",
        "notify.booking_created":    "New booking confirmed at {property}. Ref: {booking_ref}.",
        "notify.booking_cancelled":  "Booking {booking_ref} at {property} has been cancelled.",
        # Generic
        "label.property":            "Property",
        "label.booking":             "Booking",
        "label.task":                "Task",
        "label.urgency":             "Urgency",
    },
    "th": {
        "error.not_found":           "ไม่พบทรัพยากร",
        "error.unauthorized":        "ต้องมีการยืนยันตัวตน",
        "error.forbidden":           "คุณไม่มีสิทธิ์ดำเนินการนี้",
        "error.validation":          "ข้อมูลคำขอไม่ถูกต้อง",
        "error.conflict":            "มีทรัพยากรที่ขัดแย้งอยู่แล้ว",
        "error.internal":            "เกิดข้อผิดพลาดภายใน กรุณาลองอีกครั้ง",
        "error.rate_limited":        "คำขอมากเกินไป กรุณารอสักครู่",
        "notify.task_assigned":      "งาน {task_id} ถูกมอบหมายที่ {property} ความเร่งด่วน: {urgency}",
        "notify.task_escalated":     "การยกระดับ: งาน {task_id} ที่ {property} ต้องการความสนใจทันที",
        "notify.sla_breach":         "ละเมิด SLA: งาน {task_id} ที่ {property} — การยืนยันเกินกำหนด",
        "notify.booking_created":    "การจองใหม่ได้รับการยืนยันที่ {property} อ้างอิง: {booking_ref}",
        "notify.booking_cancelled":  "การจอง {booking_ref} ที่ {property} ถูกยกเลิกแล้ว",
        "label.property":            "ทรัพย์สิน",
        "label.booking":             "การจอง",
        "label.task":                "งาน",
        "label.urgency":             "ความเร่งด่วน",
    },
    "ja": {
        "error.not_found":           "リソースが見つかりません。",
        "error.unauthorized":        "認証が必要です。",
        "error.forbidden":           "この操作を実行する権限がありません。",
        "error.validation":          "リクエストデータが無効です。",
        "error.conflict":            "競合するリソースがすでに存在します。",
        "error.internal":            "内部エラーが発生しました。もう一度お試しください。",
        "error.rate_limited":        "リクエストが多すぎます。しばらくお待ちください。",
        "notify.task_assigned":      "タスク {task_id} が {property} に割り当てられました。緊急度: {urgency}",
        "notify.task_escalated":     "エスカレーション: {property} のタスク {task_id} は即時対応が必要です。",
        "notify.sla_breach":         "SLA 違反: {property} のタスク {task_id} — 確認が遅延しています。",
        "notify.booking_created":    "{property} で新しい予約が確認されました。参照: {booking_ref}",
        "notify.booking_cancelled":  "{property} の予約 {booking_ref} がキャンセルされました。",
        "label.property":            "物件",
        "label.booking":             "予約",
        "label.task":                "タスク",
        "label.urgency":             "緊急度",
    },
    "zh": {
        "error.not_found":           "资源未找到。",
        "error.unauthorized":        "需要身份验证。",
        "error.forbidden":           "您无权执行此操作。",
        "error.validation":          "请求数据无效。",
        "error.conflict":            "存在冲突的资源。",
        "error.internal":            "内部错误，请重试。",
        "error.rate_limited":        "请求过多，请稍后再试。",
        "notify.task_assigned":      "任务 {task_id} 已分配到 {property}。紧急程度：{urgency}",
        "notify.task_escalated":     "升级通知：{property} 的任务 {task_id} 需要立即处理。",
        "notify.sla_breach":         "SLA 违规：{property} 的任务 {task_id} — 确认已逾期。",
        "notify.booking_created":    "{property} 的新预订已确认。参考：{booking_ref}",
        "notify.booking_cancelled":  "{property} 的预订 {booking_ref} 已取消。",
        "label.property":            "物业",
        "label.booking":             "预订",
        "label.task":                "任务",
        "label.urgency":             "紧急程度",
    },
    "es": {
        "error.not_found":           "Recurso no encontrado.",
        "error.unauthorized":        "Se requiere autenticación.",
        "error.forbidden":           "No tienes permiso para realizar esta acción.",
        "error.validation":          "Datos de solicitud inválidos.",
        "error.conflict":            "Ya existe un recurso en conflicto.",
        "error.internal":            "Ocurrió un error interno. Por favor, inténtalo de nuevo.",
        "error.rate_limited":        "Demasiadas solicitudes. Por favor, espera e inténtalo de nuevo.",
        "notify.task_assigned":      "Tarea {task_id} asignada en {property}. Urgencia: {urgency}.",
        "notify.task_escalated":     "ESCALACIÓN: La tarea {task_id} en {property} requiere atención inmediata.",
        "notify.sla_breach":         "Incumplimiento de SLA: Tarea {task_id} en {property} — reconocimiento pendiente.",
        "notify.booking_created":    "Nueva reserva confirmada en {property}. Ref: {booking_ref}.",
        "notify.booking_cancelled":  "La reserva {booking_ref} en {property} ha sido cancelada.",
        "label.property":            "Propiedad",
        "label.booking":             "Reserva",
        "label.task":                "Tarea",
        "label.urgency":             "Urgencia",
    },
    "ko": {
        "error.not_found":           "리소스를 찾을 수 없습니다.",
        "error.unauthorized":        "인증이 필요합니다.",
        "error.forbidden":           "이 작업을 수행할 권한이 없습니다.",
        "error.validation":          "잘못된 요청 데이터입니다.",
        "error.conflict":            "충돌하는 리소스가 이미 존재합니다.",
        "error.internal":            "내부 오류가 발생했습니다. 다시 시도해 주세요.",
        "error.rate_limited":        "요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.",
        "notify.task_assigned":      "태스크 {task_id}가 {property}에 할당되었습니다. 긴급도: {urgency}",
        "notify.task_escalated":     "에스컬레이션: {property}의 태스크 {task_id}는 즉각적인 주의가 필요합니다.",
        "notify.sla_breach":         "SLA 위반: {property}의 태스크 {task_id} — 확인이 지연되었습니다.",
        "notify.booking_created":    "{property}에서 새 예약이 확인되었습니다. 참조: {booking_ref}",
        "notify.booking_cancelled":  "{property}의 예약 {booking_ref}이 취소되었습니다.",
        "label.property":            "속성",
        "label.booking":             "예약",
        "label.task":                "태스크",
        "label.urgency":             "긴급도",
    },
    "he": {
        "error.not_found":           "המשאב לא נמצא.",
        "error.unauthorized":        "נדרשת אימות.",
        "error.forbidden":           "אין לך הרשאה לבצע פעולה זו.",
        "error.validation":          "נתוני בקשה לא תקינים.",
        "error.conflict":            "משאב מתנגש כבר קיים.",
        "error.internal":            "אירעה שגיאה פנימית. אנא נסה שוב.",
        "error.rate_limited":        "יותר מדי בקשות. אנא המתן ונסה שוב.",
        "notify.task_assigned":      "משימה {task_id} הוקצתה ב-{property}. דחיפות: {urgency}",
        "notify.task_escalated":     "הסלמה: משימה {task_id} ב-{property} דורשת תשומת לב מיידית.",
        "notify.sla_breach":         "הפרת SLA: משימה {task_id} ב-{property} — האישור מאחר.",
        "notify.booking_created":    "הזמנה חדשה אושרה ב-{property}. אסמכתא: {booking_ref}",
        "notify.booking_cancelled":  "הזמנה {booking_ref} ב-{property} בוטלה.",
        "label.property":            "נכס",
        "label.booking":             "הזמנה",
        "label.task":                "משימה",
        "label.urgency":             "דחיפות",
    },
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_text(key: str, lang: str = "en", **variables: str) -> str:
    """
    Resolve a translation key to a string in the requested language.

    Falls back to English if:
    - The language is unsupported
    - The key is missing in the requested language pack

    Variable substitution: use {var_name} syntax in templates.

    Example:
        get_text("notify.task_assigned", lang="th", task_id="T-99",
                 property="Villa Sunset", urgency="CRITICAL")
    """
    pack = _PACKS.get(lang, _PACKS["en"])
    template = pack.get(key) or _PACKS["en"].get(key) or key

    if variables:
        try:
            return template.format(**variables)
        except (KeyError, ValueError):
            return template  # Return unformatted if vars don't match

    return template


def get_supported_languages() -> list[str]:
    """Return sorted list of supported language codes."""
    return sorted(SUPPORTED_LANGUAGES)


def is_supported(lang: str) -> bool:
    """Return True if language code is supported."""
    return lang in SUPPORTED_LANGUAGES


_VAR_PATTERN = re.compile(r"\{(\w+)\}")


def get_template_variables(key: str, lang: str = "en") -> list[str]:
    """
    Return the variable names required by a template key.

    Example:
        get_template_variables("notify.task_assigned")
        → ["task_id", "property", "urgency"]
    """
    pack = _PACKS.get(lang, _PACKS["en"])
    template = pack.get(key) or _PACKS["en"].get(key) or ""
    return _VAR_PATTERN.findall(template)
