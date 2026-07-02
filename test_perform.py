import uiautomator2 as u2
import re
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

d = u2.connect()
import time

# 模拟完整流程
print("=== 1. 点击第1场 (540, 751) ===")
d.long_click(540, 751, 0.5)
time.sleep(1)

xml = d.dump_hierarchy()
flow_idx = xml.find('project_detail_perform_price_flowlayout')
print(f"price_flowlayout: {'FOUND' if flow_idx >= 0 else 'NOT FOUND'}")

buy_m = re.search(r'resource-id="cn\.damai\:id/btn_buy_view"[^>]*clickable="([^"]*)"', xml, re.IGNORECASE)
print(f"btn_buy_view clickable: {buy_m.group(1) if buy_m else 'N/A'}")

# 检查 layout_price
lp_idx = xml.find('layout_price"')
print(f"layout_price: {'FOUND' if lp_idx >= 0 else 'NOT FOUND'}")

# 检查所有 clickable
print("\n=== 点击场次后 clickable ===")
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

# 如果还是没有票档区，试试点第2场
if flow_idx < 0:
    print("\n=== 2. 点击第2场 (540, 922) ===")
    d.long_click(540, 922, 0.5)
    time.sleep(1)
    
    xml2 = d.dump_hierarchy()
    flow_idx2 = xml2.find('project_detail_perform_price_flowlayout')
    print(f"price_flowlayout: {'FOUND' if flow_idx2 >= 0 else 'NOT FOUND'}")
    
    buy_m2 = re.search(r'resource-id="cn\.damai\:id/btn_buy_view"[^>]*clickable="([^"]*)"', xml2, re.IGNORECASE)
    print(f"btn_buy_view clickable: {buy_m2.group(1) if buy_m2 else 'N/A'}")
    
    print("\n=== 点击第2场后 clickable ===")
    for m in re.finditer(r'<node\b([^>]*clickable="true"[^>]*)bounds="(\[\d+,\d+\]\[\d+,\d+\])"([^>]*)>', xml2, re.IGNORECASE):
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
            rid_short = rid.replace('cn.damai:id/', '')
            print(f"  mid=({cx},{cy}) rid='{rid_short}' text='{text[:30]}' class={cls}")
