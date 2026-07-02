"""冲刺引擎单元测试"""

import time
from unittest.mock import MagicMock, PropertyMock

import pytest

from src.sprint import SprintEngine


@pytest.fixture
def mock_device():
    d = MagicMock()
    # 模拟 info 属性
    type(d).info = PropertyMock(
        return_value={"currentActivity": "cn.damai.activity.DetailActivity"}
    )
    return d


@pytest.fixture
def mock_clicker():
    clicker = MagicMock()
    clicker.blind_click.return_value = True
    clicker.coord_cache = {"buy_btn": (500, 1000)}
    return clicker


class TestSprintEngine:
    """测试冲刺引擎"""

    def test_init(self, mock_device, mock_clicker):
        engine = SprintEngine(mock_device, mock_clicker)
        assert engine.d == mock_device
        assert engine.clicker == mock_clicker
        assert engine._click_count == 0
        assert engine._page_changed is False

    def test_check_page_changed_detected(self, mock_device, mock_clicker):
        """Activity 包含 detail 时 expected_not_contains='detail' 应返回 False"""
        engine = SprintEngine(mock_device, mock_clicker)

        # DetailActivity 包含 'detail'，所以 expected_not_contains='detail' → False
        changed = engine._check_page_changed(expected_not_contains='detail')
        assert changed is False

        # 当 Activity 变化后应返回 True
        type(mock_device).info = PropertyMock(
            return_value={"currentActivity": "cn.damai.activity.TicketActivity"}
        )
        changed = engine._check_page_changed(expected_not_contains='detail')
        assert changed is True

    def test_check_page_changed_not_detected(self, mock_device, mock_clicker):
        """Activity 未变化应返回 False"""
        # 设置 info 返回不包含 'order' 的 activity
        type(mock_device).info = PropertyMock(
            return_value={"currentActivity": "cn.damai.activity.DetailActivity"}
        )
        engine = SprintEngine(mock_device, mock_clicker)

        changed = engine._check_page_changed(expected_contains='order')
        assert changed is False

    def test_check_page_changed_contains(self, mock_device, mock_clicker):
        """Activity 包含目标字符串应返回 True"""
        type(mock_device).info = PropertyMock(
            return_value={"currentActivity": "cn.damai.activity.OrderActivity"}
        )
        engine = SprintEngine(mock_device, mock_clicker)

        changed = engine._check_page_changed(expected_contains='order')
        assert changed is True

    def test_check_page_changed_exception(self, mock_device, mock_clicker):
        """异常时应返回 False"""
        type(mock_device).info = PropertyMock(side_effect=Exception("info error"))
        engine = SprintEngine(mock_device, mock_clicker)

        changed = engine._check_page_changed()
        assert changed is False

    def test_wait_interval_short(self, mock_device, mock_clicker):
        """短间隔使用 CPU 自旋"""
        engine = SprintEngine(mock_device, mock_clicker)
        start = time.perf_counter()
        engine._wait_interval(10)
        elapsed = (time.perf_counter() - start) * 1000
        assert elapsed >= 8  # 至少等了 8ms

    def test_wait_interval_long(self, mock_device, mock_clicker):
        """长间隔使用 time.sleep"""
        engine = SprintEngine(mock_device, mock_clicker)
        start = time.perf_counter()
        engine._wait_interval(100)
        elapsed = (time.perf_counter() - start) * 1000
        assert elapsed >= 80

    def test_stats_before_sprint(self, mock_device, mock_clicker):
        """开始前的统计"""
        engine = SprintEngine(mock_device, mock_clicker)
        stats = engine.stats
        assert stats["click_count"] == 0
        assert stats["elapsed_ms"] == 0
        assert stats["page_changed"] is False

    def test_confirm_sprint_detected(self, mock_device, mock_clicker):
        """确认页冲刺检测到跳转"""
        type(mock_device).info = PropertyMock(
            return_value={"currentActivity": "cn.damai.activity.OrderActivity"}
        )
        engine = SprintEngine(mock_device, mock_clicker)

        # 设置 blind_click 成功
        mock_clicker.blind_click.return_value = True

        result = engine.sprint_confirm(interval_ms=0, max_retries=3)
        assert result is True
        assert engine._click_count > 0
        assert engine._page_changed is True

    def test_submit_sprint_detected(self, mock_device, mock_clicker):
        """提交页冲刺检测到跳转"""
        type(mock_device).info = PropertyMock(
            return_value={"currentActivity": "cn.damai.activity.PayActivity"}
        )
        engine = SprintEngine(mock_device, mock_clicker)

        result = engine.sprint_submit(interval_ms=0, max_retries=3)
        assert result is True

    def test_sprint_buy_detected(self, mock_device, mock_clicker):
        """购票冲刺检测到页面变化"""
        type(mock_device).info = PropertyMock(
            # 第一次返回 DetailActivity，之后返回其他
            side_effect=[
                {"currentActivity": "cn.damai.activity.DetailActivity"},
                {"currentActivity": "cn.damai.activity.TicketActivity"},
            ]
        )
        engine = SprintEngine(mock_device, mock_clicker)

        result = engine.sprint_buy(
            target_time_ms=int(time.time() * 1000),
            interval_ms=0,
            max_retries=5,
        )
        assert result is True
