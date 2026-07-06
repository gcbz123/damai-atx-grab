"""抢票流程状态机（精简版）

新流程：
  用户已手动在购票界面 → 测RTT补偿 → 等待到开售 → 点立即购票
  → 选票档 → 点立即提交 → 用户手动支付 → 结束
  （NTP校时已移除，由GUI手动校时；观演人由用户手动勾选，脚本不介入）

状态转换:
  INIT → WAIT → BUY → SELECT_PRICE → CONFIRM → DONE
"""

from datetime import datetime
from typing import Optional
import time
import re as re_mod

import uiautomator2 as u2
from loguru import logger

# 预编译正则常量（避免循环内重复编译）
_BOUNDS_RE = re_mod.compile(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]')
_PRICE_DIGITS_RE = re_mod.compile(r'^\d{3,5}$')

from src.config_loader import AppConfig
from src.safety_guard import SafetyGuard


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
        self.clicker = None  # 将在 _run_init 中初始化
        self._sprint_engine = None
        self._submit_btn_coords: Optional[tuple[int, int]] = None  # 立即提交按钮坐标缓存（P0+）

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
        except Exception as e:
            logger.exception(f"抢票流程异常: {e}")
            self.current_phase = Phase.ERROR

        if self.current_phase != Phase.ERROR:
            self.current_phase = Phase.DONE

        logger.info(f"最终状态: {self.current_phase}")
        return self.current_phase

    def set_phase(self, phase: str):
        """切换到新阶段"""
        self.current_phase = phase
        logger.info(f"阶段转换: {self.current_phase}")

    def _run_init(self):
        """阶段 1: 初始化 — 关闭动画 + 盲点点击器（NTP 校时已移除，由 GUI 手动校时）"""
        self.set_phase(Phase.INIT)

        # 关闭系统动画提升性能（仅首次）
        try:
            self.d.shell("settings put global window_animation_scale 0.0")
            self.d.shell("settings put global transition_animation_scale 0.0")
            self.d.shell("settings put global animator_duration_scale 0.0")
        except Exception:
            pass

        # 初始化盲点点击器（不预热，点击时动态校准）
        from src.coord_blind import CoordBlindClicker
        self.clicker = CoordBlindClicker(self.d)

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

        # 用本地时间计算等待时长（NTP 校时已移除，用户手动负责本地时间准确）
        now = int(time.time() * 1000)
        wait_ms = target_ts - now - int(self._rtt_ms)
        logger.info(f"距离开售还有 {wait_ms / 1000:.1f} 秒 (RTT补偿: {self._rtt_ms:.0f}ms)")

        if wait_ms > 0:
            logger.info("⏳ 等待开售...")
            # 长等待用 time.sleep 省 CPU
            if wait_ms > 200:
                time.sleep((wait_ms - 50) / 1000)
            # 最后 50ms CPU 自旋保证精度
            while int(time.time() * 1000) < target_ts - int(self._rtt_ms):
                pass
        elif wait_ms < -5000:
            logger.warning(f"开售已过 {-wait_ms / 1000:.1f} 秒，跳过等待")

        logger.info("⏰ 到达开售时间！")

    def _measure_rtt(self):
        """测量 adb 到手机的 RTT（毫秒）

        优化：单次采样省一次 adb 往返（原 2 次中位数对 N=2 等价于第 1 小值，无统计意义）。
        """
        start = time.monotonic_ns()
        try:
            self.d.shell("echo ok")
        except Exception:
            pass
        elapsed_ns = time.monotonic_ns() - start
        self._rtt_ms = elapsed_ns / 1_000_000  # 转为毫秒
        logger.info(f"RTT 测量完成: {self._rtt_ms:.1f}ms (单次采样)")

    def _run_buy(self):
        """阶段 3: 点击「立即购票」"""
        self.set_phase(Phase.BUY)

        logger.info("--- 点击立即购票 ---")

        # 使用盲点点击器预热坐标（比硬编码更可靠）
        if hasattr(self, 'clicker') and self.clicker and self.clicker.has_coord('buy_btn'):
            logger.info("使用盲点点击器点击购票按钮")
            self.clicker.blind_click('buy_btn')
        else:
            # 降级到硬编码坐标
            buy_coords = (841, 2250)
            logger.info(f"点击购买按钮 @ {buy_coords}")
            self.d.click(*buy_coords)

        # P1: 用 Activity 轮询代替固定 sleep(0.1)，跳转到票档页即退出（最多 0.5s 兜底）
        # 实测 d.info 没有 currentActivity 字段（只有 currentPackageName），必须用 dumpsys
        self._poll_until_activity_change(
            deadline_ms=500,
            poll_interval_ms=30,
            exit_pred=lambda act: act != "" and "detail" not in act.lower(),
            log_label="BUY→票档页",
        )

    def _poll_until_activity_change(
        self,
        deadline_ms: int,
        poll_interval_ms: int,
        exit_pred,
        log_label: str = "",
    ) -> str:
        """通用 Activity 轮询：返回最后拿到的 Activity 名（即使没匹配 exit_pred 也超时退出）

        Args:
            deadline_ms: 总超时（毫秒）
            poll_interval_ms: 轮询间隔
            exit_pred: 接收 activity_str，返回 True 则提前退出
            log_label: 用于日志标记当前阶段

        Returns:
            最后一次轮询到的 Activity 名（空字符串表示完全没拿到）
        """
        start = time.time()
        deadline = start + deadline_ms / 1000
        last_act = ""
        poll_count = 0
        while time.time() < deadline:
            try:
                out = self.d.shell("dumpsys window | grep mCurrentFocus").output or ""
                # 输出示例: "  mCurrentFocus=Window{xxx u0 cn.damai/cn.damai....ActivityName}\n"
                # 提取最后一段包名 + 活动名
                import re as _re
                m = _re.search(r'mCurrentFocus=Window\{[^}]+u0\s+([^}/]+)/([^}/\s]+)', out)
                if m:
                    last_act = m.group(2)  # 仅取 Activity 名（去掉包名前缀）
                else:
                    # 备用正则：拿掉换行后的整个 token
                    m = _re.search(r'mCurrentFocus=Window\{[^}]+\s+([^\s}]+)', out)
                    if m:
                        last_act = m.group(1)
            except Exception:
                pass
            poll_count += 1
            if last_act and exit_pred(last_act):
                elapsed = (time.time() - start) * 1000
                logger.info(f"[{log_label}] Activity 切换到 '{last_act}' (轮询 {poll_count} 次, {elapsed:.0f}ms)")
                return last_act
            time.sleep(poll_interval_ms / 1000)
        elapsed = (time.time() - start) * 1000
        logger.info(f"[{log_label}] 轮询超时 {deadline_ms}ms (轮询 {poll_count} 次, last='{last_act}', {elapsed:.0f}ms)")
        return last_act

    def _ensure_price_page(self):
        """确保页面在票档选择页（大麦可能先展示场次选择页）

        优化:
        - 减少 dump_hierarchy 调用，先用 u2 API 快速检测。
        - P2: u2 API miss 后用 Activity 检测区分「已票档页」vs「场次选择页」，
          避免无意义的 dump（票档页 ADN 不到 perform_price 时省 ~700ms）。
        """
        logger.info("--- 确保进入票档页 ---")

        # 快速检测：用 u2 API 查找票价相关元素（比 XML dump 快 5-10x）
        try:
            if self.d(resourceIdContains='perform_price', clickable=True).exists:
                logger.info("已在票档页（u2 API 检测到票价元素）")
                return
        except Exception:
            pass

        # P2: u2 API 未命中，先用 Activity 判断是否已在票档页
        # 大麦票档/价格选择页 Activity 含 ticket/sku/price/perform
        # 场次选择页 Activity 通常仍含 detail 或无变化
        try:
            out = self.d.shell("dumpsys window | grep mCurrentFocus").output or ""
            import re as _re
            m = _re.search(r'mCurrentFocus=Window\{[^}]+u0\s+([^}/]+)/([^}/\s]+)', out)
            activity = m.group(2) if m else ""
        except Exception:
            activity = ""
        activity_lower = activity.lower()

        if activity_lower and ('ticket' in activity_lower or 'sku' in activity_lower
                                or 'price' in activity_lower or 'perform' in activity_lower):
            # 已在票档页：Activity 已确认，但票价数据可能异步加载未完成。
            # 缓存 XML 时校验是否含价格标记（¥/￥），无则短轮询重试。
            logger.info(f"Activity={activity} 确认在票档页，缓存 XML")
            for _ in range(5):
                self._cached_xml = self.d.dump_hierarchy()
                if '¥' in self._cached_xml or '￥' in self._cached_xml:
                    import xml.etree.ElementTree as ET
                    self._cached_xml_tree = ET.fromstring(self._cached_xml.encode("utf-8"))
                    return
                time.sleep(0.08)
            # 5 次重试后仍无价格标记，用最后一次的缓存（_find_price_coords 可能兜底到）
            logger.warning("票价数据可能未完全渲染，使用最后一次缓存")
            import xml.etree.ElementTree as ET
            self._cached_xml_tree = ET.fromstring(self._cached_xml.encode("utf-8"))
            return

        # u2 API 未命中 + Activity 不在票档页 → 大概率还在场次选择页
        # 用 XML dump 精确检测场次选择页（这是必须的，因为要确认是否需要选场次）
        logger.info("u2 API 未检测到票档区，使用 XML dump 精确检测...")
        xml = self.d.dump_hierarchy()
        import xml.etree.ElementTree as ET
        # 缓存 XML 字符串 + 解析树给后续 _find_price_coords 复用（避免重复 ET.fromstring）
        self._cached_xml = xml
        self._cached_xml_tree = ET.fromstring(xml.encode("utf-8"))
        if 'project_detail_perform_price_flowlayout' in xml:
            logger.info("已在票档页（XML 检测）")
            return

        # 没有票档区，说明在场次选择页，先选场次
        logger.info("检测到场次选择页，先选择场次...")

        # 点击第1个场次（中点坐标）— 改用 click 而非 long_click 节省时间
        perform_coords = (540, 751)
        self.d.click(*perform_coords)
        logger.info(f"已选择第1场 @ {perform_coords}")
        time.sleep(0.15)

        # 再次快速检测（用 u2 API 而非 XML）
        try:
            if self.d(resourceIdContains='perform_price', clickable=True).exists:
                logger.info("场次选择成功，票档区已加载")
                # 页面已变，缓存 XML 及解析树已过期
                self._cached_xml = self._cached_xml_tree = None
                return
        except Exception:
            pass

        # 仍然没找到，尝试第2场
        logger.warning("第1场未加载票档区，尝试第2场")
        self.d.click(540, 922)
        time.sleep(0.15)
        # 页面已变，缓存 XML 及解析树已过期
        self._cached_xml = self._cached_xml_tree = None

    def _run_select_price(self):
        """阶段 4: 确保票档页 → 选择票档"""
        self.set_phase(Phase.SELECT_PRICE)

        logger.info("--- 选择票档 ---")

        if not self.config.price and self.config.price_index == 0:
            logger.info("未配置票价，跳过")
            return

        # 先确保在票档页
        self._ensure_price_page()

        # 选择票档
        self._select_price_item()

    def _select_price_item(self):
        """选择票档 — 优先从页面 XML 动态查找，失败则降级到硬编码坐标

        优化:
        - 改用 click 替代 long_click（节省 0.3s）
        - P3: 轮询间隔改 20ms（原 50ms），超时 0.6s（原 0.3s）——
          实测 layout_num 元素可能出现稍晚，0.3s 不够稳；
          20ms 间隔让首次命中加快 ~30ms，0.6s 超时给页面加载留余量。
        - P3: 重试时对 xml-c 策略返回的坐标做 +15px 横向偏移（实测 (212,1360)
          第一次未命中按钮有效区，+15px 偏到按钮中心更靠右的可点击区）。
        """
        logger.info(f"选择票档索引: {self.config.price_index}")

        target_idx = self.config.price_index - 1  # 转为 0-based
        if target_idx < 0:
            target_idx = 0

        # 策略 1: 从页面 XML 提取票档列表，按索引选择（复用缓存 XML）
        coords = self._find_price_coords(target_idx, cached_xml=getattr(self, '_cached_xml', None))
        strategy_used = getattr(self, '_last_strategy', '')
        if coords is None:
            # 策略 2: 降级到硬编码坐标
            coords = self._fallback_price_coords(target_idx)
            strategy_used = 'fallback'

        # 对 xml-c 策略直接应用 +15px 横向偏移（实测 xml-c 计算的中心偏左，
        # (212,1360) 未命中可点击区，(227,1360) 命中。直接偏移，避免重试多耗 ~800ms）
        if strategy_used == 'xml-c':
            coords = (coords[0] + 15, coords[1])
            logger.info(f"xml-c 坐标 +15px 偏移 -> {coords}")

        # 使用 click 而非 long_click（节省 300ms+）
        self.d.click(*coords)
        logger.info(f"选择票档 @ {coords} (策略: {strategy_used})")

        # 页面短暂稳定（无需轮询 layout_num——实测该元素在当前 UI 版本不存在，
        # 轮询只会空跑 600ms 然后触发无意义重试。+15px 偏移已确保命中率）
        time.sleep(0.08)

    def _find_price_coords(self, target_idx: int, cached_xml: str = None) -> Optional[tuple[int, int]]:
        """查找票档元素坐标，返回第 N 个的坐标

        多策略混合定位，优先级从高到低:
          0. u2 API 直接查找（更可靠）:
             a. 按 resource-id 含 perform_price / price_item 的容器内的子元素
             b. 按文本含票价关键字（¥/￥/元/看台/内场/VIP）的 clickable 元素
             c. 按 resource-id 含 price/ticket 的 clickable 元素
          1. XML 解析（兜底）:
             a. 文本匹配（同 0b）
             b. resource-id 匹配（同 0c，加 Y 过滤）
             c. 通用 clickable + 行 Y 分组

        Args:
            target_idx: 目标索引（0-based）
            cached_xml: 缓存的 XML 字符串，避免重复 dump_hierarchy

        Returns:
            (x, y) 坐标，或 None
        """
        self._last_strategy = ''  # P3: 跟踪本次定位策略，供 _select_price_item 重试参考
        screen_w, screen_h = self.d.window_size()
        y_min = int(screen_h * 0.1)    # 排除顶部标题栏
        y_max = int(screen_h * 0.72)   # 排除底部导航栏
        min_width = int(screen_w * 0.08)  # 最小宽度（排除小图标）

        # 优先使用缓存的 XML 树（来自 _ensure_price_page 的 XML dump）
        # 有缓存树则跳过 u2 API 的 7 次 USB 查询（省 ~400ms），直接走 XML 解析
        cached_tree = getattr(self, '_cached_xml_tree', None)
        if cached_tree is None:
            # === 阶段 0: u2 API 直接查找（无缓存树时才有必要查） ===
            candidates = self._find_via_u2_api(y_min, y_max, min_width, target_idx)
            if candidates is not None:
                return candidates

        # === 阶段 1: XML 解析兜底（优先使用缓存 XML + 解析树） ===
        if cached_xml is None:
            cached_xml = getattr(self, '_cached_xml', None)
        candidates = self._find_via_xml(y_min, y_max, min_width, target_idx, cached_xml, cached_tree)
        if candidates is not None:
            return candidates

        logger.warning("所有策略均未找到票档")
        return None

    def _find_via_u2_api(self, y_min: int, y_max: int, min_width: int,
                         target_idx: int) -> Optional[tuple[int, int]]:
        """通过 uiautomator2 API 查找票档元素

        优化：减少 ADB 查询次数，u2-b 只试价格符号（原 9 次 → 2 次）。
        """

        # — u2-a: 按 resource-id 含 perform_price / price_item 的容器 ———
        for rid_kw in ('perform_price', 'price_item', 'price_flowlayout'):
            try:
                child = self.d(resourceIdContains=rid_kw).child(clickable=True)
                if child.exists:
                    coords = []
                    for el in child:
                        cx, cy = el.center
                        if y_min <= cy <= y_max:
                            coords.append((cx, cy))
                    coords = self._dedup_candidates(coords)
                    if coords:
                        logger.debug(f"u2-a({rid_kw}): 容器内找到 {len(coords)} 个")
                        return self._pick_from_candidates(coords, target_idx, "u2-a")
            except Exception:
                pass

        # — u2-b: 按文本含票价关键字查找 ———
        # 只试价格符号（最专一，排除页码 3/3、日期等误匹配）
        for kw in ('¥', '￥'):
            try:
                els = self.d(textContains=kw, clickable=True)
                if els.exists:
                    coords = []
                    for el in els:
                        cx, cy = el.center
                        if y_min <= cy <= y_max:
                            coords.append((cx, cy))
                    coords = self._dedup_candidates(coords)
                    if coords:
                        logger.debug(f"u2-b({kw}): 文本匹配到 {len(coords)} 个")
                        return self._pick_from_candidates(coords, target_idx, "u2-b")
            except Exception:
                pass

        # — u2-c: 按 resource-id 含 price/ticket 查找 ———
        for rid_kw in ('price', 'ticket'):
            try:
                els = self.d(resourceIdContains=rid_kw, clickable=True)
                if els.exists:
                    coords = []
                    for el in els:
                        cx, cy = el.center
                        if y_min <= cy <= y_max:
                            coords.append((cx, cy))
                    coords = self._dedup_candidates(coords)
                    if coords:
                        logger.debug(f"u2-c({rid_kw}): resource-id 匹配到 {len(coords)} 个")
                        return self._pick_from_candidates(coords, target_idx, "u2-c")
            except Exception:
                pass

        return None

    def _find_via_xml(self, y_min: int, y_max: int, min_width: int,
                      target_idx: int, cached_xml: str = None,
                      cached_tree=None) -> Optional[tuple[int, int]]:
        """通过解析页面 XML 查找票档元素（兜底方案）

        优化: 单次遍历收集所有策略候选，单次正则解析 bounds（原 4 遍历 + 2 正则/节点）。
        Args:
            cached_xml: 已缓存的 XML，避免重复 dump_hierarchy
            cached_tree: 已缓存的 ElementTree 根节点，避免重复 ET.fromstring
        """
        try:
            if cached_tree is not None:
                root = cached_tree
            else:
                xml = cached_xml or self.d.dump_hierarchy()
                import xml.etree.ElementTree as ET
                root = ET.fromstring(xml.encode("utf-8"))

            # 单次遍历 XML，同时收集 xml-a/b/c 的候选
            # 用 findall + XPath 在 C 层级过滤 clickable + bounds（跳过 Python 非匹配节点开销）
            candidates_a = []   # xml-a: 文本匹配
            candidates_b = []   # xml-b: resource-id 匹配
            clickable_raw = []  # xml-c: (cx, cy, w)

            for el in root.findall('.//*[@clickable="true"][@bounds]'):
                bounds_str = (el.get("bounds") or "").strip()
                m = _BOUNDS_RE.match(bounds_str)
                if not m:
                    continue
                x1, y1, x2, y2 = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
                text = (el.get("text") or "").strip()
                cd = (el.get("content-desc") or "").strip()
                rid = (el.get("resource-id") or "").strip()
                cx, cy, w = (x1 + x2) // 2, (y1 + y2) // 2, x2 - x1
                if not (y_min <= cy <= y_max):
                    continue

                clickable_raw.append((cx, cy, w))

                # xml-a: 文本匹配
                text_content = text or cd
                if text_content:
                    if '¥' in text_content or '￥' in text_content or '元' in text_content:
                        if w >= min_width:
                            candidates_a.append((cx, cy))
                    elif _PRICE_DIGITS_RE.match(text_content):
                        if w >= min_width:
                            candidates_a.append((cx, cy))

                # xml-b: resource-id 匹配
                if rid and ('price' in rid or 'ticket' in rid) and w >= min_width:
                    candidates_b.append((cx, cy))

            # —— xml-a ———
            unique = self._dedup_candidates(candidates_a)
            if unique:
                logger.debug(f"xml-a 文本匹配到 {len(unique)} 个: {unique}")
                result = self._pick_from_candidates(unique, target_idx, "xml-a")
                if result:
                    return result

            # —— xml-b ———
            unique = self._dedup_candidates(candidates_b)
            if 1 <= len(unique) <= 20:
                logger.debug(f"xml-b resource-id 匹配到 {len(unique)} 个: {unique}")
                result = self._pick_from_candidates(unique, target_idx, "xml-b")
                if result:
                    return result

            # —— xml-c: Y 行分组 ———
            clickable_in_zone = [(cx, cy) for cx, cy, w in clickable_raw if w >= min_width]
            if not clickable_in_zone:
                clickable_in_zone = [(cx, cy) for cx, cy, w in clickable_raw]

            if clickable_in_zone:
                buckets: dict[int, list] = {}
                for cx, cy in clickable_in_zone:
                    y_bucket = round(cy / 20) * 20
                    buckets.setdefault(y_bucket, []).append((cx, cy))

                multi_buckets = [(y, items) for y, items in sorted(buckets.items())
                                 if len(items) >= 2]
                if multi_buckets:
                    flattened = []
                    for y, items in multi_buckets:
                        items.sort(key=lambda p: p[0])
                        flattened.extend(items)
                    flattened = self._dedup_candidates(flattened)
                    logger.debug(f"xml-c 行分组到 {len(flattened)} 个: {flattened}")
                    result = self._pick_from_candidates(flattened, target_idx, "xml-c")
                    if result:
                        return result

                all_coords = self._dedup_candidates(clickable_in_zone)
                if all_coords:
                    logger.debug(f"xml-c 最终兜底 {len(all_coords)} 个: {all_coords}")
                    return self._pick_from_candidates(all_coords, target_idx, "xml-c")

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
            logger.info(f"选择第 {target_idx + 1} 个票档 @ {coord} (策略: {strategy})")
            self._last_strategy = strategy  # P3: 让 _select_price_item 知道用了哪个策略
            return coord
        logger.warning(f"策略{strategy}: 候选 {len(candidates)} 个, 目标索引 {target_idx} 超出")
        return None

    def _parse_bounds(self, bounds_str: str) -> Optional[tuple[int, int]]:
        """解析 bounds="[x1,y1][x2,y2]" 返回中点坐标"""
        m = _BOUNDS_RE.match(bounds_str)
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

    def _find_submit_btn_coords(self, xml: str) -> Optional[tuple[int, int]]:
        """从 XML 中定位提交按钮的坐标

        支持多种文本变体（立即提交 / 提交订单 / 提交）
        和 resource-id 匹配（submit / pay / commit），
        以及大麦确认页（不含按钮文本时）的兜底策略。
        """
        import xml.etree.ElementTree as ET

        root = ET.fromstring(xml.encode("utf-8"))
        screen_w, screen_h = self.d.window_size()
        y_bottom = int(screen_h * 0.75)  # 底部按钮区起点

        # —— 策略 1: 文本匹配（最精确） ——
        _SUBMIT_TEXTS = ('立即提交', '提交订单', '确认提交', '去支付', '提交')
        target_node = None
        matched_text = ''
        for el in root.iter():
            text = (el.get("text") or "").strip()
            cd = (el.get("content-desc") or "").strip()
            for kw in _SUBMIT_TEXTS:
                if kw in text or kw in cd:
                    target_node = el
                    matched_text = kw
                    break
            if target_node:
                break

        if target_node is not None:
            coord = self._resolve_clickable_node(target_node, root)
            if coord:
                logger.info(f"文本匹配「{matched_text}」-> @{coord}")
                return coord

        # —— 策略 2: resource-id 匹配 ——
        for el in root.iter():
            rid = (el.get("resource-id") or "").strip()
            if any(kw in rid for kw in ('submit', 'pay', 'commit', 'btn_bottom', 'bottom_button')):
                coord = self._resolve_clickable_node(el, root)
                if coord:
                    logger.info(f"resource-id 匹配 {rid} -> @{coord}")
                    return coord

        # —— 策略 3: 底部宽按钮兜底 ——
        # 在订单页底部找宽度 > 80% 屏宽的 clickable 按钮
        candidates = []
        for el in root.iter():
            if el.get("clickable", "false") != "true":
                continue
            bounds_str = (el.get("bounds") or "").strip()
            m = _BOUNDS_RE.match(bounds_str)
            if not m:
                continue
            x1, y1, x2, y2 = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
            cy = (y1 + y2) // 2
            w = x2 - x1
            if cy >= y_bottom and w > int(screen_w * 0.8):
                candidates.append(((x1 + x2) // 2, cy))
        if candidates:
            candidates.sort(key=lambda p: p[1], reverse=True)  # 取最底部
            logger.info(f"底部宽按钮兜底 @{candidates[0]}")
            return candidates[0]

        return None

    def _resolve_clickable_node(self, node, root) -> Optional[tuple[int, int]]:
        """从目标节点出发，找到可点击的坐标点"""
        # 自身 clickable
        if node.get("clickable", "false") == "true":
            bounds_str = node.get("bounds", "")
            m = _BOUNDS_RE.match(bounds_str)
            if m:
                x = (int(m.group(1)) + int(m.group(3))) // 2
                y = (int(m.group(2)) + int(m.group(4))) // 2
                return (x, y)

        # 向上找 clickable 祖先
        parent_map = {child: parent for parent in root.iter() for child in parent}
        cur = node
        for _ in range(5):
            if cur not in parent_map:
                break
            cur = parent_map[cur]
            if cur.get("clickable", "false") == "true":
                bounds_str = cur.get("bounds", "")
                m = _BOUNDS_RE.match(bounds_str)
                if m:
                    return ((int(m.group(1)) + int(m.group(3))) // 2,
                            (int(m.group(2)) + int(m.group(4))) // 2)

        # 直接点文本节点
        bounds_str = node.get("bounds", "")
        m = _BOUNDS_RE.match(bounds_str)
        if m:
            return ((int(m.group(1)) + int(m.group(3))) // 2,
                    (int(m.group(2)) + int(m.group(4))) // 2)

        return None

    def _run_confirm(self):
        """阶段 5: 进入订单页 → 点击「立即提交」（用户手动勾选观演人）

        优化：
        - P0: 用 Activity 轮询代替固定 sleep(0.5)（实测 d.info 没有 currentActivity，
          用 d.shell dumpsys window 拿 Activity，~130ms/次；2-3 次轮询优于固定 500ms）
        - P0+: 缓存 _submit_btn_coords，命中则跳过 dump_hierarchy（省 ~700ms）
        - 连点 2 次间不再 sleep（click 命令天然串行）
        """
        self.set_phase(Phase.CONFIRM)

        logger.info("--- 确认订单 ---")

        # 第一步：连点 2 次底部购买按钮进入订单页（两次 click 之间不需 sleep，
        # click 命令串行执行，第一次 click 已在 USB 上排队）
        buy_coords = (841, 2250)
        self.d.click(*buy_coords)
        self.d.click(*buy_coords)

        # P0: 用 Activity 轮询检测页面跳转（~130ms 一次 dumpsys），超时 1.2s 兜底
        activity_lower = ""
        last_activity = self._poll_until_activity_change(
            deadline_ms=1200,
            poll_interval_ms=50,
            exit_pred=lambda act: 'order' in act.lower() or 'confirm' in act.lower(),
            log_label="CONFIRM→订单页",
        )
        activity_lower = last_activity.lower()
        entered_order = 'order' in activity_lower or 'confirm' in activity_lower

        if not entered_order:
            # Activity 检测失败兜底：dump 一次确认是否在订单页
            logger.warning(f"Activity 轮询未确认进入订单页 (last={last_activity}), 用 XML 兜底")
            xml = self.d.dump_hierarchy()
            if '立即提交' in xml or 'submit_order' in xml or 'order_activity' in xml:
                entered_order = True
            else:
                logger.warning("连点2次后仍未进入订单页")
                self.set_phase(Phase.ERROR)
                return
        # 进入订单页后：等待页面渲染完成再搜按钮
        # Activity 名在 onCreate 就设置好了，但 UI 元素（提交按钮）需要额外时间渲染，
        # 实测约 1.2s 按钮才进入 XML。首次等 300ms 再 dump（减少 dump 次数），
        # 然后短轮询（100ms 间隔，2.5s 兜底，50 次循环 ≈ 5 次 dump）。
        logger.info("等待订单页渲染（短轮询检测提交按钮）...")
        submit_coords = self._submit_btn_coords
        if submit_coords is None:
            time.sleep(0.3)  # 首次等 300ms，避免渲染未完成时的 dump 浪费
            _find_start = time.time()
            while time.time() - _find_start < 2.5:
                xml = self.d.dump_hierarchy()
                submit_coords = self._find_submit_btn_coords(xml)
                if submit_coords is not None:
                    self._submit_btn_coords = submit_coords
                    logger.info(f"已缓存提交按钮坐标: {submit_coords} (查找耗时: {int((time.time()-_find_start)*1000)}ms)")
                    break
                time.sleep(0.1)
        else:
            logger.info(f"复用缓存的提交按钮坐标: {submit_coords}")

        if submit_coords is None:
            logger.warning("页面渲染超时，未找到提交按钮坐标")
            self.set_phase(Phase.ERROR)
            return
        logger.info("已进入订单页，提交按钮已定位")

        # 第二步：等待页面稳定，用户可在此手动勾选观演人
        logger.info("等待页面稳定，请手动勾选观演人...")
        time.sleep(0.3)

        # 第三步：点击「立即提交」
        logger.info("点击「立即提交」...")
        self.d.click(*submit_coords)
        logger.info(f"已点击提交按钮 @ {submit_coords}")

        self.set_phase(Phase.DONE)
        logger.info("=" * 50)
        logger.info("🎉 订单已提交，请在手机上手动完成支付")
        logger.info("=" * 50)
