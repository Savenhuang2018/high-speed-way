#!/usr/bin/env python3
"""下载 gradle 发行版并提取 gradle-wrapper.jar 到工程（services.gradle.org 可达）"""
import os
import shutil
import subprocess
import sys
import urllib.request

DIST = "https://services.gradle.org/distributions/gradle-8.5-bin.zip"
ZIP = "/tmp/gradle-8.5-bin.zip"
OUT = os.path.expanduser("~/service-area-dianping/android/gradle/wrapper/gradle-wrapper.jar")

if os.path.exists(OUT):
    print("gradle-wrapper.jar 已存在")
    sys.exit(0)

print("下载 gradle 8.5 (services.gradle.org)...")
r = subprocess.run(["curl", "-sL", "--max-time", "900", "-o", ZIP, DIST])
if r.returncode != 0:
    print("下载失败 rc=", r.returncode)
    sys.exit(1)
print(f"下载完成: {os.path.getsize(ZIP)/1024/1024:.1f} MB")

import zipfile
print("解压提取 wrapper jar...")
os.makedirs(os.path.dirname(OUT), exist_ok=True)
found = False
with zipfile.ZipFile(ZIP, "r") as z:
    for name in z.namelist():
        if name.endswith("gradle-wrapper.jar"):
            with z.open(name) as src, open(OUT, "wb") as dst:
                shutil.copyfileobj(src, dst)
            found = True
            break
os.remove(ZIP)
if found:
    print("gradle-wrapper.jar 已写入:", OUT, os.path.getsize(OUT), "bytes")
else:
    print("zip 内未找到 gradle-wrapper.jar")
    sys.exit(1)
