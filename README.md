# 口袋待办 / Pocket Todo

小而完整的原生 Android Todo 测试应用：添加、勾选完成、取消完成、筛选、确认删除、本地持久化。无需登录，不申请网络或其他权限。

## 安装

从本仓库 Releases 下载 `PocketTodo-1.0-debug.apk`，适用于 Android 8.0 及以上。只为你用于下载的浏览器或文件管理器临时允许“安装未知应用”，安装后可关闭。此 APK 使用一次性测试签名，不是应用商店正式版。不同构建的测试签名可能不同，无法覆盖安装时请先备份内容；卸载会清空数据。

## 构建与验证

JDK 17、Gradle 8.9、Android SDK 35 / build-tools 35.0.0；Android Gradle Plugin 8.7.3。无第三方运行时依赖。

```sh
python3 tools/verify.py core
python3 tools/verify.py build
# 仅限一次性的、已启动安卓模拟器；该命令会清空模拟器里的应用数据：
python3 tools/ui_test.py
```

核心纯 Java 测试覆盖新增、空白/长度/容量边界、完成切换、精确删除、Unicode、序列化、损坏输入。Android 构建闸门执行 assembleDebug / lintDebug，并验证签名、包名、最低系统版本、权限及 SHA256。模拟器闸门真实安装 APK、点击界面、强制停止重启并验证持久化，截图来自实际运行。

快闸门与慢闸门分开。CI 报告位于 `evidence` 分支的 `reports/<source-SHA>-<run-ID>.json`，包含退出状态、失败日志尾部、APK 校验与模拟器证据，并在写入后逐字节读回。APK 在构建闸门通过后即可下载，模拟器是否通过须看独立报告，不能仅凭 Release 判断。

## 数据与限制

数据仅保存在应用私有 SharedPreferences 中，每次修改同步提交；保存失败不更新内存列表。最多 500 条，每条最多 200 个 UTF-16 代码单元。读取损坏数据时保留原始内容并禁止覆盖，不静默清空。禁用系统备份，不含云同步、提醒、编辑、导出或正式签名。

本项目验证自动生成 APK 的开发闭环，不宣称完成真机或应用商店验收。手机厂商兼容性、触感、字体放大与个人使用习惯仍需实际体验。
