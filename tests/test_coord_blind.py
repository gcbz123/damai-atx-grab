"""坐标盲点点击模块单元测试

注意：部分测试需要连接 Android 真机。
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from src.coord_blind import CoordBlindClicker


@pytest.fixture
def mock_device():
    """创建模拟的 u2.Device"""
    d = MagicMock()

    # 模拟元素
    mock_el = MagicMock()
    mock_el.center = (500, 1000)
    mock_el.rect = {"x": 400, "y": 950, "width": 200, "height": 100}

    # 模拟 xpath
    mock_xpath = MagicMock()
    mock_xpath.get.return_value = mock_el
    d.xpath.return_value = mock_xpath

    return d


class TestCoordBlindClicker:
    """测试坐标盲点点击器"""

    def test_init(self, mock_device):
        clicker = CoordBlindClicker(mock_device)
        assert clicker.coord_cache == {}
        assert clicker.xpath_cache == {}
        assert clicker.max_fallbacks == 3

    def test_record_coord(self, mock_device):
        clicker = CoordBlindClicker(mock_device)
        result = clicker.record_coord("buy_btn", '//*[@text="立即购票"]')

        assert result is True
        assert "buy_btn" in clicker.coord_cache
        assert clicker.coord_cache["buy_btn"] == (500, 1000)
        assert clicker.xpath_cache["buy_btn"] == '//*[@text="立即购票"]'

    def test_record_coord_not_found(self, mock_device):
        """元素不存在时返回 False"""
        clicker = CoordBlindClicker(mock_device)
        mock_device.xpath.return_value.get.return_value = None

        result = clicker.record_coord("buy_btn", '//*[@text="假的"]')
        assert result is False
        assert "buy_btn" not in clicker.coord_cache

    def test_blind_click_cached(self, mock_device):
        clicker = CoordBlindClicker(mock_device)
        clicker.coord_cache["buy_btn"] = (500, 1000)

        result = clicker.blind_click("buy_btn")
        assert result is True
        mock_device.click.assert_called_once_with(500, 1000)

    def test_blind_click_not_cached(self, mock_device):
        """未缓存的按钮应触发降级"""
        clicker = CoordBlindClicker(mock_device)

        result = clicker.blind_click("unknown_btn")
        assert result is False

    def test_blind_click_fallback_on_failures(self, mock_device):
        """连续失败超过阈值应触发降级"""
        clicker = CoordBlindClicker(mock_device)
        clicker.coord_cache["buy_btn"] = (500, 1000)
        clicker.xpath_cache["buy_btn"] = '//*[@text="立即购票"]'

        # 让盲点点击抛出异常
        mock_device.click.side_effect = Exception("Click failed")

        # 第一次
        result1 = clicker.blind_click("buy_btn")
        assert result1 is False  # 尝试降级
        assert clicker._consecutive_failures["buy_btn"] == 1

        # 恢复点击（模拟第三次时 XPath 成功）
        mock_device.click.side_effect = None
        mock_device.xpath.return_value.get.return_value = None  # XPath 也失败

        # 第二次（依然盲点失败，但没到阈值）
        mock_device.click.side_effect = Exception("Click failed")
        result2 = clicker.blind_click("buy_btn")
        assert clicker._consecutive_failures["buy_btn"] == 2

        # 第三次（达到阈值，降级到 XPath）
        result3 = clicker.blind_click("buy_btn")
        assert clicker._consecutive_failures["buy_btn"] == 3

    def test_has_coord(self, mock_device):
        clicker = CoordBlindClicker(mock_device)
        assert clicker.has_coord("buy_btn") is False
        clicker.coord_cache["buy_btn"] = (500, 1000)
        assert clicker.has_coord("buy_btn") is True

    def test_get_coord(self, mock_device):
        clicker = CoordBlindClicker(mock_device)
        clicker.coord_cache["buy_btn"] = (500, 1000)
        assert clicker.get_coord("buy_btn") == (500, 1000)
        assert clicker.get_coord("unknown") is None

    def test_clear_cache(self, mock_device):
        clicker = CoordBlindClicker(mock_device)
        clicker.coord_cache["buy_btn"] = (500, 1000)
        clicker.xpath_cache["buy_btn"] = '//*[@text="立即购票"]'
        clicker._consecutive_failures["buy_btn"] = 2

        clicker.clear_cache()

        assert clicker.coord_cache == {}
        assert clicker.xpath_cache == {}
        assert clicker._consecutive_failures == {}

    def test_fallback_click_success(self, mock_device):
        """降级点击成功应重新校准坐标"""
        clicker = CoordBlindClicker(mock_device)
        clicker.xpath_cache["buy_btn"] = '//*[@text="立即购票"]'

        result = clicker.fallback_click("buy_btn")
        assert result is True
        assert clicker.coord_cache["buy_btn"] == (500, 1000)

    def test_fallback_click_no_xpath(self, mock_device):
        """无 XPath 记录时应返回 False"""
        clicker = CoordBlindClicker(mock_device)
        result = clicker.fallback_click("unknown")
        assert result is False
