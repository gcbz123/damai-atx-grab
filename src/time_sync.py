"""NTP 校时与 CPU 自旋定时模块

提供毫秒级精度的定时能力：
  1. 连接 NTP 服务器获取时间偏移
  2. 多 NTP 源交叉校验
  3. CPU 自旋等待到目标时刻（无 sleep 调度抖动）
"""

import time
from loguru import logger


class TimeSync:
    """时间同步与高精度定时器

    Usage:
        ts = TimeSync()
        ts.sync()                          # NTP 校时
        target = ts.server_now_ms() + 5000 # 5 秒后
        ts.spin_until(target)              # CPU 自旋等待
    """

    def __init__(self, ntp_server: str = "ntp.aliyun.com"):
        self.ntp_server = ntp_server
        # offset = 本地时间 - 服务器时间（毫秒）
        self.offset_ms: float = 0.0
        self._synced = False

    def sync(self, retries: int = 3) -> float:
        """NTP 校时，计算本地与 NTP 服务器的时间偏移

        使用 retries 次校时的中位数结果，避免单次网络抖动。

        Args:
            retries: 校时重试次数

        Returns:
            时间偏移量（毫秒），正数 = 本地比服务器快
        """
        import ntplib

        offsets = []
        c = ntplib.NTPClient()

        for attempt in range(retries):
            try:
                resp = c.request(self.ntp_server, version=3, timeout=5)
                # NTP 响应中的 tx_time 是服务器发送时间
                server_time = resp.tx_time
                local_time = time.time()
                offset = (local_time - server_time) * 1000
                offsets.append(offset)
                logger.debug(f"NTP 校时第 {attempt + 1} 次: offset={offset:.1f}ms, delay={resp.delay:.1f}ms")
            except Exception as e:
                logger.warning(f"NTP 校时第 {attempt + 1} 次失败: {e}")

        if not offsets:
            logger.warning("NTP 校时全部失败，使用本地时间")
            self.offset_ms = 0.0
        else:
            # 使用中位数避免异常值
            offsets.sort()
            self.offset_ms = offsets[len(offsets) // 2]
            logger.info(f"NTP 校时完成: offset={self.offset_ms:.1f}ms (使用中位数)")

        self._synced = True
        return self.offset_ms

    def server_now_ms(self) -> int:
        """返回 NTP 服务器当前时间戳（毫秒）

        Returns:
            int: 当前服务器时间戳（毫秒）
        """
        return int(time.time() * 1000 - self.offset_ms)

    def local_now_ms(self) -> int:
        """返回本地当前时间戳（毫秒）"""
        return int(time.time() * 1000)

    def spin_until(self, target_ms: int):
        """CPU 自旋等到目标时刻，精度毫秒级

        Args:
            target_ms: 目标时间戳（毫秒，与 server_now_ms 同基准）
        """
        while self.server_now_ms() < target_ms:
            pass  # busy-wait，避免 sleep 调度抖动

    def sleep_precise(self, duration_ms: int):
        """高精度休眠指定毫秒数

        短时间用 CPU 自旋（< 100ms），长时间用 time.sleep 节省 CPU。

        Args:
            duration_ms: 休眠毫秒数
        """
        if duration_ms <= 0:
            return
        target = self.server_now_ms() + duration_ms
        if duration_ms < 100:
            self.spin_until(target)
        else:
            # time.sleep 精度约 15ms，留 20ms 余量用自旋补偿
            sleep_sec = max(0, (duration_ms - 20) / 1000)
            time.sleep(sleep_sec)
            self.spin_until(target)
