import uiautomator2 as u2
import re
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

d = u2.connect()
import time
time.sleep(2)

xml = d.dump_hierarchy()

# 打印前 2000 字符看看是什么页面
print("=== XML 前 2000 字符 ===")
print(xml[:2000])

# 统计 package
packages = set()
for m in re.finditer(r'package="([^"]*)"', xml):
    packages.add(m.group(1))
print(f"\n=== Packages: {packages} ===")

# 统计 clickable
clickable_count = xml.count('clickable="true"')
print(f"Clickable nodes: {clickable_count}")

# 所有 resource-id
rids = set()
for m in re.finditer(r'resource-id="([^"]*)"', xml):
    rid = m.group(1)
    if rid:
        rids.add(rid)
print(f"\n=== Resource IDs ({len(rids)}) ===")
for r in sorted(rids):
    print(f"  {r}")
