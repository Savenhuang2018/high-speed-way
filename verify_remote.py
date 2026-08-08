#!/usr/bin/env python3
"""从远程 high-speed-way 仓库克隆并验证最新代码"""
import os
import subprocess
import sys
import tempfile

tmpdir = tempfile.mkdtemp(prefix="hsw_verify_")
print(f"克隆到: {tmpdir}")

def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)

# 1. 克隆远程仓库
clone = run(["git", "clone", "-q", "git@github.com:Savenhuang2018/high-speed-way.git", tmpdir])
print("clone exit:", clone.returncode, clone.stderr.strip()[:200])
if clone.returncode != 0:
    sys.exit(1)

# 2. 最新提交
log = run(["git", "-C", tmpdir, "log", "--oneline", "-1"])
print("最新提交:", log.stdout.strip())

# 3. 跑测试
test = run([sys.executable, "test_stdlib.py"], cwd=tmpdir, timeout=60)
print(test.stdout)
ok = "0 失败" in test.stdout and "27 通过" in test.stdout
print("远程代码测试通过:", ok)

# 清理
run(["rm", "-rf", tmpdir])
sys.exit(0 if ok else 1)
