# Android WebView 包装 APK 工程

把高速服务区 Web 应用打包为原生 Android APK（WebView 外壳）。

## 前提条件（需在能访问 dl.google.com 的网络下）
- JDK 17
- Android SDK（含 platform-tools / build-tools / platform android-34）
- Android Gradle Plugin 环境

## 快速开始
1. 将本目录拷贝到能访问 dl.google.com 的机器
2. 配置 SDK 路径（见 local.properties）
3. 运行：
   ```bash
   ./gradlew assembleDebug
   ```
4. 产物：`app/build/outputs/apk/debug/app-debug.apk`

## 说明
- `MainActivity` 用 WebView 加载 Web 应用
- 支持定位（需要权限）、返回键、加载进度
- 网络权限已声明
- 应用名：高速服务区

## 目录
- `app/src/main/java/com/example/servicarea/MainActivity.java` — 主 Activity
- `app/src/main/AndroidManifest.xml` — 清单（权限、Activity）
- `app/build.gradle` — 模块构建脚本
- `build.gradle` — 顶层构建脚本
- `settings.gradle` — 工程设置
- `gradle.properties` — Gradle 配置
- `local.properties.example` — SDK 路径模板
