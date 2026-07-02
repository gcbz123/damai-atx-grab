"""GUI 后台工作线程

在 QThread 中执行设备连接和 PhaseMachine 抢票流程，
通过 Qt 信号与主界面通信。
"""

import time
from typing import Any, Optional

from PyQt6.QtCore import QThread, pyqtSignal

import uiautomator2 as u2
from loguru import logger

from src.config_loader import AppConfig, load_config
from src.safety_guard import SafetyGuard
from src.phase_machine import PhaseMachine
from src.logger import LoggerManager


class LogSignalEmitter:
    """将日志消息通过回调发送到 GUI"""

    def __init__(self, callback):
        self.callback = callback

    def write(self, message):
        if self.callback and message.strip():
            self.callback(message.strip())

    def flush(self):
        pass


class GrabWorker(QThread):
    """抢票后台工作线程

    Signals:
        log_message(str): 日志消息
        phase_changed(str): 阶段名称
        progress_update(int, str): (百分比, 描述)
        device_info(str, str, str): (设备名, 分辨率, 状态)
        device_error(str): 设备错误
        finished(int): 最终阶段 (Phase.value)
    """

    log_message = pyqtSignal(str)
    phase_changed = pyqtSignal(str)
    progress_update = pyqtSignal(int, str)
    device_info = pyqtSignal(str, str, str)
    device_error = pyqtSignal(str)
    connect_finished = pyqtSignal(bool)
    detect_result = pyqtSignal(dict)
    ntp_test_result = pyqtSignal(str, float)  # (server_name, offset_ms)
    finished = pyqtSignal(int)

    def __init__(self, config_path: str, parent=None):
        super().__init__(parent)
        self.config_path = config_path
        self._config: Optional[AppConfig] = None
        self._device: Optional[u2.Device] = None
        self._machine: Optional[PhaseMachine] = None
        self._running = False
        self._abort = False
        self._pending_udid = ""        # 待连接的 udid
        self._pending_ntp_server = ""  # 待测试的 NTP 服务器
        self._task = ""                # "connect" | "detect" | "ntp_test" | "workflow"

        # 挂载日志钩子
        self._loguru_handler_id = None

    def _install_log_hook(self):
        """挂载 loguru 到 GUI 日志输出（去重：仅挂载一次）"""
        if self._loguru_handler_id is not None:
            return
        self._loguru_handler_id = logger.add(
            self._emit_log,
            format="{message}",
            level="DEBUG",
            colorize=False,
        )

    def _remove_log_hook(self):
        if self._loguru_handler_id:
            logger.remove(self._loguru_handler_id)
            self._loguru_handler_id = None

    def _emit_log(self, message):
        """loguru 回调 -> Qt 信号"""
        if self.log_message:
            self.log_message.emit(message)

    def abort(self):
        """请求停止工作"""
        self._abort = True
        logger.warning("用户请求停止")

    def connect_device(self, udid: str = ""):
        """异步连接 Android 设备（通过线程执行，不阻塞主线程）

        Args:
            udid: adb 设备序列号，留空自动选择
        """
        self._pending_udid = udid
        self._task = "connect"
        self._abort = False
        self.start()  # -> run()

    def request_detect(self):
        """异步检测手机当前页面信息（在后台线程执行）

        从已连接的手机 dump 当前页面 XML，提取城市/日期/票价等信息。
        """
        self._task = "detect"
        self._abort = False
        self.start()

    def test_ntp(self, server: str = "ntp.aliyun.com"):
        """异步测试 NTP 服务器连通性

        Args:
            server: NTP 服务器地址
        """
        self._pending_ntp_server = server
        self._task = "ntp_test"
        self._abort = False
        self.start()

    def disconnect_device(self):
        """断开设备连接"""
        self._device = None
        self.device_info.emit("", "", "未连接")
        self._remove_log_hook()

    def run_workflow(self, config: AppConfig):
        """运行抢票流程

        Args:
            config: 应用配置（含安全模式设置）
        """
        self._config = config
        self._abort = False
        self.start()  # 启动线程

    def _run_connect(self):
        """后台线程：连接设备"""
        try:
            udid = self._pending_udid
            if udid:
                logger.info(f"连接设备: {udid}")
                self._device = u2.connect(udid)
            else:
                logger.info("连接设备（自动选择第一个）")
                self._device = u2.connect()

            info = self._device.info
            name = info.get("productName", "Unknown")
            size = f"{self._device.window_size()[0]}x{self._device.window_size()[1]}"

            logger.info(f"设备连接成功: {name}")
            logger.info(f"屏幕: {size}")

            self.device_info.emit(name, size, "已连接")
            self.connect_finished.emit(True)

        except Exception as e:
            err = f"设备连接失败: {e}"
            logger.error(err)
            self.device_error.emit(err)
            self.connect_finished.emit(False)
        finally:
            self._running = False

    def _run_detect(self):
        """后台线程：检测手机当前页面，提取演出信息

        通过 uiautomator2 dump 当前页面 XML 层次结构，
        使用启发式规则提取城市、日期、票价等信息。
        """

        if self._device is None:
            logger.error("设备未连接，无法检测页面")
            self.detect_result.emit({"error": "设备未连接，请先连接设备"})
            self._running = False
            return

        try:
            logger.info("正在检测手机当前页面...")

            # 获取当前 activity 确认在大麦内
            try:
                activity = self._device.info.get("currentActivity", "")
                logger.info(f"当前 Activity: {activity}")
            except Exception:
                activity = ""

            # dump 页面 XML
            xml_str = self._device.dump_hierarchy()
            logger.info(f"页面 XML 获取成功: {len(xml_str)} 字符")

            # 解析 XML 提取文本
            import re
            import xml.etree.ElementTree as ET

            # 提取所有可见文本节点
            texts = []
            try:
                root = ET.fromstring(xml_str.encode("utf-8"))
                for el in root.iter():
                    text = (el.get("text") or "").strip()
                    if text:
                        texts.append(text)
                    cd = (el.get("content-desc") or "").strip()
                    if cd:
                        texts.append(cd)
            except ET.ParseError:
                # XML 解析失败时用正则兜底提取 text 属性
                texts = re.findall(r'text="([^"]*)"', xml_str)
                texts = [t.strip() for t in texts if t.strip()]

            # 去重但保留顺序
            seen = set()
            unique_texts = []
            for t in texts:
                if t not in seen:
                    seen.add(t)
                    unique_texts.append(t)
            texts = unique_texts

            logger.debug(f"页面文本节点数: {len(texts)}")
            logger.debug(f"文本内容: {texts[:20]}...")

            # ====== 提取结果 ======
            result = {
                "city": "",
                "date": "",
                "price": "",
                "price_index": 0,
                "show_name": "",
                "venue": "",
                "item_url": "",
                "sale_time": "",
            }

            # --- 检测日期 ---
            # 策略：优先全格式 YYYY.MM.DD（4 位年份不会误截取），再降级到 MM.DD
            # 所有 MM.DD 模式加 (?<!\d) 避免从年份数字中误截取（如 2026.07.19 → 6.07）
            date_patterns = [
                # 第1组: YYYY.MM.DD / YYYY/MM/DD（最精确，4位年防止从2026中截取）
                re.compile(r"(\d{4})[./](\d{1,2})[./](\d{1,2})"),
                # 第2组: MM.DD-MM.DD 日期范围
                re.compile(r"(?<!\d)(\d{1,2})\.(\d{1,2})-(\d{1,2})\.(\d{1,2})"),
                # 第3组: 常规 MM.DD / MM/DD
                re.compile(r"(?<!\d)(\d{1,2})[./](\d{1,2})"),
                # 第4组: 中文 MM月DD日
                re.compile(r"(\d{1,2})月(\d{1,2})日"),
            ]
            for t in texts:
                # 排除开票时间文本
                if '开抢' in t or '开售' in t:
                    continue
                # 排除页码/视频进度指示（如 "3/3"、"2/5"），避免误判为日期
                if re.match(r'^\d{1,2}/\d{1,2}$', t):
                    continue
                for pat in date_patterns:
                    m = pat.search(t)
                    if m:
                        groups = m.groups()
                        if len(groups) == 4:
                            # MM.DD-MM.DD 格式，取第一个日期
                            month, day = groups[0], groups[1]
                            month_i, day_i = int(month), int(day)
                            if 1 <= month_i <= 12 and 1 <= day_i <= 31:
                                result["date"] = f"{month.zfill(2)}.{day.zfill(2)}"
                                logger.info(f"检测到日期: {result['date']}")
                                break
                        elif len(groups) == 3:
                            # YYYY.MM.DD 格式，取月.日
                            year, month, day = groups
                            month_i, day_i = int(month), int(day)
                            if 1 <= month_i <= 12 and 1 <= day_i <= 31:
                                result["date"] = f"{month.zfill(2)}.{day.zfill(2)}"
                                logger.info(f"检测到日期 (from full date): {result['date']}")
                                break
                        elif len(groups) == 2:
                            month, day = groups
                            month_i, day_i = int(month), int(day)
                            if 1 <= month_i <= 12 and 1 <= day_i <= 31:
                                result["date"] = f"{month.zfill(2)}.{day.zfill(2)}"
                                logger.info(f"检测到日期: {result['date']}")
                                break
                if result["date"]:
                    break

            # --- 检测城市 ---
            # 方式1: 从演出标题中提取（如 "武汉·许嵩2026「安泊猜想」巡回演唱会 武汉站"）
            # 格式通常是 "城市·演出名" 或 "演出名 城市站"
            city_from_title = None
            for t in texts:
                # 匹配 "城市·" 格式
                m = re.match(r'^([\u4e00-\u9fff]{2,6})·', t)
                if m:
                    city_from_title = m.group(1)
                    break
                # 匹配 "城市站" 结尾
                m = re.search(r'([\u4e00-\u9fff]{2,6})站$', t)
                if m:
                    city_from_title = m.group(1)
                    break

            if city_from_title:
                result["city"] = city_from_title
                logger.info(f"检测到城市 (from title): {result['city']}")
            else:
                # 方式2: 从城市 Tab 列表中提取（兜底）
                KNOWN_CITIES = [
                    "北京", "上海", "广州", "深圳", "天津", "重庆",
                    "杭州", "南京", "苏州", "成都", "武汉", "西安",
                    "长沙", "郑州", "青岛", "大连", "宁波", "厦门",
                    "福州", "合肥", "昆明", "贵阳", "南宁", "海口",
                    "兰州", "西宁", "银川", "乌鲁木齐", "呼和浩特",
                    "拉萨", "哈尔滨", "长春", "沈阳", "石家庄",
                    "太原", "济南", "南昌", "常州", "无锡", "温州",
                    "襄阳", "洛阳", "珠海", "东莞", "佛山", "中山",
                    "惠州", "嘉兴", "绍兴", "台州", "泉州", "漳州",
                    "赣州", "九江", "宜昌", "岳阳", "常德", "株洲",
                    "徐州", "南通", "扬州", "镇江", "泰州", "盐城",
                    "芜湖", "绵阳", "德阳", "遵义", "曲靖", "玉溪",
                    "桂林", "柳州", "三亚", "包头", "鄂尔多斯",
                ]
                # 先找 "XX站" 格式
                for t in texts:
                    if t.endswith("站") and len(t) < 8:
                        for city in KNOWN_CITIES:
                            if city in t:
                                result["city"] = city
                                logger.info(f"检测到城市 (from 站): {result['city']}")
                                break
                    if result["city"]:
                        break
                # 如果没找到，再找纯城市名
                if not result["city"]:
                    for t in texts:
                        for city in KNOWN_CITIES:
                            if city in t and len(t) < 12:
                                result["city"] = city
                                logger.info(f"检测到城市: {result['city']}")
                                break
                        if result["city"]:
                            break

            # --- 检测票价 ---
            # 优先匹配 "¥318-1618" 或 "¥80-880" 格式
            MAX_PRICE = 99999  # 票价上限
            price_range_pattern = re.compile(r'[¥￥]?\s*(\d{2,5})\s*[-~]\s*(\d{2,5})')
            for t in texts:
                # 跳过明显不是票价的文本（含时间、日期关键字）
                if any(kw in t for kw in ('开抢', '开售', '开票', '月', '日', ':')):
                    continue
                m = price_range_pattern.search(t)
                if m:
                    v1, v2 = int(m.group(1)), int(m.group(2))
                    # 价格合理性校验：大麦最低票价一般 80+，排除 08-08 这类错误匹配
                    if 30 <= v1 <= MAX_PRICE and 30 <= v2 <= MAX_PRICE and v1 <= v2:
                        result["price"] = f"{v1}-{v2}"
                        logger.info(f"检测到票价 (range): {result['price']}")
                        break

            # 如果没找到范围，找单个价格
            if not result["price"]:
                price_candidates = []
                for t in texts:
                    # 排除非价格数字（太短或太长）
                    if len(t) > 10:
                        continue
                    # 包含票价关键词或价格数字
                    if '¥' in t or '￥' in t:
                        # 提取数字部分
                        m = re.search(r'[¥￥]\s*(\d+)', t)
                        if m:
                            price_candidates.append(m.group(1))
                    elif re.match(r'^\d{3,5}$', t.strip()):
                        # 纯数字且 3-5 位，可能是票价
                        price_candidates.append(t.strip())

                if price_candidates:
                    # 取第一个作为票价
                    result["price"] = price_candidates[0]
                    logger.info(f"检测到票价: {result['price']}")

            # --- 检测演出名称 ---
            # 标题通常在文本列表的前面，且长度适中
            # 排除日期/城市/按钮文本等
            exclude_keywords = {"元", "¥", "￥", "购买", "开抢", "分享",
                               "收藏", "首页", "搜索", "返回", "登录"}
            for t in texts:
                t_clean = t.strip()
                if (len(t_clean) >= 6 and len(t_clean) <= 60
                        and not any(k in t_clean for k in exclude_keywords)
                        and t_clean != result.get("city", "")
                        and t_clean != result.get("date", "")):
                    # 检查是否是普通按钮文本
                    if not re.match(r"^[^\u4e00-\u9fff]{1,10}$", t_clean):
                        result["show_name"] = t_clean
                        break

            # --- 检测场馆 ---
            venue_keywords = ["体育场", "体育馆", "中心", "剧场", "剧院",
                             "馆", "大舞台", "广场", "会展"]
            for t in texts:
                for kw in venue_keywords:
                    if kw in t and len(t) < 30:
                        result["venue"] = t.strip()
                        break
                if result["venue"]:
                    break

            logger.info(f"页面检测完成: "
                        f"city={result['city']} "
                        f"date={result['date']} "
                        f"price={result['price']}")

            # --- 检测商品链接 (item_url) ---
            # 尝试从页面 XML 全文查找 itemId
            item_id = None
            # 模式1: 查找 itemId=数字
            m = re.search(r'itemId[=:]\s*(\d{5,})', xml_str)
            if m:
                item_id = m.group(1)
            if not item_id:
                # 模式2: 查找 id=数字 (but only if in damai context)
                m = re.search(r'[?&]id[=:](\d{5,})', xml_str)
                if m:
                    item_id = m.group(1)
            if not item_id:
                # 模式3: 从 content-desc 中查找纯数字 item ID (>=6位)
                for t in texts:
                    m = re.search(r'(\d{6,})', t)
                    if m:
                        item_id = m.group(1)
                        break
            if item_id:
                result["item_url"] = f"https://m.damai.cn/damai/home/index.html?itemId={item_id}"
                logger.info(f"检测到商品链接 (itemId={item_id})")

            # --- 检测开票时间 ---
            # 查找 "XX月XX日 HH:MM开抢" 格式的文本
            sale_time_patterns = [
                re.compile(r"(\d{1,2})月(\d{1,2})日?\s*(\d{1,2}):(\d{2})开抢"),
                re.compile(r"(\d{1,2})月(\d{1,2})日?\s*(\d{1,2}):(\d{2})"),
            ]
            for t in texts:
                for pat in sale_time_patterns:
                    m = pat.search(t)
                    if m:
                        result["sale_time"] = m.group(0)
                        logger.info(f"检测到开票时间: {result['sale_time']}")
                        break
                if result["sale_time"]:
                    break

            # 如果没从文本中找到，尝试从 resource-id 查找
            if not result["sale_time"]:
                # 查找 id_project_count_sell_time 节点
                for el in root.iter():
                    rid = (el.get("resource-id") or "").strip()
                    if "count_sell_time" in rid or "sell_time" in rid:
                        text = (el.get("text") or "").strip()
                        if text:
                            result["sale_time"] = text
                            logger.info(f"检测到开票时间 (from rid): {result['sale_time']}")
                            break

            # 通过 activity 判断是否在大麦页面
            if "damai" not in activity.lower() and "damai" not in str(xml_str).lower():
                result["warning"] = "当前页面可能不在大麦 App 内"

            self.detect_result.emit(result)

        except Exception as e:
            logger.exception(f"页面检测异常: {e}")
            self.detect_result.emit({"error": f"页面检测失败: {e}"})

    def _run_ntp_test(self):
        """后台线程：测试 NTP 服务器连通性"""
        server = self._pending_ntp_server
        try:
            logger.info(f"正在测试 NTP 服务器: {server}")
            from src.time_sync import TimeSync
            ts = TimeSync(ntp_server=server)
            offset = ts.sync(retries=2)
            if abs(offset) < 1_000_000:  # 合理偏移范围
                logger.info(f"NTP 测试成功: {server}, offset={offset:.1f}ms")
                self.ntp_test_result.emit(server, offset)
            else:
                logger.warning(f"NTP 偏移异常: {offset:.1f}ms")
                self.ntp_test_result.emit(server, offset)
        except Exception as e:
            logger.error(f"NTP 测试失败: {e}")
            self.ntp_test_result.emit(server, -1)

    def _run_workflow(self):
        """后台线程：运行抢票流程

        新流程:
          1. NTP 校时
          2. 测 RTT 补偿
          3. 等待到开售时间
          4. 点击「立即购票」
          5. 选择票档
          6. 点击「确认」
          7. 结束（支付由用户完成）
        """
        try:
            safety = SafetyGuard(
                probe_only=self._config.probe_only,
                if_commit_order=self._config.if_commit_order,
            )

            logger.info(f"运行模式: {safety.mode.mode_name}")
            logger.info(f"目标演出: city={self._config.city} date={self._config.date}")
            logger.info(f"开售时间: {self._config.start_at}")

            # 检查设备是否已连接
            if self._device is None:
                logger.error("设备未连接")
                self.device_error.emit("设备未连接，请先连接设备")
                self.finished.emit(-1)
                return

            self._machine = PhaseMachine(self._config, self._device, safety)

            # Hook phase changes
            original_set_phase = self._machine.set_phase
            def hooked_set_phase(phase):
                original_set_phase(phase)
                self.phase_changed.emit(phase)
                # 计算进度 (6 个阶段)
                phases_order = ["初始化", "等待开售", "点击购票", "选择票档", "确认订单", "完成"]
                try:
                    idx = phases_order.index(phase)
                    progress = int(idx / len(phases_order) * 100)
                    self.progress_update.emit(progress, phase)
                except ValueError:
                    pass
                if self._abort:
                    raise InterruptedError("用户中止")

            self._machine.set_phase = hooked_set_phase

            final_phase = self._machine.run()
            self.finished.emit(1 if final_phase == "完成" else 0)

        except InterruptedError:
            logger.warning("流程被用户中止")
            self.finished.emit(1)
        except Exception as e:
            logger.exception(f"运行异常: {e}")
            self.finished.emit(0)
        finally:
            self._running = False

    def run(self):
        """QThread 入口 - 在后台线程执行"""
        self._running = True
        self._abort = False
        self._install_log_hook()

        if self._task == "connect":
            self._run_connect()
        elif self._task == "detect":
            self._run_detect()
        elif self._task == "ntp_test":
            self._run_ntp_test()
        else:
            self._run_workflow()

        self._remove_log_hook()
        self._task = ""

