import uiautomator2 as u2
import re
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

d = u2.connect()
import time
time.sleep(3)

xml = d.dump_hierarchy()

# 所有 clickable
print("=== 所有 clickable ===")
clickables = []
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
        clickables.append({'mid': f'({cx},{cy})', 'rid': rid.replace('cn.damai:id/', ''), 'text': text[:30], 'desc': desc[:30], 'class': cls})

for c in clickables:
    print(f"  {c['mid']:15s} rid={c['rid']:30s} text='{c['text']}' desc='{c['desc']}' class={c['class']}")

# 底部栏状态
buy_m = re.search(r'resource-id="cn\.damai\:id/btn_buy_view"[^>]*clickable="([^"]*)"[^>]*bounds="(\[\d+,\d+\]\[\d+,\d+\])"', xml, re.IGNORECASE)
print(f"\nbtn_buy_view: clickable={buy_m.group(1) if buy_m else 'N/A'} bounds={buy_m.group(1) if buy_m else 'N/A'}")

# 底部栏完整结构
bottom_idx = xml.find('bottom_layout"')
if bottom_idx >= 0:
    chunk = xml[bottom_idx:bottom_idx+3000]
    print("\n=== 底部栏结构 ===")
    for m in re.finditer(r'<node\b([^>]*resource-id="([^"]*)"[^>]*)bounds="(\[\d+,\d+\]\[\d+,\d+\])"[^>]*>', chunk, re.IGNORECASE):
        attrs = m.group(1)
        rid = m.group(2)
        bounds = m.group(3)
        clickable_m = re.search(r'clickable="([^"]*)"', attrs, re.IGNORECASE)
        text_m = re.search(r'text="([^"]*)"', attrs, re.IGNORECASE)
        class_m = re.search(r'class="([^"]*)"', attrs, re.IGNORECASE)
        clickable = clickable_m.group(1) if clickable_m else ""
        text = text_m.group(1) if text_m else ""
        cls = class_m.group(1) if class_m else ""
        rid_short = rid.replace('cn.damai:id/', '') if rid else ""
        coords = re.search(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
        mid = f'({(int(coords.group(1))+int(coords.group(3)))//2},{(int(coords.group(2))+int(coords.group(4)))//2})' if coords else ''
        print(f"  {rid_short:35s} text='{text[:20]}' bounds={bounds} mid={mid} clickable={clickable} class={cls}")

# 票档区域
print("\n=== 票档区域 ===")
flow_idx = xml.find('project_detail_perform_price_flowlayout')
if flow_idx >= 0:
    chunk = xml[flow_idx:flow_idx+2000]
    for m in re.finditer(r'<node\b([^>]*class="android\.widget\.FrameLayout"[^>]*)bounds="(\[\d+,\d+\]\[\d+,\d+\])"[^>]*>', chunk, re.IGNORECASE):
        attrs = m.group(1)
        bounds = m.group(2)
        clickable_m = re.search(r'clickable="([^"]*)"', attrs, re.IGNORECASE)
        clickable = clickable_m.group(1) if clickable_m else ""
        coords = re.search(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
        if coords:
            x1, y1, x2, y2 = int(coords.group(1)), int(coords.group(2)), int(coords.group(3)), int(coords.group(4))
            print(f"  mid=({(x1+x2)//2},{(y1+y2)//2}) clickable={clickable}")

# 价格
price_m = re.search(r'resource-id="cn\.damai\:id/tv_price"[^>]*text="([^"]*)"', xml, re.IGNORECASE)
print(f"\ntv_price: '{price_m.group(1) if price_m else 'N/A'}'")

# 标签
print("\n=== 标签 ===")
for m in re.finditer(r'resource-id="cn\.damai\:id/tv_tag"[^>]*text="([^"]*)"[^>]*bounds="(\[\d+,\d+\]\[\d+,\d+\])"', xml, re.IGNORECASE):
    text = m.group(1)
    bounds = m.group(2)
    coords = re.search(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
    if coords:
        x1, y1, x2, y2 = int(coords.group(1)), int(coords.group(2)), int(coords.group(3)), int(coords.group(4))
        print(f"  tag='{text}' mid=({(x1+x2)//2},{(y1+y2)//2})")

# 页面标题
print("\n=== 页面信息 ===")
title_m = re.search(r'resource-id="cn\.damai\:id/tv_title"[^>]*text="([^"]*)"', xml, re.IGNORECASE)
desc_m = re.search(r'resource-id="cn\.damai\:id/tv_desc"[^>]*text="([^"]*)"', xml, re.IGNORECASE)
if title_m:
    print(f"Title: {title_m.group(1)}")
if desc_m:
    print(f"Desc: {desc_m.group(1)}")
