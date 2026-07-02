import uiautomator2 as u2
import re
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

d = u2.connect()
import time

print("=== 点击 btn_buy_view (841, 2250) ===")
d.click(841, 2250)
time.sleep(2)

xml = d.dump_hierarchy()

# 所有 clickable
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
        clickables.append({
            'mid': f'({(x1+x2)//2},{(y1+y2)//2})',
            'rid': rid.replace('cn.damai:id/', ''),
            'text': text[:30],
            'class': cls
        })

print(f"\nClickable after submit click: {len(clickables)}")
for c in clickables:
    print(f"  {c['mid']:15s} rid={c['rid']:30s} text='{c['text']}' class={c['class']}")

# 查看底部栏
buy_m = re.search(r'resource-id="cn\.damai\:id/btn_buy_view"[^>]*bounds="(\[\d+,\d+\]\[\d+,\d+\])"', xml, re.IGNORECASE)
print(f"\nbtn_buy_view: {buy_m.group(1) if buy_m else 'NOT FOUND'}")

# 查看页面标题
title_m = re.search(r'resource-id="cn\.damai\:id/tv_title"[^>]*text="([^"]*)"', xml, re.IGNORECASE)
if title_m:
    print(f"Title: {title_m.group(1)}")

# 查看是否有 confirm/submit 相关节点
for kw in ['submit', 'confirm', 'order_btn', 'checkout', 'buy_now', 'place_order']:
    if kw.lower() in xml.lower():
        print(f"Found keyword: {kw}")

# 查看所有 resource-id
rids = set()
for m in re.finditer(r'resource-id="([^"]*)"', xml):
    rid = m.group(1)
    if rid and 'cn.damai' in rid:
        rids.add(rid.replace('cn.damai:id/', ''))

print(f"\n=== Resource IDs ({len(rids)}) ===")
for r in sorted(rids):
    print(f"  {r}")
