"""各业务 service 的共用写操作：状态口径同步 + 落盘，失败回滚并保留原值。"""
from __future__ import annotations

from typing import Any

from app.store import store


def commit_status(module: str, entry: dict[str, Any], target: str) -> str | None:
    """把动作产生的目标状态写入记录并落盘。

    成功返回 None；落盘失败时恢复整条记录并返回可读原因。
    """
    snapshot = dict(entry)
    entry["status"] = target
    store.sync_row(module, entry)
    try:
        store.save()
    except OSError as exc:
        entry.clear()
        entry.update(snapshot)
        return f"操作未生效，数据未能落盘：{exc}，原状态已保留，请稍后重试"
    return None


def commit_new(module: str, entry: dict[str, Any], rows: list[dict[str, Any]]) -> str | None:
    """登记新记录并落盘；失败时移除刚追加的记录并返回原因。"""
    store.sync_row(module, entry)
    rows.append(entry)
    try:
        store.save()
    except OSError as exc:
        rows.remove(entry)
        return f"保存失败，数据未能落盘：{exc}，请稍后重试"
    return None
