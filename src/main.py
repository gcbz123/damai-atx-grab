"""抢票程序主入口

ATX (uiautomator2) 真机方案。

用法:
    # 探测模式（默认）
    python -m src.main

    # 演练模式（不提交）
    python -m src.main --no-probe-only

    # 实战模式（正式提交）
    python -m src.main --commit

    # 指定配置文件
    python -m src.main --config my_config.jsonc
"""

import argparse
import sys
from pathlib import Path

import uiautomator2 as u2
from loguru import logger

from src.config_loader import load_config
from src.logger import LoggerManager
from src.safety_guard import SafetyGuard
from src.phase_machine import Phase, PhaseMachine


def parse_args(argv: list[str]) -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="大麦网抢票 - ATX 真机方案 v2.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s                         探测模式
  %(prog)s --no-probe-only         演练模式（走到确认页）
  %(prog)s --commit                实战模式（正式提交）
  %(prog)s --config my_config.jsonc 指定配置
        """,
    )
    parser.add_argument(
        "--config",
        default="config.jsonc",
        help="配置文件路径（默认: config.jsonc）",
    )
    parser.add_argument(
        "--no-probe-only",
        action="store_true",
        help="关闭探测模式，进入演练/实战模式",
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        help="正式提交订单（覆盖配置文件中的 if_commit_order）",
    )
    parser.add_argument(
        "--udid",
        default="",
        help="adb 设备序列号（留空自动选择第一个）",
    )
    parser.add_argument(
        "--check-env",
        action="store_true",
        help="仅检查环境，不执行抢票流程",
    )
    return parser.parse_args(argv)


def check_environment() -> bool:
    """检查运行环境是否就绪

    Returns:
        True 如果环境就绪
    """
    logger.info("--- 环境检查 ---")
    ok = True

    # 检查 adb 可用
    import subprocess
    try:
        result = subprocess.run(
            ["adb", "version"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            version = result.stdout.strip().split("\n")[0]
            logger.info(f"✅ adb: {version}")
        else:
            logger.error("❌ adb 命令失败")
            ok = False
    except Exception as e:
        logger.error(f"❌ adb 不可用: {e}")
        ok = False

    # 检查设备连接
    try:
        result = subprocess.run(
            ["adb", "devices", "-l"],
            capture_output=True, text=True, timeout=5
        )
        lines = result.stdout.strip().split("\n")
        device_lines = [l for l in lines if "device" in l and "List" not in l]
        if device_lines:
            logger.info(f"✅ 已连接 {len(device_lines)} 台设备")
            for dl in device_lines:
                logger.info(f"   {dl.strip()}")
        else:
            logger.warning("⚠️ 未检测到设备（请连接手机并开启 USB 调试）")
    except Exception as e:
        logger.error(f"❌ adb devices 失败: {e}")
        ok = False

    # 检查 ATX
    try:
        import uiautomator2
        logger.info(f"✅ uiautomator2: OK")
    except ImportError as e:
        logger.error(f"❌ uiautomator2 未安装: {e}")
        ok = False

    return ok


def main(argv: list[str] | None = None) -> int:
    """主入口

    Args:
        argv: 命令行参数（默认使用 sys.argv[1:]）

    Returns:
        退出码（0=成功，1=错误）
    """
    args = parse_args(argv or sys.argv[1:])

    # 初始化日志
    LoggerManager.init(level="DEBUG")

    # 仅检查环境
    if args.check_env:
        ok = check_environment()
        return 0 if ok else 1

    # 加载配置
    try:
        config = load_config(args.config)

        # 命令行参数覆盖配置
        if args.no_probe_only:
            config.probe_only = False
        if args.commit:
            config.probe_only = False
            config.if_commit_order = True
        if args.udid:
            config.udid = args.udid
    except (FileNotFoundError, ValueError) as e:
        logger.error(f"配置加载失败: {e}")
        return 1

    # 安全模式
    safety = SafetyGuard(
        probe_only=config.probe_only,
        if_commit_order=config.if_commit_order,
    )
    logger.info(f"运行模式: {safety.mode.mode_name}")
    logger.info(f"目标演出: city={config.city} date={config.date}")
    logger.info(f"开售时间: {config.start_at}")
    logger.info(f"观演人: {config.users}")

    # 连接设备
    try:
        if config.udid:
            logger.info(f"连接设备: {config.udid}")
            d = u2.connect(config.udid)
        else:
            logger.info("连接设备（自动选择第一个）")
            d = u2.connect()
        device_info = d.info
        logger.info(f"✅ 设备连接成功: {device_info.get('productName', '')}")
        logger.info(f"   屏幕: {d.window_size()}")
        logger.info(f"   系统: {device_info.get('version', '')}")
    except Exception as e:
        logger.error(f"❌ 设备连接失败: {e}")
        logger.error("请确保手机已连接并开启 USB 调试")
        return 1

    # 运行抢票流程
    machine = PhaseMachine(config, d, safety)
    final_phase = machine.run()
    machine.print_summary()

    return 0 if final_phase != Phase.ERROR else 1


if __name__ == "__main__":
    sys.exit(main())
