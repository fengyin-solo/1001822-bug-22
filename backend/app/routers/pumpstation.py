"""泵站设施接口：维护泵站，覆盖办理接管、标记减量、安排检修等动作。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.pumpstation import PumpstationService

router = APIRouter(prefix="/api/pumpstation", tags=["泵站设施"])

service = PumpstationService()

LIST_FIELDS = ["泵站编号", "泵站名称", "服务区域", "装机台数", "设计流量", "上次检修日", "值守方式", "泵站状态"]
STATUSES = ["待接管", "运行正常", "减量运行", "停运检修"]


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按泵站编号检索"),
    status: str | None = Query(default=None, description="待接管、运行正常、减量运行、停运检修"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按泵站编号与状态过滤泵站设施列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(keyword=keyword, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出泵站设施清单：返回当前过滤条件下的全量数据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "pumpstation", "total": total, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条泵站明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"泵站 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条泵站，缺字段时说明原因而不是静默丢弃。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        detail = missing[0] if len(missing) == 1 and missing[0].startswith(("保存失败", "操作未生效")) else f"缺少必填字段：{'、'.join(missing)}"
        return ActionResult(ok=False, message=detail)
    return ActionResult(ok=True, message="泵站已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条泵站执行办理接管、标记减量、安排检修；不允许的动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)

