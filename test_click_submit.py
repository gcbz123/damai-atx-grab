import uiautomator2 as u2
import re
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

d = u2.connect()
import time

print("=== 点击 btn_buy_view 坐标 (841, 2250) ===")
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

print(f"\nClickable nodes after click: {len(clickables)}")
for c in clickables:
    print(f"  {c['mid']:15s} rid={c['rid']:30s} text='{c['text']}' class={c['class']}")

# 底部栏
buy_m = re.search(r'resource-id="cn\.damai\:id/btn_buy_view"[^>]*bounds="(\[\d+,\d+\]\[\d+,\d+\])"', xml, re.IGNORECASE)
print(f"\nbtn_buy_view: {buy_m.group(1) if buy_m else 'NOT FOUND'}")

submit_m = re.search(r'submit_order_btn', xml, re.IGNORECASE)
print(f"submit_order_btn: {'FOUND' if submit_m else 'NOT FOUND'}")

# 查找所有包含"提交"或"确认"或"购买"的 text
print("\n=== 包含提交/确认/购买文本的节点 ===")
for m in re.finditer(r'<node\b([^>]*text="([^"]*(?:提交|确认|购买|预订|下单)[^"]*)"[^>]*)>', xml, re.IGNORECASE):
    text = m.group(2)
    rid_m = re.search(r'resource-id="([^"]*)"', m.group(0), re.IGNORECASE)
    bounds_m = re.search(r'bounds="(\[\d+,\d+\]\[\d+,\d+\])"', m.group(0), re.IGNORECASE)
    rid = rid_m.group(1) if rid_m else ""
    bounds = bounds_m.group(1) if bounds_m else ""
    print(f"  text='{text}' rid='{rid}' bounds='{bounds}'")

# 也检查 TextView 的 text 属性
print("\n=== 所有有 text 的节点 ===")
for m in re.finditer(r'<node\b([^>]*text="([^"]+)"[^>]*)bounds="(\[\d+,\d+\]\[\d+,\d+\])"', xml, re.IGNORECASE):
    attrs = m.group(1)
    text = m.group(2)
    bounds = m.group(3)
    rid_m = re.search(r'resource-id="([^"]*)"', attrs, re.IGNORECASE)
    rid = rid_m.group(1) if rid_m else ""
    if 'cn.damai' in rid and len(text.strip()) > 0:
        coords = re.search(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
        if coords:
            x1, y1, x2, y2 = int(coords.group(1)), int(coords.group(2)), int(coords.group(3)), int(coords.group(4))
            print(f"  text='{text.strip()[:40]}' mid=({(x1+x2)//2},{(y1+y2)//2}) rid='{rid.replace('cn.damai:id/', '')}'")
