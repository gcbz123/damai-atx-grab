"""三段式安全模式控制模块

控制抢票流程的三种模式：
  1. probe_only=true  → 仅探测环境，停在「立即购票」前
  2. probe_only=false, if_commit_order=false → 走到确认页，停在「立即提交」前
  3. probe_only=false, if_commit_order=true  → 正式提交订单
"""

from dataclasses import dataclass
from loguru import logger


@dataclass
class SafetyMode:
    """安全模式状态

    Attributes:
        probe_only: 仅探测模式，不点购票
        if_commit_order: 是否提交订单
    """
    probe_only: bool
    if_commit_order: bool

    @property
    def mode_name(self) -> str:
        """返回当前模式名称"""
        if self.probe_only:
            return "🔍 探测模式"
        if not self.if_commit_order:
            return "🧪 演练模式（不提交）"
        return "🚀 实战模式"

    @property
    def description(self) -> str:
        """返回模式详细描述"""
        if self.probe_only:
            return "仅探测元素 + 校验环境，不操作购票按钮"
        if not self.if_commit_order:
            return "走到确认页，停在『立即提交』前，不下单"
        return "全程自动抢票到付款页，提示用户手动支付"

    def can_click_buy(self) -> bool:
        """是否允许点击购票按钮"""
        return not self.probe_only

    def can_submit_order(self) -> bool:
        """是否允许提交订单"""
        return not self.probe_only and self.if_commit_order


class SafetyGuard:
    """三段式安全守卫"""

    def __init__(self, probe_only: bool, if_commit_order: bool):
        self.mode = SafetyMode(probe_only=probe_only, if_commit_order=if_commit_order)
        logger.info(f"安全模式: {self.mode.mode_name} - {self.mode.description}")

    def assert_can_buy(self):
        """检查是否可以执行购票操作"""
        if not self.mode.can_click_buy():
            logger.warning("探测模式下跳过购票按钮点击")

    def assert_can_submit(self):
        """检查是否可以提交订单"""
        if not self.mode.can_submit_order():
            logger.info("演练模式：停在确认页，不提交订单")
