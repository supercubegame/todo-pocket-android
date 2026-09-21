# 口袋待办 v1.2 开发中

**尚无可交付 v1.2 APK。** 目前在验证 Android 数据库和文件保存，仍非完整产品；界面继承自 v1.1，设备契约不启动它，不代表 UI 已验收。

[v1.1 原发布页](https://github.com/supercubegame/todo-pocket-android/releases/tag/preview-35575804413-1) · [v1.2 草稿 PR](https://github.com/supercubegame/todo-pocket-android/pull/4)。旧包/main/PR #3 未改，不承诺覆盖升级。

## 已实现范围

领域规则包括分类/应用关联、自定义字段、精确金额账本、打卡日历、有序图文引用。文件层有旧备份普通待办预览、按摘要保存/去重/校验、带清单与展开预算的 ZIP 容器及新目录暂存。

Android SQLiteOpenHelper 数据库 v1 使用系统 SQLite、事务、外键和 WAL，保存分类改名/顺序、应用与活动、路径/标签、账本及批次重试/撤销记录、打卡日期与录入时间、笔记顺序/隐私标志/媒体登记。最新未修改批次才可撤销，撤销后旧请求不能复活；未知高版本拒绝打开而不删库。后续结构变更必须添加显式迁移，尚无成功迁移链。

## 验证命令

快速：`python3 tools/verify.py v12`，真实 JDK17 运行原54、领域82、文件49项。

设备：`gradle --no-daemon --console=plain assembleDebug assembleDebugAndroidTest lintDebug`，再在 GitHub 隔离 runner 中 `TEST_API=26 python3 tools/emulator_gate.py`，另一档为34。Android8/14，独立包 `com.supercubegame.pockettodo.v12.preview`，1.2/code3，min26/target34，固定 desugar_jdk_libs2.1.5。

先行 d7b3714e7aa84aa54cdbee7e6db9b23833d0e677 / [35612488818](https://github.com/supercubegame/todo-pocket-android/actions/runs/35612488818) 真实编译/lint/安装后，两档均因缺少 AppDatabase 失败。实现 8ca2b733ee937a9952bc2481bdefe1c2d8dd2f05 / [35613201820](https://github.com/supercubegame/todo-pocket-android/actions/runs/35613201820) 两档通过前29项后，均在媒体硬链接创建处被系统拒绝。这是实际兼容缺陷，不能用 JVM 文件检查通过代替 Android 验证。

修复为同目录原子重命名，使用持久化 OS 文件锁加 JVM 锁；锁内确认目标不存在，不覆盖已有文件。仅供协作的应用私有写入者，不能直接用于其他应用可写目录；SAF 必须从已验证私有快照复制。没有改成不安全覆盖，也没有跳过测试。设备测试补并发仓库实例、重复媒体和备份不覆盖的字节级检查。最新是否通过以相同 SHA 的完整 evidence 报告为准。

设备 seed/reopen 是两次独立 instrumentation，中间强停并确认进程不存在，检查已提交数据和撤销日志。**不代表写入中杀进程或设备断电验证。** 合成媒体是字节夹具，不证明图片解码。登记媒体不代表文件/尺寸/格式已验证。

交付入口 `python3 tools/verify.py build` 仍故意阻断，保留旧原因字符串供保护断言使用；这不表示单独的内部 Android 编译未执行。CI 只上传日志/结果，不上传 APK/不创建 Release。报告 `ui.devices` 存设备结果；`ui.status=NOT_TESTED` 表示没有 UI 验收，`release_ready=false`。

## 仍待完成

数据库自定义字段/字段笔记、普通待办、应用快捷关联、计划/模板/搜索；旧备份事务迁入；数据库/媒体完整备份恢复；原生 Today/Activities/Calendar/NoteEditor 界面；图片选择/解码/缩略图/裁剪遮挡；PDF/分段图片/Markdown+assets 分享；真实 UI 自动验收、截图与真机试用。

当前账本汇总会加载全账本，规模优化未完成。备份元数据/状态8MiB上限是暂定防护，不是容量实测；媒体按显式字节预算处理。原子重命名加文件同步不等于断电耐久性保证。ZIP 的 state.bin 尚未接数据库语义校验，容器通过不等于完整恢复。旧备份只预览，尚未写入数据库。

备份不加密，摘要不证明作者；分享过滤不是截图遮挡，最终不得带入未遮挡原图。无云同步、自动打卡或付费服务。长期签名需用户可信本地生成备份并配置，私钥不得进入聊天/代码/日志；debug 不是长期升级通道。

批准32文件与完整计划：[docs/V1_2_PLAN.md](docs/V1_2_PLAN.md)。
