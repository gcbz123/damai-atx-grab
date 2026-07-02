"""定时模块单元测试"""

import time
import pytest

from src.time_sync import TimeSync


class TestTimeSync:
    """测试时间同步模块"""

    def test_init(self):
        ts = TimeSync(ntp_server="ntp.aliyun.com")
        assert ts.ntp_server == "ntp.aliyun.com"
        assert ts.offset_ms == 0.0
        assert ts._synced is False

    def test_local_now_ms(self):
        """本地时间戳应返回毫秒级整数"""
        ts = TimeSync()
        now = ts.local_now_ms()
        assert isinstance(now, int)
        # 与 time.time 差值不超过 10ms
        assert abs(now - time.time() * 1000) < 10

    def test_server_now_ms_without_sync(self):
        """未校时时 server_now_ms 应与 local_now_ms 相近"""
        ts = TimeSync()
        server = ts.server_now_ms()
        local = ts.local_now_ms()
        assert abs(server - local) < 5

    def test_spin_until(self):
        """CPU 自旋应精确到毫秒级"""
        ts = TimeSync()
        target = ts.server_now_ms() + 50  # 50ms 后
        start = time.perf_counter()
        ts.spin_until(target)
        elapsed = (time.perf_counter() - start) * 1000
        # 实际误差应在 15ms 内
        assert abs(elapsed - 50) < 15

    def test_spin_until_past_target(self):
        """目标时间已过时应立即返回"""
        ts = TimeSync()
        target = ts.server_now_ms() - 1000  # 1 秒前
        start = time.perf_counter()
        ts.spin_until(target)
        elapsed = (time.perf_counter() - start) * 1000
        assert elapsed < 5  # 应几乎立即返回

    def test_sleep_precise_short(self):
        """短时间休眠（< 100ms）应使用 CPU 自旋"""
        ts = TimeSync()
        start = time.perf_counter()
        ts.sleep_precise(30)
        elapsed = (time.perf_counter() - start) * 1000
        assert abs(elapsed - 30) < 25

    def test_sleep_precise_long(self):
        """长时间休眠应使用 time.sleep"""
        ts = TimeSync()
        start = time.perf_counter()
        ts.sleep_precise(200)
        elapsed = (time.perf_counter() - start) * 1000
        assert abs(elapsed - 200) < 30

    def test_sleep_zero(self):
        """休眠 0ms 应立即返回"""
        ts = TimeSync()
        start = time.perf_counter()
        ts.sleep_precise(0)
        elapsed = (time.perf_counter() - start) * 1000
        assert elapsed < 5

    def test_sync_ntp(self):
        """NTP 校时应返回合理的偏移值"""
        ts = TimeSync()
        offset = ts.sync(retries=2)
        assert ts._synced is True
        # 偏移应在合理范围内（通常 < 500ms，网络差时放宽）
        assert abs(offset) < 5000, f"NTP 偏移异常: {offset}ms"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
