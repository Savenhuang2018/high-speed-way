#!/usr/bin/env python3
"""从远程 high-speed-way 仓库克隆并验证最新代码"""
import os
import subprocess
import sys
import tempfile

tmpdir = tempfile.mkdtemp(prefix="hsw_verify2_")

def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)

clone = run(["git", "clone", "-q", "git@github.com:Savenhuang2018/high-speed-way.git", tmpdir])
print("clone exit:", clone.returncode)
if clone.returncode != 0:
    print(clone.stderr[:300]); sys.exit(1)

log = run(["git", "-C", tmpdir, "log", "--oneline", "-1"])
print("最新提交:", log.stdout.strip())

# 关键文件存在
import os
files = ["server.py", "static/index.html", "static/admin.html", "docs/market-research.md", "test_stdlib.py"]
for f in files:
    print(("  ✓ " if os.path.exists(os.path.join(tmpdir, f)) else "  ✗ ") + f)

# 跑测试
test = run([sys.executable, "test_stdlib.py"], cwd=tmpdir, timeout=90)
ok = "33 通过, 0 失败" in test.stdout
print("远程代码测试通过:", ok, "| exit:", test.returncode)

run(["rm", "-rf", tmpdir])
sys.exit(0 if ok else 1)
