"""管网档案接口：维护档案记录，覆盖提交归档、确认归档、作废档案等动作。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.archive import ArchiveService

router = APIRouter(prefix="/api/archive", tags=["管网档案"])

service = ArchiveService()

LIST_FIELDS = ["档案编号", "关联管段", "档案类别", "资料名称", "存放位置", "归档人员", "归档日期", "档案状态"]
STATUSES = ["待归档", "已归档", "待补充", "已作废"]


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按档案编号检索"),
    status: str | None = Query(default=None, description="待归档、已归档、待补充、已作废"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按档案编号与状态过滤管网档案列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(keyword=keyword, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出管网档案清单：返回当前过滤条件下的全量数据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "archive", "total": total, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条档案记录明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"档案记录 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条档案记录，缺字段时说明原因而不是静默丢弃。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        detail = missing[0] if len(missing) == 1 and missing[0].startswith(("保存失败", "操作未生效")) else f"缺少必填字段：{'、'.join(missing)}"
        return ActionResult(ok=False, message=detail)
    return ActionResult(ok=True, message="档案记录已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条档案记录执行提交归档、确认归档、作废档案；不允许的动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)

