"""各业务模块的状态口径：状态序列、异常状态、终态与中文展示名统一收在这里。

列表与运营概览共用同一份口径：待处理 = 非终态记录，异常 = 处于异常状态的记录，
避免一边按标志位、一边按状态值统计导致的条数对不上。
"""
from __future__ import annotations

# 模块英文标识 -> 导航/概览里使用的中文名称
MODULE_LABELS: dict[str, str] = {
    "pipe": "管段档案",
    "manhole": "检查井",
    "valve": "阀门井室",
    "pumpstation": "泵站设施",
    "patrol": "巡查任务",
    "defect": "缺陷登记",
    "cctv": "内窥检测",
    "repair": "修复施工",
    "pressure": "压力监测",
    "flow": "流量监测",
    "leak": "泄漏排查",
    "dredge": "清淤疏浚",
    "material": "养护材料",
    "equip": "养护机械",
    "traffic": "占道许可",
    "complaint": "公众诉求",
    "fund": "养护资金",
    "archive": "管网档案",
}

# 每个模块的全部业务状态（与各 service 的 STATUS_ORDER 保持一致）
STATUS_ORDER: dict[str, list[str]] = {
    "pipe": ["待移交", "正常运行", "重点观测", "封闭施工"],
    "manhole": ["待清掏", "正常使用", "井盖缺失", "已废弃"],
    "valve": ["待启闭", "操作正常", "启闭卡涩", "已停用"],
    "pumpstation": ["待接管", "运行正常", "减量运行", "停运检修"],
    "patrol": ["待派发", "巡查中", "已提交", "已作废"],
    "defect": ["待定级", "已定级", "处置中", "已闭环"],
    "cctv": ["待检测", "检测中", "已出具", "已退回"],
    "repair": ["待开工", "施工中", "待验收", "已完工"],
    "pressure": ["待采集", "采集正常", "压力越限", "已停测"],
    "flow": ["待采集", "采集正常", "流量异常", "已停测"],
    "leak": ["待排查", "排查中", "已处置", "已排除"],
    "dredge": ["待安排", "清淤中", "已完成", "已取消"],
    "material": ["正常可用", "临近不足", "已冻结", "已耗尽"],
    "equip": ["待保养", "可用", "保养中", "已报废"],
    "traffic": ["待审批", "已批准", "施工中", "已恢复"],
    "complaint": ["待受理", "办理中", "已回复", "已关闭"],
    "fund": ["待审批", "已批复", "执行中", "已超支"],
    "archive": ["待归档", "已归档", "待补充", "已作废"],
}

# 算作“异常量”的状态（按业务语义，而不是动作名）
ABNORMAL_STATUSES: dict[str, set[str]] = {
    "pipe": set(),
    "manhole": {"井盖缺失"},
    "valve": {"启闭卡涩"},
    "pumpstation": {"减量运行"},
    "patrol": set(),
    "defect": set(),
    "cctv": set(),
    "repair": set(),
    "pressure": {"压力越限"},
    "flow": {"流量异常"},
    "leak": set(),
    "dredge": set(),
    "material": {"临近不足"},
    "equip": set(),
    "traffic": set(),
    "complaint": set(),
    "fund": {"已超支"},
    "archive": {"待补充"},
}

def terminal_status(module: str) -> str | None:
    """每个模块状态序列的最后一个状态视为终态（已停测、已完工等）。"""
    order = STATUS_ORDER.get(module)
    return order[-1] if order else None


def is_pending(module: str, status: str | None) -> bool:
    """待处理：处于非终态的记录。"""
    return status is not None and status != terminal_status(module)


def is_abnormal(module: str, status: str | None) -> bool:
    """异常：处于该模块异常状态集合内的记录。"""
    return status in ABNORMAL_STATUSES.get(module, set())
