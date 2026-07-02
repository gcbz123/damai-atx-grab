"""配置加载与校验模块

支持 JSONC 格式（含 // 注释的 JSON），提供类型安全的配置访问。
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from loguru import logger


@dataclass
class AppConfig:
    """应用配置数据类"""
    # 设备
    udid: str = ""
    app_package: str = "cn.damai"
    app_activity: str = ".launcher.splash.SplashMainActivity"

    # 演出
    item_url: str = ""
    keyword: Optional[str] = None
    users: list[str] = field(default_factory=list)
    city: str = "深圳"
    date: str = ""
    price: str = ""
    price_index: int = 0
    perform_index: int = 0  # 场次索引，0=不指定（默认第1场）

    # 安全模式
    if_commit_order: bool = False
    probe_only: bool = True
    auto_navigate: bool = True

    # 定时
    start_at: str = ""
    warmup_sec: int = 120
    ntp_server: str = "ntp.aliyun.com"

    # 冲刺参数
    sprint_interval_ms: int = 50
    sprint_max_retries: int = 60

    # 日志
    log_level: str = "DEBUG"
    log_dir: str = "logs"


def _strip_jsonc_comments(text: str) -> str:
    """去除 JSONC 中的 // 和 /* */ 注释"""
    # 去除多行注释 /* ... */
    text = re.sub(r'/\*[\s\S]*?\*/', '', text)
    # 去除单行注释 // ...（不在字符串内）
    result = []
    i = 0
    in_string = False
    string_char = None
    while i < len(text):
        ch = text[i]
        if in_string:
            result.append(ch)
            if ch == '\\':
                i += 1
                if i < len(text):
                    result.append(text[i])
            elif ch == string_char:
                in_string = False
        else:
            if ch in '"\'':
                in_string = True
                string_char = ch
                result.append(ch)
            elif ch == '/' and i + 1 < len(text) and text[i + 1] == '/':
                # 跳到行尾
                i += 2
                while i < len(text) and text[i] not in '\n\r':
                    i += 1
                continue
            else:
                result.append(ch)
        i += 1
    return ''.join(result)


def load_config(config_path: str) -> AppConfig:
    """加载并校验配置文件

    Args:
        config_path: 配置文件路径（支持 JSONC 格式）

    Returns:
        AppConfig 实例

    Raises:
        FileNotFoundError: 配置文件不存在
        ValueError: 配置校验失败
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")

    raw = path.read_text(encoding="utf-8")
    clean = _strip_jsonc_comments(raw)

    try:
        data = json.loads(clean)
    except json.JSONDecodeError as e:
        raise ValueError(f"配置文件 JSON 解析失败: {e}")

    config = AppConfig(**{k: v for k, v in data.items() if k in AppConfig.__dataclass_fields__})

    _validate(config)
    logger.info(f"配置加载完成: {path.resolve()}")
    return config


def _validate(config: AppConfig):
    """校验配置字段合法性"""
    errors = []

    if not config.start_at:
        errors.append("start_at 不能为空，请设置开售时间")
    if not config.users:
        errors.append("users 不能为空，请至少添加一个观演人")
    if not config.city:
        errors.append("city 不能为空")
    if not config.date:
        errors.append("date 不能为空")
    if config.warmup_sec < 10:
        logger.warning(f"warmup_sec={config.warmup_sec} 过小，建议 ≥ 30 秒")
    if config.sprint_interval_ms < 10:
        logger.warning(f"sprint_interval_ms={config.sprint_interval_ms} 过小，可能触发风控")
    if config.sprint_max_retries < 1:
        errors.append("sprint_max_retries 必须 ≥ 1")

    if errors:
        raise ValueError("配置校验失败:\n" + "\n".join(f"  - {e}" for e in errors))

    logger.info("配置校验通过")
