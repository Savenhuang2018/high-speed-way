#!/usr/bin/env python3
"""验证 Android WebView 工程结构完整性（不依赖 SDK/网络）"""
import os

PROJ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "android")
ok = 0
def check(name, cond):
    global ok
    print(("  ✓ " if cond else "  ✗ ") + name)
    ok += 1 if cond else 0

def f(*p): return os.path.join(PROJ, *p)

check("settings.gradle 存在", os.path.exists(f("settings.gradle")))
check("build.gradle 存在", os.path.exists(f("build.gradle")))
check("gradle.properties 存在", os.path.exists(f("gradle.properties")))
check("app/build.gradle 存在", os.path.exists(f("app", "build.gradle")))
check("AndroidManifest.xml 存在", os.path.exists(f("app", "src", "main", "AndroidManifest.xml")))
check("MainActivity.java 存在", os.path.exists(f("app", "src", "main", "java", "com", "example", "servicarea", "MainActivity.java")))
check("gradlew 存在且可执行", os.path.exists(f("gradlew")) and os.access(f("gradlew"), os.X_OK))
check("local.properties.example 存在", os.path.exists(f("local.properties.example")))
check("gradle-wrapper.properties 存在", os.path.exists(f("gradle", "wrapper", "gradle-wrapper.properties")))

# 内容检查
with open(f("app", "src", "main", "java", "com", "example", "servicarea", "MainActivity.java")) as fh:
    java = fh.read()
check("MainActivity 加载 WebView", "WebView" in java and "loadUrl" in java)
check("MainActivity 含定位权限请求", "ACCESS_FINE_LOCATION" in java)
check("MainActivity 含返回键处理", "onBackPressed" in java and "canGoBack" in java)

with open(f("app", "src", "main", "AndroidManifest.xml")) as fh:
    manifest = fh.read()
check("Manifest 声明网络权限", "android.permission.INTERNET" in manifest)
check("Manifest 声明定位权限", "ACCESS_FINE_LOCATION" in manifest)
check("Manifest 含启动Activity", "MAIN" in manifest and "LAUNCHER" in manifest)
check("Manifest 允许cleartext(本地http)", "usesCleartextTraffic=\"true\"" in manifest)

print(f"\n结果: {ok} 通过, {17-ok} 失败")
