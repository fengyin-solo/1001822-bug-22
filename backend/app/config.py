"""运行配置：端口、跨域、运行环境。"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

_BASE_DIR = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    app_name: str = "城市地下管网巡检养护平台"
    env: str = "local"
    port: int = 8000
    allowed_origins: list[str] = field(
        default_factory=lambda: [
            "http://127.0.0.1:5173",
            "http://localhost:5173",
        ]
    )
    page_size_default: int = 20
    page_size_max: int = 200
    # 数据落盘文件：保存结果写到这里，重启进程后仍读得到最新值。
    # 可用环境变量 FLOW_DATA_FILE 覆盖（其实是全模块共用的仓库文件）。
    data_file: Path = field(
        default_factory=lambda: Path(os.environ.get("APP_DATA_FILE", _BASE_DIR / "data" / "store.json"))
    )


settings = Settings()
