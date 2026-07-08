"""临时调试：直接 adb shell dumpsys 取 Activity 的开销"""
import time
import subprocess
import uiautomator2 as u2

d = u2.connect("AN2FVB1913005525")

# warm up
for _ in range(2):
    d.shell("dumpsys window | grep mCurrentFocus")

# d.shell dumpsys
t = time.time()
for _ in range(5):
    out = d.shell("dumpsys window | grep mCurrentFocus").output
elapsed_sh = (time.time() - t) * 1000
print(f"d.shell dumpsys 5次: {elapsed_sh:.0f}ms, avg {elapsed_sh/5:.0f}ms/次")
print(f"sample output: {out!r}")

# 比较: d.shell 的简单命令（echo ok）
t = time.time()
for _ in range(5):
    d.shell("echo ok")
elapsed_echo = (time.time() - t) * 1000
print(f"d.shell echo 5次: {elapsed_echo:.0f}ms, avg {elapsed_echo/5:.0f}ms/次")
