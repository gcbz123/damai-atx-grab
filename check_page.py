import uiautomator2 as u2
import re
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

d = u2.connect()
import time
time.sleep(2)

xml = d.dump_hierarchy()

# 提取所有 clickable 节点
print("=== 所有 clickable 节点 ===")
for m in re.finditer(r'<node\b([^>]*clickable="true"[^>]*)bounds="(\[\d+,\d+\]\[\d+,\d+\])"([^>]*)>', xml, re.IGNORECASE):
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

# 提取所有包含 price/ticket/perform 的节点
print("\n=== 票档/票价相关节点 ===")
for m in re.finditer(r'<node\b([^>]*)bounds="(\[\d+,\d+\]\[\d+,\d+\])"([^>]*)>', xml, re.IGNORECASE):
    attrs = m.group(1) + m.group(3)
    bounds = m.group(2)
    rid_m = re.search(r'resource-id="([^"]*)"', attrs, re.IGNORECASE)
    text_m = re.search(r'text="([^"]*)"', attrs, re.IGNORECASE)
    class_m = re.search(r'class="([^"]*)"', attrs, re.IGNORECASE)
    rid = rid_m.group(1) if rid_m else ""
    text = text_m.group(1) if text_m else ""
    cls = class_m.group(1) if class_m else ""
    
    if any(kw in (rid + text).lower() for kw in ['price', 'ticket', 'perform', 'sku', 'discount']):
        rid_short = rid.replace('cn.damai:id/', '') if rid else ''
        text_short = text.strip()[:30] if text else ''
        coords = re.search(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
        mid = ''
        if coords:
            x1, y1, x2, y2 = int(coords.group(1)), int(coords.group(2)), int(coords.group(3)), int(coords.group(4))
            mid = f' mid=({(x1+x2)//2},{(y1+y2)//2})'
        clickable = 'clickable=true' if 'clickable="true"' in attrs else ''
        print(f"  rid='{rid_short}' text='{text_short}' bounds={bounds}{mid} {clickable} class={cls}")

# 标题
print("\n=== 页面标题 ===")
for m in re.finditer(r'<node\b([^>]*)bounds="(\[\d+,\d+\]\[\d+,\d+\])"([^>]*)>', xml, re.IGNORECASE):
    attrs = m.group(1) + m.group(3)
    text_m = re.search(r'text="([^"]*)"', attrs, re.IGNORECASE)
    rid_m = re.search(r'resource-id="([^"]*)"', attrs, re.IGNORECASE)
    text = text_m.group(1) if text_m else ""
    rid = rid_m.group(1) if rid_m else ""
    if 'tv_title' in rid or 'tv_desc' in rid:
        text_short = text.strip()[:50] if text else ''
        print(f"  {rid}: '{text_short}'")
