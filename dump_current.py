import uiautomator2 as u2
import re
import xml.etree.ElementTree as ET

import sys
import io

# 修复 stdout 编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

d = u2.connect()
import time
time.sleep(2)

xml = d.dump_hierarchy()

# 写完整 XML
with open(r"C:\Users\Administrator\AppData\Local\Temp\opencode\current_dump.xml", "w", encoding="utf-8") as f:
    f.write(xml)

# 提取关键词节点
keywords = ["price", "buy", "submit", "order", "ticket", "sku", "btn_", "layout_", "bottom", "confirm", "pay"]

print("=" * 80)
print("=== 关键词节点 ===")
print("=" * 80)

for kw in keywords:
    # 在 XML 中搜索包含该关键词的 resource-id 或 text 属性
    pattern = rf'<node[^>]*(?:resource-id|text)="[^"]*{kw}[^"]*"[^>]*/?>'
    matches = re.findall(pattern, xml, re.IGNORECASE)
    if matches:
        print(f"\n--- 包含 '{kw}' 的节点 ---")
        for m in matches[:10]:  # 每个关键词最多 10 个
            # 简化输出
            rid_m = re.search(r'resource-id="([^"]*)"', m)
            text_m = re.search(r'text="([^"]*)"', m)
            bounds_m = re.search(r'bounds="(\[\d+,\d+\]\[\d+,\d+\])"', m)
            
            rid = rid_m.group(1) if rid_m else ""
            text = text_m.group(1) if text_m else ""
            bounds = bounds_m.group(1) if bounds_m else ""
            
            if rid or text:
                print(f"  rid={rid}, text={text}, bounds={bounds}")

# 提取底部栏 clickable 节点
print("\n" + "=" * 80)
print("=== 底部栏 clickable 节点 ===")
print("=" * 80)

# 找到 bottom_layout 区域
bottom_pattern = re.compile(r'<node[^>]*resource-id="cn\.damai:id/bottom_layout"[^>]*>.*?</node>', re.DOTALL)
bm = bottom_pattern.search(xml)
if bm:
    bottom_section = bm.group(0)
    # 提取所有 clickable 节点 - 更宽松的匹配
    clickable_pattern = re.compile(r'<node([^>]*clickable="true"[^>]*)bounds="(\[[\d,]+\])"([^>]*)>')
    for m in clickable_pattern.finditer(bottom_section):
        attrs = m.group(1) + m.group(3)
        bounds = m.group(2)
        rid_m = re.search(r'resource-id="([^"]*)"', attrs)
        text_m = re.search(r'text="([^"]*)"', attrs)
        rid = rid_m.group(1) if rid_m else ""
        text = text_m.group(1) if text_m else ""
        print(f"  clickable bounds={bounds}, rid={rid}, text={text}")
else:
    print("未找到 bottom_layout")

# 也打印所有 bounds 在底部的 clickable 节点（不限 resource-id）
print("\n=== 所有 bounds y>2000 的 clickable 节点 ===")
for m in re.finditer(r'<node([^>]*)bounds="(\[[\d,]+\])"([^>]*)>', xml):
    attrs = m.group(1) + m.group(3)
    bounds = m.group(2)
    if "clickable=\"true\"" in attrs:
        coords = re.search(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
        if coords:
            y1 = int(coords.group(2))
            if y1 > 2000:
                rid_m = re.search(r'resource-id="([^"]*)"', attrs)
                text_m = re.search(r'text="([^"]*)"', attrs)
                class_m = re.search(r'class="([^"]*)"', attrs)
                rid = rid_m.group(1) if rid_m else ""
                text = text_m.group(1) if text_m else ""
                cls = class_m.group(1) if class_m else ""
                print(f"  y>{y1} bounds={bounds} rid={rid} text='{text}' class={cls}")
