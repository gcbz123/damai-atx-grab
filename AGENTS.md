# Damai ATX Grab — AGENTS.md

## 项目概览

大麦网抢票工具，通过 **uiautomator2（ATX）** 连接 Android 真机，自动化抢票流程。
双入口：CLI（`src/main.py`）和 GUI（`src/main_gui.py`，PyQt6）。

## 快速命令

```bat
:: 环境检查
python -m src.main --check-env

:: CLI 抢票（3 种模式）
python -m src.main                    -- 探测模式（默认，不点击购票）
python -m src.main --no-probe-only     -- 演练模式（走到确认页不提交）
python -m src.main --commit            -- 实战模式（走到付款页）
python -m src.main --config xxx.jsonc  -- 指定配置文件
python -m src.main --udid 序列号       -- 指定 adb 设备

:: GUI
python -m src.main_gui

:: 测试（不需要真机，纯单元测试）
pytest -v
pytest tests/test_sprint.py -v   -- 单个文件
pytest -k "test_parse" -v        -- 关键词匹配

:: 批处理快捷入口
scripts\check_env.bat     -- 环境检查
scripts\start_grab.bat    -- CLI 交互式启动
scripts\start_gui.bat     -- GUI 启动
```

**必须用 `-m` 模块方式运行**，不能用 `python src/main.py`（会破坏 `src` 包的 import path）。

## 关键架构

```
src/
├── main.py              CLI 入口（argparse）
├── main_gui.py          GUI 入口（PyQt6）
├── config_loader.py     JSONC 配置加载（支持 // 注释）
├── phase_machine.py     抢票状态机：INIT→WAIT→BUY→SELECT_PRICE→CONFIRM→DONE
├── sprint.py            极速冲刺引擎（盲点点击 + Activity 检测跳转）
├── time_sync.py         NTP 校时 + CPU 自旋毫秒级定时
├── coord_blind.py       坐标盲点点击器（预热记录坐标，冲刺直接 click）
├── element_locator.py   uiautomator2 XPath 元素定位封装
├── safety_guard.py      三段式安全守卫（探测/演练/实战）
├── image_fallback.py    AirTest 图像模板匹配兜底（airtest 可选依赖）
├── logger.py            loguru 日志管理（控制台 + 文件 + 错误分离）
├── damai_share_parser.py  大麦分享链接解析（requests + BeautifulSoup）
├── actions/             操作模块（城市/搜索/日期/票价/观演人）
│   ├── search_show.py   自动导航（URL 跳转 or 搜索关键词）
│   ├── select_city.py   切换城市
│   ├── select_date.py   选择日期
│   ├── select_price.py  选择票档
│   └── select_viewers.py 选择观演人
├── gui/
│   ├── app.py           PyQt6 主界面（ConfigPanel + LogPanel + MainWindow）
│   ├── worker.py        QThread 后台线程（连接/检测/抢票）
│   └── fetcher.py       大麦分享链接抓取器（纯 urllib，无需 requests/bs4）
tests/
├── test_sprint.py              冲刺引擎单元测试
├── test_time_sync.py           NTP 校时单元测试
├── test_coord_blind.py         盲点点击器测试
├── test_damai_share_parser.py  分享链接解析器测试
├── test_config_loader.py       配置加载测试
```

### 运行模式（`safety_guard.py`）

| probe_only | if_commit_order | 模式 | 行为 |
|---|---|---|---|
| true | — | 探测 | 仅检测环境，不点购票 |
| false | false | 演练 | 走到确认页，停在「提交」前 |
| false | true | 实战 | 全程自动到付款页 |

### 抢票流程

NTP 校时 → 测 RTT → CPU 自旋等到开售 → 盲点点击「立即购票」→ 选票档 → 点击确认 → 用户手动支付

### 两个网页解析器

`src/gui/fetcher.py` — 无外部依赖（纯 `urllib`），从大麦分享链接抓取 __NUXT__/__INITIAL_STATE__ JSON 提取信息。
`src/damai_share_parser.py` — 用 `requests` + `BeautifulSoup`，从 HTML 的 `#staticDataDefault` 提取。

GUI 用 `fetcher.py`，分享链接处理用 `damai_share_parser.py`。改解析逻辑需要对两个都改或合并。

## 配置（config.jsonc）

JSONC 格式（支持 `//` 注释和尾逗号）。关键字段：

```jsonc
{
  "udid": "AN2FVB1913005525",  // adb 序列号，留空自动选第一个
  "item_url": "https://...",   // 商品链接（优先级高于 keyword）
  "keyword": "演出名称",        // 搜索关键词（item_url 为空时用）
  "city": "襄阳",
  "date": "08.01",             // MM.DD
  "price": "380",
  "price_index": 1,            // 票价列表索引（从 1 开始）
  "users": ["谢晖"],           // 观演人列表
  "if_commit_order": false,
  "probe_only": true,
  "start_at": "2026-07-01 20:00:00",
  "sprint_interval_ms": 50,    // 冲刺点击间隔
  "sprint_max_retries": 60,    // 最大重试次数
}
```

其他可选字段：`app_package`、`app_activity`、`auto_navigate`、`warmup_sec`、`ntp_server`、`log_level`、`log_dir`、`perform_index`。

⚠️ `price_index` 从 **1** 开始（用户输入），内部转 0-based：`target_idx = price_index - 1`。`perform_index` 同理（0=不指定，默认第1场）。
- **选择票档逻辑** (`phase_machine.py`): 两阶段多策略混合定位。
  **阶段 0 — u2 API 直接查找**（优先可靠）:
  - a) 找 resource-id 含 `perform_price` / `price_item` / `price_flowlayout` 的容器内的 clickable 子元素
  - b) 按文本含票价关键字（¥/￥/元/看台/内场/VIP/套票）的 clickable 元素
  - c) 按 resource-id 含 price/ticket 的 clickable 元素（Y 过滤 + 最小宽度过滤）
  **阶段 1 — XML 解析兜底**（`_find_via_xml`）:
  - a) 文本匹配（¥/￥/元 + 纯数字 3-5位），加宽度和 Y 过滤
  - b) resource-id 含 price/ticket，加宽度和 Y 过滤，候选 ≤20 个才采纳
  - c) Y 行分组（20px 精度桶，取 ≥2 个元素的桶作为票价行）
  **最终降级**: 硬编码坐标（覆盖 6 个位置）。索引超出时自动取最后一个。
  **关键改进**: 阶段 0 的 u2 API 方法避免 XML 解析的文本编码问题，使用 `d(textContains=..., clickable=True)` 原生选择器，更可靠。

## ⚠️ 已知坑点

### 日期/价格检测 (`worker.py`)
- **YYYY.MM.DD 优先**: 正则必须优先匹配 4 位年格式（防止 `2026.07.19` 中的 `6.07` 被误匹配）
- **price 正则过滤**: `¥80-880` 范围匹配后需要做值域校验（`>=30`, `<=99999`, `v1<=v2`），防止 `08-08` 等误匹配
- **跳过 `3/3`**: 纯数字斜杠文本（如页码 `3/3`、`2/5`）需排除，避免被当做日期 `3.3`
- 所有 MM.DD 模式加 `(?<!\d)` 前缀

### countdown 切换泄漏 (`app.py`)
- `_on_detect_result()` **必须先** 调 `self._config_panel.stop_countdown()` 清除旧倒计时，再判断是否启动新倒计时
- 切到无开票时间的页面时，旧倒计时必须清零

### 调试脚本（根目录）
大量 `check_*.py` / `dump_*.py` / `test_*.py` 是临时调试脚本，不在 `pyproject.toml` 中，**不是项目正式代码**。修改前先确认文件是否在 `src/` 下。

### Git 代理
全局 git 配置将 `https://github.com/` 重定向到 `https://ghproxy.net/https://github.com/`（ghproxy 有时不可达）。push 失败时需临时解除：
```
git config --global --unset url.https://ghproxy.net/https://github.com/.insteadof
```

### 代码风格
- 2 空格缩进
- 变量名 camelCase
- 代码注释中文（保留代码/命令/标识符原文）
- 创建脚本用 `.bat`/`.cmd`，不用 `.ps1`
- python 3.11+, dependencies in `pyproject.toml`
