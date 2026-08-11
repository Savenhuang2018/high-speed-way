#!/usr/bin/env python3
"""列出 Adoptium JDK17 mac 资产，并下载解压正确的 mac x64 jdk"""
import json
import os
import subprocess
import sys
import tarfile

api = "https://api.github.com/repos/adoptium/temurin17-binaries/releases/latest"
r = subprocess.run(["curl", "-sL", "--max-time", "40", api], capture_output=True)
data = json.loads(r.stdout.decode())
assets = data.get("assets", [])

# 列出所有 mac jdk tar.gz（注意排除 jre/jre 类：'OpenJDK17U-jre...' 含 'jdk' 子串）
candidates = [a["browser_download_url"] for a in assets
              if "jdk_" in a["name"].lower()
              and "jre" not in a["name"].lower()
              and a["name"].endswith(".tar.gz")
              and "mac" in a["name"].lower()
              and "debugimage" not in a["name"].lower()]
print("mac jdk 候选:")
for u in candidates:
    print("  ", u.split("/")[-1])

# 优先 x64 mac（本机是 Intel mac，arch 显示 x86_64）
url = None
for u in candidates:
    if "x64_mac" in u or "mac_x64" in u:
        url = u
        break
if not url and candidates:
    url = candidates[0]
if not url:
    print("无可用 mac jdk")
    sys.exit(1)
print("选择:", url.split("/")[-1])

tmp = "/tmp/temurin17.tar.gz"
r = subprocess.run(["curl", "-sL", "--max-time", "600", "-o", tmp, url], capture_output=True)
if r.returncode != 0:
    print("下载失败 rc=", r.returncode, r.stderr.decode()[:200])
    sys.exit(1)
print(f"下载完成: {os.path.getsize(tmp)/1024/1024:.1f} MB")

dest_dir = os.path.expanduser("~/java")
os.makedirs(dest_dir, exist_ok=True)
with tarfile.open(tmp, "r:gz") as t:
    t.extractall(dest_dir)
os.remove(tmp)

jdk = None
for d in os.listdir(dest_dir):
    if "jdk" in d.lower():
        jdk = os.path.join(dest_dir, d)
        break
if not jdk:
    print("未找到 jdk 目录:", os.listdir(dest_dir))
    sys.exit(1)
java_bin = os.path.join(jdk, "Contents", "Home", "bin", "java")
if not os.path.exists(java_bin):
    java_bin = os.path.join(jdk, "bin", "java")
print("JDK:", jdk)
out = subprocess.run([java_bin, "-version"], capture_output=True, text=True)
print("版本:", (out.stderr or out.stdout).strip().splitlines()[0])
with open(os.path.expanduser("~/java/jdk_path.txt"), "w") as f:
    f.write(jdk)
print("jdk_path 已保存")
