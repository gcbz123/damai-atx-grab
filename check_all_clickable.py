import uiautomator2 as u2
import xml.etree.ElementTree as ET
import re
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

d = u2.connect()
import time
time.sleep(2)

xml = d.dump_hierarchy()

# 用正则匹配所有 clickable 节点（兼容单双引号）
print("=== 所有 clickable 节点 ===")
clickable_pattern = re.compile(r'<node\b([^>]*clickable="true"[^>]*)bounds="(\[\d+,\d+\]\[\d+,\d+\])"([^>]*)>', re.IGNORECASE)
for m in clickable_pattern.finditer(xml):
    attrs = m.group(1) + m.group(3)
    bounds = m.group(2)
    rid_m = re.search(r'resource-id="([^"]*)"', attrs, re.IGNORECASE)
    text_m = re.search(r'text="([^"]*)"', attrs, re.IGNORECASE)
    class_m = re.search(r'class="([^"]*)"', attrs, re.IGNORECASE)
    desc_m = re.search(r'content-desc="([^"]*)"', attrs, re.IGNORECASE)
    rid = rid_m.group(1) if rid_m else ""
    text = text_m.group(1) if text_m else ""
    cls = class_m.group(1) if class_m else ""
    desc = desc_m.group(1) if desc_m else ""
    coords = re.search(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
    if coords:
        x1, y1, x2, y2 = int(coords.group(1)), int(coords.group(2)), int(coords.group(3)), int(coords.group(4))
        cx, cy = (x1+x2)//2, (y1+y2)//2
        rid_short = rid.replace('cn.damai:id/', '') if rid else ''
        print(f"  mid=({cx},{cy}) rid='{rid_short}' text='{text}' desc='{desc}' class={cls}")

# 打印底部栏完整结构
print("\n=== 底部栏完整结构 ===")
bottom_pattern = re.compile(r'<node\b[^>]*resource-id="cn\.damai\:id/bottom_layout"[^>]*/?>', xml)
# 找到 bottom_layout 的起始位置
bm = re.search(r'<node\b[^>]*resource-id="cn\.damai\:id/bottom_layout"', xml, re.IGNORECASE)
if bm:
    start = bm.start()
    # 向后找 3000 字符
    chunk = xml[start:start+3000]
    print(chunk)
