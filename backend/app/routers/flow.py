"""流量监测接口：维护流量记录，覆盖登记、修改、启动采集、标记异常、停止监测等动作。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.flow import FlowService

router = APIRouter(prefix="/api/flow", tags=["流量监测"])

service = FlowService()

LIST_FIELDS = ["监测编号", "监测断面", "监测时段", "平均流量", "峰值流量", "累计流量", "采集人员", "监测状态"]
STATUSES = ["待采集", "采集正常", "流量异常", "已停测"]


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按监测编号检索"),
    section: str | None = Query(default=None, description="按监测断面检索"),
    period: str | None = Query(default=None, description="按监测时段检索"),
    status: str | None = Query(default=None, description="待采集、采集正常、流量异常、已停测"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按监测编号、监测断面、监测时段与状态过滤流量监测列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(
        keyword=keyword, section=section, period=period, status=status, page=page, size=size
    )
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/stats")
def flow_stats() -> dict[str, Any]:
    """列表卡片指标：与运营概览共用同一口径，条数始终一致。"""
    return service.stats()


@router.get("/export")
def export_entries(
    keyword: str | None = None,
    section: str | None = None,
    period: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    """导出流量监测清单：返回当前过滤条件下的全量数据。"""
    items, total = service.list_entries(
        keyword=keyword, section=section, period=period, status=status, page=1, size=10000
    )
    return {"module": "flow", "total": total, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条流量记录明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"流量记录 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条流量记录，缺字段或落盘失败时说明原因；同一监测编号重复提交只算一次。"""
    entry, message, _created = service.create_entry(payload.values)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.put("/{entry_id}", response_model=ActionResult)
def update_entry(entry_id: int, payload: EntryPayload) -> ActionResult:
    """修改一条流量记录；校验或落盘不成功时原值保留，并把原因讲清楚。"""
    entry, message = service.update_entry(entry_id, payload.values)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条流量记录执行启动采集、标记异常、停止监测；不允许的动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message, _changed = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
