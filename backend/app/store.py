"""数据仓库：启动时从磁盘载入，每次写操作后落盘，重启进程数据也不丢。

真实项目里这里会换成数据库访问层；当前实现只依赖标准库，保证克隆下来就能起。
列表与概览共用 app.policies 里的同一份状态口径，待处理/异常条数始终一致。
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from app.config import settings
from app.policies import MODULE_LABELS, is_abnormal, is_pending
from app.seed import SEED_ROWS

# 各模块列表里展示状态的中文列名；保存/动作后同步该列，避免列表与明细状态对不上。
STATUS_FIELD = {
    "pipe": "管段状态",
    "manhole": "检查井状态",
    "valve": "阀门状态",
    "pumpstation": "泵站状态",
    "patrol": "巡查状态",
    "defect": "缺陷状态",
    "cctv": "检测状态",
    "repair": "修复状态",
    "pressure": "监测状态",
    "flow": "监测状态",
    "leak": "排查状态",
    "dredge": "清淤状态",
    "material": "材料状态",
    "equip": "机械状态",
    "traffic": "许可状态",
    "complaint": "诉求状态",
    "fund": "资金状态",
    "archive": "档案状态",
}


class Store:
    def __init__(self, data_file: str | Path | None = None) -> None:
        self._data_file = Path(data_file) if data_file else settings.data_file
        self._lock = threading.RLock()
        self._tables: dict[str, list[dict[str, Any]]] = {}
        self._load()

    # ---------- 载入与落盘 ----------

    def _load(self) -> None:
        with self._lock:
            if self._data_file.exists():
                try:
                    data = json.loads(self._data_file.read_text(encoding="utf-8"))
                    if isinstance(data, dict):
                        self._tables = {
                            name: [dict(row) for row in rows]
                            for name, rows in data.items()
                            if isinstance(rows, list)
                        }
                except (json.JSONDecodeError, OSError):
                    # 落盘文件损坏时退回种子数据，避免服务直接起不来
                    self._tables = self._seed_tables()
            else:
                self._tables = self._seed_tables()
            # 种子数据里 pending/abnormal 标志位与状态语义有出入，统一按口径重算
            for module, rows in self._tables.items():
                for row in rows:
                    self._sync_row(module, row)
            self._save_locked()
    def _seed_tables(self) -> dict[str, list[dict[str, Any]]]:
        return {name: [dict(row) for row in rows] for name, rows in SEED_ROWS.items()}

    def _save_locked(self) -> None:
        self._data_file.parent.mkdir(parents=True, exist_ok=True)
        tmp_file = self._data_file.with_suffix(".tmp")
        tmp_file.write_text(
            json.dumps(self._tables, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp_file.replace(self._data_file)

    def save(self) -> None:
        """写操作完成后调用：把最新结果落盘，失败时向上抛出由接口层说明原因。"""
        with self._lock:
            self._save_locked()

    # ---------- 读取 ----------

    def module_names(self) -> list[str]:
        # 按导航里的业务顺序返回，概览表顺序与左侧菜单一致
        with self._lock:
            return [name for name in MODULE_LABELS if name in self._tables]

    def rows(self, module: str) -> list[dict[str, Any]]:
        with self._lock:
            return self._tables.setdefault(module, [])

    def find(self, module: str, entry_id: int) -> dict[str, Any] | None:
        with self._lock:
            for row in self.rows(module):
                if int(row.get("id", 0)) == entry_id:
                    return row
            return None

    # ---------- 口径同步 ----------

    def _sync_row(self, module: str, row: dict[str, Any]) -> None:
        """按统一口径刷新派生字段：标志位与中文状态列都从 status 推导。"""
        status = row.get("status")
        row["pending"] = is_pending(module, status)
        row["abnormal"] = is_abnormal(module, status)
        status_field = STATUS_FIELD.get(module)
        if status_field and status is not None:
            row[status_field] = status

    def sync_row(self, module: str, row: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self._sync_row(module, row)
            return row

    # ---------- 概览 ----------

    def overview(self) -> dict[str, object]:
        with self._lock:
            modules: list[dict[str, object]] = []
            for name in self.module_names():
                rows = self.rows(name)
                pending = sum(1 for row in rows if is_pending(name, row.get("status")))
                abnormal = sum(1 for row in rows if is_abnormal(name, row.get("status")))
                modules.append({
                    "name": name,
                    "label": MODULE_LABELS.get(name, name),
                    "created": len(rows),
                    "pending": pending,
                    "abnormal": abnormal,
                })
            cards = [
                {"label": "业务模块", "value": len(modules)},
                {"label": "今日新增", "value": sum(int(item["created"]) for item in modules)},
                {"label": "待处理", "value": sum(int(item["pending"]) for item in modules)},
                {"label": "异常量", "value": sum(int(item["abnormal"]) for item in modules)},
            ]
            return {"cards": cards, "modules": modules}


store = Store()
