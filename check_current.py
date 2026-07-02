import uiautomator2 as u2
import re
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

d = u2.connect()
import time
time.sleep(2)

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
    rid = rid_m.group(1) if rid_m else ""
    text = text_m.group(1) if text_m else ""
    cls = class_m.group(1) if class_m else ""
    coords = re.search(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
    if coords:
        x1, y1, x2, y2 = int(coords.group(1)), int(coords.group(2)), int(coords.group(3)), int(coords.group(4))
        cx, cy = (x1+x2)//2, (y1+y2)//2
        clickables.append({'mid': f'({cx},{cy})', 'rid': rid.replace('cn.damai:id/', ''), 'text': text[:30], 'class': cls})

for c in clickables:
    print(f"  {c['mid']:15s} rid={c['rid']:30s} text='{c['text']}' class={c['class']}")

# 底部栏
buy_m = re.search(r'resource-id="cn\.damai\:id/btn_buy_view"[^>]*clickable="([^"]*)"[^>]*bounds="(\[\d+,\d+\]\[\d+,\d+\])"', xml, re.IGNORECASE)
print(f"\nbtn_buy_view: clickable={buy_m.group(1) if buy_m else 'N/A'} bounds={buy_m.group(2) if buy_m else 'N/A'}")

# 价格
price_m = re.search(r'resource-id="cn\.damai\:id/tv_price"[^>]*text="([^"]*)"', xml, re.IGNORECASE)
print(f"tv_price: '{price_m.group(1) if price_m else 'N/A'}'")

# 标签
print("\n=== 标签 ===")
for m in re.finditer(r'resource-id="cn\.damai\:id/tv_tag"[^>]*text="([^"]*)"[^>]*bounds="(\[\d+,\d+\]\[\d+,\d+\])"', xml, re.IGNORECASE):
    text = m.group(1)
    bounds = m.group(2)
    coords = re.search(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
    if coords:
        x1, y1, x2, y2 = int(coords.group(1)), int(coords.group(2)), int(coords.group(3)), int(coords.group(4))
        print(f"  tag='{text}' mid=({(x1+x2)//2},{(y1+y2)//2})")

# 所有 FrameLayout 在票档区
print("\n=== 票档区 FrameLayout ===")
flow_idx = xml.find('project_detail_perform_price_flowlayout')
if flow_idx >= 0:
    chunk = xml[flow_idx:flow_idx+2000]
    for m in re.finditer(r'<node\b([^>]*class="android\.widget\.FrameLayout"[^>]*)bounds="(\[\d+,\d+\]\[\d+,\d+\])"([^>]*)>', chunk, re.IGNORECASE):
        attrs = m.group(1) + m.group(3)
        bounds = m.group(2)
        clickable_m = re.search(r'clickable="([^"]*)"', attrs, re.IGNORECASE)
        clickable = clickable_m.group(1) if clickable_m else ""
        coords = re.search(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
        if coords:
            x1, y1, x2, y2 = int(coords.group(1)), int(coords.group(2)), int(coords.group(3)), int(coords.group(4))
            print(f"  mid=({(x1+x2)//2},{(y1+y2)//2}) clickable={clickable}")
