#!/usr/bin/env python3
"""验证美化的运营后台页面"""
import urllib.request

BASE = "http://127.0.0.1:8123"
html = urllib.request.urlopen(BASE + "/admin").read().decode()

ok = 0
def check(name, cond):
    global ok
    print(("  ✓ " if cond else "  ✗ ") + name)
    ok += 1 if cond else 0

check("页面可访问", bool(html))
check("侧边栏品牌存在", "High-Speed-Way Admin" in html)
check("侧边导航含5项", all(x in html for x in ["数据看板","点评审核","商户管理","全部点评","服务区"]))
check("渐变统计卡片", "accent" in html and "c-blue" in html)
check("业态分布条形图", "category-bars" in html)
check("差评预警板块", "low-rating" in html)
check("顶部栏面包屑", "crumbs" in html)
check("头像组件", "avatar" in html)
check("新徽章样式", "badge-blue" in html and "badge-red" in html)
check("响应式隐藏侧栏", "@media" in html and "display: none" in html)

print(f"\n结果: {ok} 通过, {10-ok} 失败")
