"""抢票流程状态机（精简版）

新流程：
  用户已手动在购票界面 → NTP校时 → 测RTT补偿 → 等待到开售 → 点立即购票 → 选票档 → 点确认 → 结束

状态转换:
  INIT → WAIT → BUY → SELECT_PRICE → CONFIRM → DONE
"""

from datetime import datetime
from typing import Optional
import time
import re as re_mod

import uiautomator2 as u2
from loguru import logger

from src.config_loader import AppConfig
from src.safety_guard import SafetyGuard
from src.time_sync import TimeSync


class Phase:
    """阶段枚举"""
    INIT = "初始化"
    WAIT = "等待开售"
    BUY = "点击购票"
    SELECT_PRICE = "选择票档"
    CONFIRM = "确认订单"
    DONE = "完成"
    ERROR = "错误"


class PhaseMachine:
    """抢票流程状态机（精简版）

    管理从 INIT 到 DONE 的完整抢票流程。
    """

    def __init__(
        self,
        config: AppConfig,
        d: u2.Device,
        safety: SafetyGuard,
    ):
        self.config = config
        self.d = d
        self.safety = safety
        self.current_phase: str = Phase.INIT
        self._rtt_ms: float = 0  # 网络往返延迟（毫秒）

    def run(self) -> str:
        """运行完整的抢票流程

        Returns:
            最终阶段名称
        """
        logger.info("=" * 50)
        logger.info("抢票流程启动")
        logger.info(f"安全模式: {self.safety.mode.mode_name}")
        logger.info("=" * 50)

        try:
            self._run_init()
            self._run_wait()
            self._run_buy()
            self._run_select_price()
            self._run_confirm()
            self.current_phase = Phase.DONE

        except Exception as e:
            logger.exception(f"抢票流程异常: {e}")
            self.current_phase = Phase.ERROR

        logger.info(f"最终状态: {self.current_phase}")
        return self.current_phase

    def set_phase(self, phase: str):
        """切换到新阶段"""
        self.current_phase = phase
        logger.info(f"阶段转换: {self.current_phase}")

    def _run_init(self):
        """阶段 1: 初始化 — NTP 校时"""
        self.set_phase(Phase.INIT)

        # NTP 校时 — 只做一次
        self.time_sync = TimeSync(ntp_server=self.config.ntp_server)
        logger.info("正在进行 NTP 校时...")
        self.time_sync.sync(retries=1)
        logger.info(f"NTP 校时完成: offset={self.time_sync.offset_ms:.1f}ms")

        # 关闭系统动画提升性能（仅首次）
        try:
            self.d.shell("settings put global window_animation_scale 0.0")
            self.d.shell("settings put global transition_animation_scale 0.0")
            self.d.shell("settings put global animator_duration_scale 0.0")
        except Exception:
            pass

    def _run_wait(self):
        """阶段 2: 等待开售 — 测 RTT 补偿，CPU 自旋等待"""
        self.set_phase(Phase.WAIT)

        # 解析开售时间
        try:
            start_dt = datetime.strptime(self.config.start_at, "%Y-%m-%d %H:%M:%S")
            target_ts = int(start_dt.timestamp() * 1000)
        except ValueError as e:
            logger.error(f"开售时间解析失败: {e}")
            self.set_phase(Phase.ERROR)
            return

        # 计算 RTT（通过 adb shell 快速 ping）
        self._measure_rtt()

        # 计算还需要等多久 — 使用已有的 time_sync
        now = self.time_sync.server_now_ms()
        wait_ms = target_ts - now - int(self._rtt_ms)
        logger.info(f"距离开售还有 {wait_ms / 1000:.1f} 秒 (RTT补偿: {self._rtt_ms:.0f}ms)")

        if wait_ms > 0:
            logger.info("⏳ 等待开售...")
            self.time_sync.spin_until(target_ts)
        elif wait_ms < -5000:
            logger.warning(f"开售已过 {-wait_ms / 1000:.1f} 秒，跳过等待")

        logger.info("⏰ 到达开售时间！")

    def _measure_rtt(self):
        """测量 adb 到手机的 RTT（毫秒）

        通过执行一个简单的 adb shell 命令并计时。
        """
        trials = 3
        delays = []
        for _ in range(trials):
            start = time.monotonic_ns()
            try:
                self.d.shell("echo ok")
            except Exception:
                pass
            elapsed_ns = time.monotonic_ns() - start
            delays.append(elapsed_ns / 1_000_000)  # 转为毫秒

        if delays:
            delays.sort()
            median = delays[len(delays) // 2]
            self._rtt_ms = median
            logger.info(f"RTT 测量完成: {median:.1f}ms (中位数, {trials} 次采样)")
        else:
            self._rtt_ms = 0
            logger.warning("RTT 测量失败，使用 0ms 补偿")

    def _run_buy(self):
        """阶段 3: 点击「立即购票」"""
        self.set_phase(Phase.BUY)

        logger.info("--- 点击立即购票 ---")

        # 大麦新版底部栏结构:
        #   btn_buy_view (bounds=[666,2184][1017,2316]) — 购买按钮（自定义View，clickable=false）
        buy_coords = (841, 2250)  # btn_buy_view 中点
        logger.info(f"点击购买按钮 @ {buy_coords}")
        self.d.click(*buy_coords)
        # 页面渲染只需要 ~200ms
        time.sleep(0.2)

    def _ensure_price_page(self):
        """确保页面在票档选择页（大麦可能先展示场次选择页）

        大麦流程: 点击购票 → 场次选择页 → 选场次 → 票档选择页
        需要检测当前页面是否有票档区，没有则先选场次。
        """
        logger.info("--- 确保进入票档页 ---")

        # 检查是否已有票档区
        xml = self.d.dump_hierarchy()
        if 'project_detail_perform_price_flowlayout' in xml:
            logger.info("已在票档页")
            return

        # 没有票档区，说明在场次选择页，先选场次
        logger.info("检测到场次选择页，先选择场次...")

        # 点击第1个场次（中点坐标）
        perform_coords = (540, 751)
        self.d.long_click(*perform_coords, 0.5)
        logger.info(f"已选择第1场 @ {perform_coords}")
        time.sleep(0.5)

        # 验证票档区已加载
        xml = self.d.dump_hierarchy()
        if 'project_detail_perform_price_flowlayout' not in xml:
            logger.warning("场次选择后仍未加载票档区，尝试第2场")
            self.d.long_click(540, 922, 0.5)
            time.sleep(0.5)

    def _run_select_price(self):
        """阶段 4: 确保票档页 → 选择票档"""
        self.set_phase(Phase.SELECT_PRICE)

        logger.info("--- 选择票档 ---")

        if not self.config.price and self.config.price_index == 0:
            logger.info("未配置票价，跳过")
            return

        # 大麦流程: 购票 → 场次选择页 → 选场次 → 票档页
        # 先确保在票档页
        self._ensure_price_page()

        # 选择票档
        self._select_price_item()

        # 等待页面更新（数量按钮出现）
        time.sleep(0.3)

    def _select_price_item(self):
        """选择票档 — 优先从页面 XML 动态查找，失败则降级到硬编码坐标"""
        logger.info(f"选择票档索引: {self.config.price_index}")

        target_idx = self.config.price_index - 1  # 转为 0-based
        if target_idx < 0:
            target_idx = 0

        # 策略 1: 从页面 XML 提取票档列表，按索引选择
        coords = self._find_price_coords_from_xml(target_idx)
        if coords is None:
            # 策略 2: 降级到硬编码坐标
            coords = self._fallback_price_coords(target_idx)

        # 大麦新版需要 long_click 才能触发选中态（普通 click 可能被场次区拦截）
        self.d.long_click(*coords, 0.5)
        logger.info(f"选择票档 @ {coords}")

        # 验证是否选中：检查底部栏是否出现数量选择区
        time.sleep(0.5)
        xml = self.d.dump_hierarchy()
        if 'layout_num' in xml:
            logger.info("票档已选中（检测到数量选择区）")
        else:
            logger.warning("票档可能未选中，重试一次")
            self.d.long_click(*coords, 0.5)
            time.sleep(0.5)

    def _find_price_coords_from_xml(self, target_idx: int) -> Optional[tuple[int, int]]:
        """从页面 XML 中查找票档元素，返回第 N 个的坐标

        搜索策略（优先级从高到低）:
          1. 找 resource-id 含 price_flowlayout/perform_price 的容器内的 clickable 子元素
          2. 找文本含 ¥ / ￥ / 价格数字的节点
          3. 找 resource-id 含 price/ticket 的 clickable 节点
          4. 找通用 clickable 非底部元素

        Args:
            target_idx: 目标索引（0-based）

        Returns:
            (x, y) 坐标，或 None
        """
        try:
            xml = self.d.dump_hierarchy()
            import xml.etree.ElementTree as ET
            import re as re_mod

            root = ET.fromstring(xml.encode("utf-8"))
            screen_w, screen_h = self.d.window_size()

            # 顶部排除高度：状态栏 + 导航栏 (~150px)
            y_min = int(screen_h * 0.12)
            # 底部排除高度：底部导航栏
            y_max = int(screen_h * 0.75)

            # 收集所有节点（遍历一次，后续复用）
            all_nodes = []
            for el in root.iter():
                text = (el.get("text") or "").strip()
                cd = (el.get("content-desc") or "").strip()
                rid = (el.get("resource-id") or "").strip()
                bounds_str = (el.get("bounds") or "").strip()
                clickable = el.get("clickable", "false") == "true"
                if bounds_str:
                    parsed = self._parse_bounds(bounds_str)
                    if parsed:
                        cx, cy = parsed
                        all_nodes.append({
                            "text": text, "content_desc": cd,
                            "rid": rid, "cx": cx, "cy": cy,
                            "clickable": clickable,
                        })

            all_candidates = []

            # ——— 策略 1: 找 price 容器内的 clickable 子元素 ———
            # 大麦票价容器 resource-id 含 price_flowlayout / perform_price
            container_bounds = None
            for n in all_nodes:
                if any(kw in n["rid"] for kw in ('price_flowlayout', 'perform_price', 'price_item')):
                    container_bounds = (n["cx"], n["cy"])
                    # 找到容器后，取它的可见区域上下边界
                    # 直接从 XML 重新解析容器 bounds
                    m = re_mod.search(
                        rf'resource-id="{re_mod.escape(n["rid"])}"[^>]*bounds="(\[(\d+),(\d+)\]\[(\d+),(\d+)\])"',
                        xml
                    )
                    if m:
                        cy1, cy2 = int(m.group(3)), int(m.group(5))
                        # 只取容器范围内的 clickable 元素
                        for cn in all_nodes:
                            if cn["clickable"] and cy1 <= cn["cy"] <= cy2:
                                all_candidates.append((cn["cx"], cn["cy"]))
                        if all_candidates:
                            logger.debug(f"策略1: 在容器 {n['rid']} 内找到 {len(all_candidates)} 个票档")
                            return self._pick_from_candidates(all_candidates, target_idx, "策略1")

            # ——— 策略 2: 文本匹配（¥ / ￥ / 价格数字） ———
            for n in all_nodes:
                text = n["text"] or n["content_desc"]
                if not text:
                    continue
                has_price_symbol = '¥' in text or '￥' in text
                is_price_number = re_mod.match(r'^\d{3,5}$', text)
                if has_price_symbol or is_price_number:
                    cx, cy = n["cx"], n["cy"]
                    if y_min <= cy <= y_max:
                        all_candidates.append((cx, cy))

            # 去重后按 Y 排序
            unique = self._dedup_candidates(all_candidates)
            if unique:
                logger.debug(f"策略2: 文本匹配到 {len(unique)} 个票价候选: {unique}")
                return self._pick_from_candidates(unique, target_idx, "策略2")

            # ——— 策略 3: resource-id 含 price/ticket 的 clickable 元素 ———
            all_candidates = []
            # 先找出所有匹配的 resource-id
            matched_rids = set()
            for n in all_nodes:
                if n["clickable"] and ('price' in n["rid"] or 'ticket' in n["rid"]):
                    matched_rids.add(n["rid"])
            # 收集这些 id 对应元素的坐标（只取 clickable）
            for n in all_nodes:
                if n["rid"] in matched_rids and n["clickable"]:
                    cx, cy = n["cx"], n["cy"]
                    if y_min <= cy <= y_max:
                        all_candidates.append((cx, cy))

            unique = self._dedup_candidates(all_candidates)
            if unique:
                logger.debug(f"策略3: resource-id 匹配到 {len(unique)} 个票价候选: {unique}")
                return self._pick_from_candidates(unique, target_idx, "策略3")

            # ——— 策略 4: 通用 clickable（无 resource-id，不在底部） ———
            all_candidates = []
            for n in all_nodes:
                if n["clickable"] and not n["rid"]:
                    if y_min <= n["cy"] <= y_max:
                        all_candidates.append((n["cx"], n["cy"]))

            unique = self._dedup_candidates(all_candidates)
            if unique:
                logger.debug(f"策略4: 通用 clickable 匹配到 {len(unique)} 个候选: {unique}")
                return self._pick_from_candidates(unique, target_idx, "策略4")

            logger.warning("XML 解析: 所有策略均未找到有效票档")
            return None

        except Exception as e:
            logger.warning(f"XML 查找票档失败: {e}")
            return None

    def _dedup_candidates(self, candidates: list) -> list:
        """去重并排序，基于 10px 精度"""
        if not candidates:
            return []
        seen = set()
        unique = []
        for cx, cy in candidates:
            key = (round(cx / 10) * 10, round(cy / 10) * 10)
            if key not in seen:
                seen.add(key)
                unique.append((cx, cy))
        unique.sort(key=lambda p: p[1])  # 按 Y 排序
        return unique

    def _pick_from_candidates(self, candidates: list, target_idx: int,
                              strategy: str = "") -> Optional[tuple[int, int]]:
        """从候选列表中选取目标索引的坐标"""
        if target_idx < len(candidates):
            coord = candidates[target_idx]
            logger.info(f"XML 选择第 {target_idx + 1} 个票档 @ {coord} (策略: {strategy})")
            return coord
        logger.warning(f"策略{strategy}: 候选 {len(candidates)} 个, 目标索引 {target_idx} 超出")
        return None

    def _parse_bounds(self, bounds_str: str) -> Optional[tuple[int, int]]:
        """解析 bounds="[x1,y1][x2,y2]" 返回中点坐标"""
        m = re_mod.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds_str)
        if m:
            x1, y1, x2, y2 = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
            return ((x1 + x2) // 2, (y1 + y2) // 2)
        return None

    def _fallback_price_coords(self, target_idx: int) -> tuple[int, int]:
        """降级到硬编码坐标（仅覆盖 6 个票档位）

        Args:
            target_idx: 目标索引（0-based）

        Returns:
            (x, y) 坐标
        """
        fallback_coords = [
            (236, 1066),  # 第1行左
            (644, 1066),  # 第1行右
            (295, 1237),  # 第2行左
            (644, 1237),  # 第2行右
            (295, 1408),  # 第3行左
            (644, 1408),  # 第3行右
        ]
        idx = min(target_idx, len(fallback_coords) - 1)
        logger.warning(f"使用降级坐标 {idx}: {fallback_coords[idx]}")
        return fallback_coords[idx]

    def _run_confirm(self):
        """阶段 5: 点击「确认」并提交订单"""
        self.set_phase(Phase.CONFIRM)

        logger.info("--- 确认订单 ---")

        # 大麦新版：底部购买按钮是 btn_buy_view，选中票档后 clickable=true
        # 未选中时 clickable=false，需要重试直到按钮可用
        buy_coords = (841, 2250)
        confirmed = False

        for attempt in range(5):
            self.d.click(*buy_coords)
            time.sleep(0.5)

            # 检查是否已跳转到订单页 — 通过 XML 特征判断
            xml = self.d.dump_hierarchy()
            if '立即提交' in xml or 'submit_order' in xml or 'order_activity' in xml:
                confirmed = True
                logger.info(f"已点击提交按钮 @ {buy_coords} (第 {attempt+1} 次)")
                break

            logger.debug(f"第 {attempt+1} 次点击提交，尚未跳转")

        if not confirmed:
            logger.warning("多次尝试后仍未进入订单页")
            self.set_phase(Phase.ERROR)
            return

        # 检查订单页特征
        xml = self.d.dump_hierarchy()
        if '立即提交' in xml or 'order_activity' in xml:
            logger.info("✅ 已进入订单确认页！")
            logger.info("=" * 50)
            logger.info("🎉 请在手机上手动完成支付")
            logger.info("=" * 50)
        else:
            logger.info("请检查手机是否已进入订单页面")

        self.set_phase(Phase.DONE)
