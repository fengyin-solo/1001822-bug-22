"""流量监测业务规则：状态流转、字段校验、筛选口径与落盘都收在这里。"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.policies import is_abnormal, is_pending
from app.store import store

MODULE = "flow"
REQUIRED_FIELDS = ["监测编号", "监测断面", "监测时段"]
EDITABLE_FIELDS = ["监测编号", "监测断面", "监测时段", "平均流量", "峰值流量", "累计流量", "采集人员"]
STATUS_ORDER = ["待采集", "采集正常", "流量异常", "已停测"]
ACTION_RULES = {"启动采集": "采集正常", "标记异常": "流量异常", "停止监测": "已停测"}


def _to_number(value: Any) -> float | None:
    """能转成数字就转；占位文本、空值返回 None，不参与流量汇总。"""
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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
        rows = list(store.rows(MODULE))
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
        return rows[start:start + size], total

    def stats(self) -> dict[str, int | float]:
        """列表卡片与运营概览共用同一份口径：总数/在测(非终态)/异常三处数完全对得上。"""
        rows = store.rows(MODULE)
        today = date.today().isoformat()
        today_total = 0.0
        for row in rows:
            if str(row.get("监测时段", ""))[:10] == today:
                value = _to_number(row.get("累计流量"))
                if value is not None:
                    today_total += value
        return {
            "total": len(rows),
            "monitoring": sum(1 for row in rows if is_pending(MODULE, row.get("status"))),
            "abnormal": sum(1 for row in rows if is_abnormal(MODULE, row.get("status"))),
            "today_total": round(today_total, 2),
        }

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def _find_by_code(self, code: str, exclude_id: int | None = None) -> dict[str, Any] | None:
        for row in store.rows(MODULE):
            if str(row.get("监测编号", "")).strip() == code and row.get("id") != exclude_id:
                return row
        return None

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str, bool]:
        """登记流量记录。

        返回 (记录, 说明, 是否新建)：监测编号重复时幂等返回已有记录，不新增、不报错，
        保证重复提交只算一次。
        """
        code = str(values.get("监测编号") or "").strip()
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, f"缺少必填字段：{'、'.join(missing)}", False
        existing = self._find_by_code(code)
        if existing is not None:
            return existing, f"监测编号 {code} 已存在，本次重复提交未重复登记", False
        rows = store.rows(MODULE)
        entry: dict[str, Any] = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        for field in EDITABLE_FIELDS:
            entry[field] = str(values.get(field) or "").strip() if values.get(field) is not None else None
        entry["status"] = STATUS_ORDER[0]
        store.sync_row(MODULE, entry)
        rows.append(entry)
        try:
            store.save()
        except OSError as exc:
            rows.remove(entry)
            return None, f"保存失败，数据未能落盘：{exc}，请稍后重试", False
        return entry, "流量记录已登记", True

    def update_entry(self, entry_id: int, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        """修改流量记录。校验先于落库：任何一步不成功都保留原值并说明原因。"""
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"流量记录 {entry_id} 不存在或已归档"
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, f"缺少必填字段：{'、'.join(missing)}"
        code = str(values.get("监测编号") or "").strip()
        duplicate = self._find_by_code(code, exclude_id=entry_id)
        if duplicate is not None:
            return None, f"监测编号 {code} 已被其他记录占用，未保存"

        snapshot = dict(entry)
        for field in EDITABLE_FIELDS:
            entry[field] = str(values.get(field) or "").strip() if values.get(field) is not None else None
        store.sync_row(MODULE, entry)
        try:
            store.save()
        except OSError as exc:
            # 落盘失败：恢复原值，保证“保存不成功时保留原值”
            entry.clear()
            entry.update(snapshot)
            return None, f"保存失败，数据未能落盘：{exc}，原值已保留，请稍后重试"
        return entry, "流量记录修改已保存"

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str, bool]:
        """执行状态动作。重复提交相同动作时幂等返回当前状态，不产生额外变更。"""
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"流量记录 {entry_id} 不存在或已归档", False
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于流量监测可执行范围", False
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里", False
        current = entry.get("status")
        if current == target:
            return entry, f"流量记录已是「{target}」，无需重复{action}", False
        snapshot = dict(entry)
        entry["status"] = target
        store.sync_row(MODULE, entry)
        try:
            store.save()
        except OSError as exc:
            entry.clear()
            entry.update(snapshot)
            return None, f"操作未生效，数据未能落盘：{exc}，原状态已保留，请稍后重试", False
        return entry, f"流量记录已{action}", True
