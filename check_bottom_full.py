import uiautomator2 as u2
import re
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

d = u2.connect()
import time

# 长按票档
d.long_click(236, 1066, 0.5)
time.sleep(1)

xml = d.dump_hierarchy()

# 底部栏完整结构
bottom_idx = xml.find('bottom_layout')
if bottom_idx >= 0:
    print(xml[bottom_idx:bottom_idx+4000])

# 检查 btn_buy_view
buy_m = re.search(r'<node\b([^>]*resource-id="cn\.damai\:id/btn_buy_view"[^>]*)bounds="(\[\d+,\d+\]\[\d+,\d+\])"[^>]*clickable="([^"]*)"', xml, re.IGNORECASE)
if buy_m:
    print(f"\nbtn_buy_view: attrs={buy_m.group(1)[:100]} bounds={buy_m.group(2)} clickable={buy_m.group(3)}")

# 查找所有包含 buy/submit 的节点
print("\n=== 所有 buy/submit 相关节点 ===")
for m in re.finditer(r'<node\b([^>]*resource-id="[^"]*(?:buy|submit|order|checkout|purchase)[^"]*"[^>]*)bounds="(\[\d+,\d+\]\[\d+,\d+\])"[^>]*>', xml, re.IGNORECASE):
    full = m.group(0)
    clickable_m = re.search(r'clickable="([^"]*)"', full, re.IGNORECASE)
    text_m = re.search(r'text="([^"]*)"', full, re.IGNORECASE)
    class_m = re.search(r'class="([^"]*)"', full, re.IGNORECASE)
    clickable = clickable_m.group(1) if clickable_m else ""
    text = text_m.group(1) if text_m else ""
    cls = class_m.group(1) if class_m else ""
    rid_m = re.search(r'resource-id="([^"]*)"', full, re.IGNORECASE)
    rid = rid_m.group(1).replace('cn.damai:id/', '') if rid_m else ""
    print(f"  rid={rid} bounds={m.group(2)} clickable={clickable} text='{text}' class={cls}")

# 查找 layout_num 区域
print("\n=== layout_num 区域 ===")
num_idx = xml.find('layout_num"')
if num_idx >= 0:
    print(xml[num_idx:num_idx+2000])
