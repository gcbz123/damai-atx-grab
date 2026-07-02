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
        rid_short = rid.replace('cn.damai:id/', '')
        print(f"  mid=({cx},{cy}) rid='{rid_short}' text='{text[:30]}' class={cls}")

# 底部栏
print("\n=== 底部栏 ===")
buy_m = re.search(r'resource-id="cn\.damai\:id/btn_buy_view"[^>]*clickable="([^"]*)"[^>]*bounds="(\[\d+,\d+\]\[\d+,\d+\])"', xml, re.IGNORECASE)
if buy_m:
    print(f"btn_buy_view: clickable={buy_m.group(1)} bounds={buy_m.group(2)}")
else:
    print("btn_buy_view: NOT FOUND")

price_m = re.search(r'resource-id="cn\.damai\:id/tv_price"[^>]*text="([^"]*)"', xml, re.IGNORECASE)
print(f"tv_price: '{price_m.group(1) if price_m else 'N/A'}'")

# 查找所有 text 节点
print("\n=== 所有有 text 的大麦节点 ===")
for m in re.finditer(r'<node\b([^>]*resource-id="cn\.damai[^"]*"[^>]*)text="([^"]*)"[^>]*bounds="(\[\d+,\d+\]\[\d+,\d+\])"', xml, re.IGNORECASE):
    attrs = m.group(1)
    text = m.group(2)
    bounds = m.group(3)
    rid_m = re.search(r'resource-id="([^"]*)"', attrs, re.IGNORECASE)
    clickable_m = re.search(r'clickable="([^"]*)"', attrs, re.IGNORECASE)
    rid = rid_m.group(1) if rid_m else ""
    clickable = clickable_m.group(1) if clickable_m else ""
    rid_short = rid.replace('cn.damai:id/', '')
    coords = re.search(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
    mid = f'({(int(coords.group(1))+int(coords.group(3)))//2},{(int(coords.group(2))+int(coords.group(4)))//2})' if coords else ''
    print(f"  {rid_short:30s} text='{text}' mid={mid} clickable={clickable}")

# 检查 layout_price 是否存在
print("\n=== layout_price ===")
lp_idx = xml.find('layout_price"')
if lp_idx >= 0:
    print(xml[lp_idx:lp_idx+500])
else:
    print("NOT FOUND")

# 检查 project_detail_perform_price_flowlayout
print("\n=== price_flowlayout ===")
pf_idx = xml.find('project_detail_perform_price_flowlayout')
if pf_idx >= 0:
    print("FOUND")
else:
    print("NOT FOUND")

# 检查 project_detail_perform_flowlayout
print("\n=== perform_flowlayout ===")
pfl_idx = xml.find('project_detail_perform_flowlayout')
if pfl_idx >= 0:
    print("FOUND")
else:
    print("NOT FOUND")
