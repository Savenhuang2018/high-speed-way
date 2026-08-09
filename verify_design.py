#!/usr/bin/env python3
"""验证首页视觉升级：token 系统 + 无残留旧变量 + 功能完整"""
import urllib.request

BASE = "http://127.0.0.1:8123"
html = urllib.request.urlopen(BASE + "/index.html").read().decode()

ok = 0
def check(name, cond):
    global ok
    print(("  ✓ " if cond else "  ✗ ") + name)
    ok += 1 if cond else 0

# 新 token 体系存在
check("brand token", "--brand: #ff6b35" in html)
check("文本层级 token", "--text-primary" in html and "--text-secondary" in html and "--text-tertiary" in html)
check("表面层级 token", "--surface-canvas" in html and "--surface-card" in html and "--surface-inset" in html)
check("边框层级 token", "--border-default" in html and "--border-subtle" in html and "--border-strong" in html)
check("阴影 token", "--shadow-1" in html and "--shadow-2" in html)
check("动效 token", "--ease" in html and "--dur" in html)
check("间距 token", "--space-1" in html and "--space-6" in html)

# 无残留旧变量
for old in ["var(--primary)", "var(--ink)", "var(--card)", "var(--line)", "var(--radius)"]:
    check(f"无残留 {old}", old not in html)
# 无残留硬编码颜色
for old in ["color:#999", "color:#666", "color:#e85d2f", "background:#f0f0f0", "background:#fafafa"]:
    check(f"无残留 {old}", old not in html)

# 功能 JS 完整
for fn in ["function loadRoute", "function doSearch", "function switchNav",
           "function toggleFavorite", "function loadFavorites", "function loadMine",
           "function openArea", "function showMerchant", "function submitReview"]:
    check(f"JS {fn}", fn in html)

print(f"\n结果: {ok} 通过, {22-ok} 失败")
