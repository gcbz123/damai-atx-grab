import uiautomator2 as u2
import re
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

d = u2.connect()
import time

# 先长按选中票档
print("=== 长按 (236, 1066) ===")
d.long_click(236, 1066, 0.5)
time.sleep(1)

xml = d.dump_hierarchy()

# 找到第一个票档 FrameLayout 的完整结构
# 先找 project_detail_perform_price_flowlayout
flow_idx = xml.find('project_detail_perform_price_flowlayout')
if flow_idx >= 0:
    print("\n=== 票档 flowlayout 完整结构 ===")
    print(xml[flow_idx:flow_idx+3000])

# 也找 ll_perform_item 结构
ll_idx = xml.find('ll_perform_item')
if ll_idx >= 0:
    print("\n=== ll_perform_item 完整结构 ===")
    print(xml[ll_idx:ll_idx+1000])

# 检查底部栏
print("\n=== 底部栏 ===")
bottom_idx = xml.find('bottom_layout')
if bottom_idx >= 0:
    print(xml[bottom_idx:bottom_idx+2000])

# 检查价格
print("\n=== 价格 ===")
price_m = re.search(r'resource-id="cn\.damai\:id/tv_price"[^>]*text="([^"]*)"', xml, re.IGNORECASE)
if price_m:
    print(f"tv_price: '{price_m.group(1)}'")

# 检查 ticket 区域
ticket_idx = xml.find('discount_ticket')
if ticket_idx >= 0:
    print(f"\n=== discount_ticket 区域 ===")
    print(xml[ticket_idx:ticket_idx+500])
