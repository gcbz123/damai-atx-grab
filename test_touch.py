import uiautomator2 as u2
import re
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

d = u2.connect()
import time

# 方案1: 用 u2 的 click（已经试过不行）
print("=== 尝试 d.click(236, 1066) ===")
d.click(236, 1066)
time.sleep(1)

xml = d.dump_hierarchy()
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
        clickables.append({'mid': f'({(x1+x2)//2},{(y1+y2)//2})', 'rid': rid.replace('cn.damai:id/', ''), 'text': text[:30], 'class': cls})

print(f"Clickable: {len(clickables)}")
for c in clickables:
    print(f"  {c['mid']:15s} rid={c['rid']:30s} text='{c['text']}'")

# 查看底部栏价格
price_m = re.search(r'resource-id="cn\.damai\:id/tv_price"[^>]*text="([^"]*)"', xml, re.IGNORECASE)
if price_m:
    print(f"Price text: '{price_m.group(1)}'")

# 方案2: 用 shell input tap
print("\n=== 尝试 shell input tap 236 1066 ===")
d.shell(f"input tap 236 1066")
time.sleep(1)

xml2 = d.dump_hierarchy()
clickables2 = []
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
        clickables2.append({'mid': f'({(x1+x2)//2},{(y1+y2)//2})', 'rid': rid.replace('cn.damai:id/', ''), 'text': text[:30], 'class': cls})

print(f"Clickable: {len(clickables2)}")
for c in clickables2:
    print(f"  {c['mid']:15s} rid={c['rid']:30s} text='{c['text']}'")

price_m2 = re.search(r'resource-id="cn\.damai\:id/tv_price"[^>]*text="([^"]*)"', xml2, re.IGNORECASE)
if price_m2:
    print(f"Price text: '{price_m2.group(1)}'")

# 底部栏购买按钮
buy_m = re.search(r'resource-id="cn\.damai\:id/btn_buy_view"[^>]*bounds="(\[\d+,\d+\]\[\d+,\d+\])"', xml2, re.IGNORECASE)
print(f"\nbtn_buy_view: {buy_m.group(1) if buy_m else 'NOT FOUND'}")
