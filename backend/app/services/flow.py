"""流量监测业务规则：状态流转、字段校验、统计口径都收在这里。

列表、概览、详情页共用同一套状态语义（status 为唯一口径），
pending / abnormal 以及在测、今日累计等指标都从 status 实时推导，
避免列表和概览各算各的导致条数对不上。
"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.store import store

MODULE = "flow"
EDITABLE_FIELDS = ["监测编号", "监测断面", "监测时段", "平均流量", "峰值流量", "累计流量", "采集人员"]
REQUIRED_FIELDS = ["监测编号", "监测断面", "监测时段"]
NUMERIC_FIELDS = ["平均流量", "峰值流量", "累计流量"]
STATUS_ORDER = ["待采集", "采集正常", "流量异常", "已停测"]
ACTION_RULES = {"启动采集": "采集正常", "标记异常": "流量异常", "停止监测": "已停测"}
# 异常状态：概览的异常量、列表的统计卡都只认这一口径
ABNORMAL_STATUS = "流量异常"
# 仍在监测（未停测）的状态，用于“在测断面”
STOPPED_STATUS = "已停测"
# 需要跟进的待处理状态，用于概览“待处理”
PENDING_STATUSES = ["待采集", "流量异常"]
STATUS_FIELD = "监测状态"


def is_pending(status: Any) -> bool:
    return status in PENDING_STATUSES


def is_abnormal_status(status: Any) -> bool:
    return status == ABNORMAL_STATUS


def is_monitoring(status: Any) -> bool:
    return status in STATUS_ORDER and status != STOPPED_STATUS


def _to_float(value: Any) -> float | None:
    """把累计流量等数值字段转成数字；空值返回 None，脏数据不当作 0 混进统计。"""
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _display(row: dict[str, Any]) -> dict[str, Any]:
    """统一出口：列表、详情、概览都按同一份口径输出。

    监测状态始终以内部 status 为准，避免历史数据里的占位字段盖过真实状态。
    """
    item = {key: value for key, value in row.items() if key not in ("pending", "abnormal")}
    item[STATUS_FIELD] = row.get("status")
    return item


class FlowService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        section: str | None = None,
        period: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("监测编号", ""))]
        if section:
            rows = [row for row in rows if section in str(row.get("监测断面", ""))]
        if period:
            rows = [row for row in rows if period in str(row.get("监测时段", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return [_display(row) for row in rows[start:start + size]], total

    def stats(self) -> dict[str, int]:
        """列表页统计卡与运营概览共用的口径：全部按 status 实时推导。"""
        rows = store.rows(MODULE)
        today = date.today().isoformat()
        return {
            "monitoring": sum(1 for row in rows if is_monitoring(row.get("status"))),
            "abnormal": sum(1 for row in rows if is_abnormal_status(row.get("status"))),
            "today_total": int(
                sum(
                    amount
                    for row in rows
                    if str(row.get("监测时段", "")) == today
                    for amount in [_to_float(row.get("累计流量"))]
                    if amount is not None
                )
            ),
            "total": len(rows),
            "pending": sum(1 for row in rows if is_pending(row.get("status"))),
        }

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        row = store.find(MODULE, entry_id)
        return _display(row) if row is not None else None

    def _validate(self, values: dict[str, Any], *, require_all: bool) -> list[str]:
        """必填校验 + 数值非负校验；不通过时给出可读原因。

        require_all=True（登记）时三个必填字段缺一不可；
        修改时只校验本次真正提交上来的字段，未提交字段沿用原值。
        """
        problems: list[str] = []
        for field in REQUIRED_FIELDS:
            if (require_all or field in values) and not str(values.get(field) or "").strip():
                problems.append(f"缺少必填字段：{field}")
        for field in NUMERIC_FIELDS:
            if field not in values:
                continue
            raw = values[field]
            if raw is None or str(raw).strip() == "":
                continue
            amount = _to_float(raw)
            if amount is None:
                problems.append(f"{field}必须是数字")
            elif amount < 0:
                problems.append(f"{field}不能为负数")
        return problems

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        """登记一条流量记录。

        同一监测编号已存在时不重复入库，直接返回原记录（重复提交只算一次）。
        """
        problems = self._validate(values, require_all=True)
        if problems:
            return None, "；".join(problems)
        rows = store.rows(MODULE)
        code = str(values.get("监测编号")).strip()
        existing = next((row for row in rows if str(row.get("监测编号")) == code), None)
        if existing is not None:
            return _display(existing), f"监测编号 {code} 已存在，未重复登记"
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        for field in EDITABLE_FIELDS:
            entry[field] = str(values.get(field, "")).strip() if values.get(field) is not None else ""
        entry["status"] = STATUS_ORDER[0]
        rows.append(entry)
        return _display(entry), "流量记录已登记"

    def update_entry(
        self, entry_id: int, values: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str, bool]:
        """修改一条流量记录。

        返回 (记录, 说明, 是否真的改动)。校验失败时一条字段都不会落库，
        前端据此保留原值并提示原因；内容与现状一致视为重复提交，不再写一遍。
        """
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"流量记录 {entry_id} 不存在或已归档", False
        provided = {key: value for key, value in values.items() if key in EDITABLE_FIELDS}
        problems = self._validate(provided, require_all=False)
        if problems:
            return None, "；".join(problems), False
        candidate = {field: entry.get(field, "") for field in EDITABLE_FIELDS}
        candidate.update(provided)
        code = str(candidate["监测编号"]).strip()
        clash = next(
            (
                row
                for row in store.rows(MODULE)
                if int(row.get("id", 0)) != entry_id and str(row.get("监测编号")) == code
            ),
            None,
        )
        if clash is not None:
            return None, f"监测编号 {code} 已被记录 {clash.get('id')} 占用，未保存", False
        normalized = {field: str(candidate[field] or "").strip() for field in EDITABLE_FIELDS}
        if all(str(entry.get(field, "")) == normalized[field] for field in EDITABLE_FIELDS):
            return _display(entry), "内容没有变化，未重复保存", False
        entry.update(normalized)
        return _display(entry), "流量记录已保存", True

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"流量记录 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于流量监测可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        if entry.get("status") == target:
            # 重复点击同一个动作只算一次，不重复流转
            return _display(entry), f"流量记录已是「{target}」，无需重复执行"
        entry["status"] = target
        return _display(entry), f"流量记录已{action}，当前状态：{target}"
