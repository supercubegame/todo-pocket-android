# 口袋待办 v1.2 开发中

**尚无可交付 v1.2 APK。** 已接入内部 Android 数据库测试，仍非完整产品；界面仍是继承的 v1.1 Activity，设备契约不启动它，也不代表 UI 验收。

已发布 v1.1 预览：[原发布页](https://github.com/supercubegame/todo-pocket-android/releases/tag/preview-35575804413-1)。旧包、main 与 PR #3 未改，本分支不提供覆盖升级承诺。[v1.2 草稿 PR](https://github.com/supercubegame/todo-pocket-android/pull/4)。

## 当前实现

领域层：分类/应用关联、自定义字段、精确金额账本、打卡日历、有序图文引用。文件层：旧备份普通待办预览、内容摘要文件保存/去重/校验、带清单和展开预算的 ZIP 传输及全新暂存。

新增 Android SQLiteOpenHelper 数据库 v1（系统 SQLite，无额外数据库依赖）：分类改名/顺序、应用/活动关联、路径/标签、账本及批次重试和撤销日志、打卡日期/真实录入时间、笔记有序块/隐私标志/媒体登记。写入启用事务和外键；后续写入使旧撤销失效，已撤销批次不可悄悄重放。未知高版本拒绝打开，绝不删库重建。没有成功迁移链，后续改结构必须补显式迁移测试。

## 验证入口

快速验证：`python3 tools/verify.py v12`，需要真实 JDK17，执行原54、领域82、文件49项。新鲜编译目录，真实文件操作，非 Python 模拟业务。

设备验证：`gradle --no-daemon --console=plain assembleDebug assembleDebugAndroidTest lintDebug`，再在 GitHub 隔离 runner 上 `TEST_API=26 python3 tools/emulator_gate.py` 或 API34。系统矩阵为 Android8/14，测试独立包 `com.supercubegame.pockettodo.v12.preview`，1.2/code3、min26/target34。编译启用固定 desugar_jdk_libs2.1.5。

测试先行提交 d7b3714e7aa84aa54cdbee7e6db9b23833d0e677 / [运行35612488818](https://github.com/supercubegame/todo-pocket-android/actions/runs/35612488818) 已实际完成编译/lint/安装，两档设备均在独立包和 API 守卫后因缺少 AppDatabase 失败。随后才推送数据库实现。当前是否通过须看相同 SHA 的完整 evidence 报告，不继承上一提交结果。

设备测试含 seed 和 reopen 两次 instrumentation，中间强停并确认进程不存在，检查提交后的数据和撤销日志持久化；**不是写入中杀进程，也不是设备断电测试**。文件夹具只是合成字节，不证明照片可解码。媒体登记只验证元数据，不代表文件/图片验证已完成。

`python3 tools/verify.py build` 仍故意拒绝产品交付；保留的旧错误字符串只供保护断言使用，并非内部构建未执行。CI 仅上传日志/结果，不上传 APK，不创建 Release。报告 `ui.devices` 承载矩阵设备结果，`ui.status=NOT_TESTED` 指没有 UI 验收；总 `release_ready=false`。

## 仍待完成

数据库接入自定义字段/字段笔记、普通待办、应用快捷关联、计划/模板/搜索；旧备份事务迁入；数据库/媒体完整备份恢复；原生 Today/Activities/Calendar/NoteEditor 界面；图片选择/解码/缩略图/裁剪遮挡；PDF/分段图片/Markdown+assets 分享；真实 UI 自动验收、截图与真机试用。

当前账本汇总复用精确领域计算，会把账本加载到内存，规模优化尚未完成。8MiB 备份元数据/状态限制为暂定内存防护，不是手机容量实测；媒体按调用方字节预算处理。原子建硬链接和文件同步不等于断电耐久性保证。

ZIP 中 state.bin 仍是待数据库适配器解释的数据，容器通过不等于业务关系完整恢复。旧备份预览尚未写入数据库。备份不加密，摘要仅检测损坏、不证明作者。分享过滤不是截图遮挡，最终导出不得混入未遮挡原图。

长期签名需用户可信本地生成备份与配置，私钥不得进入聊天、代码或日志。debug 签名不是长期升级通道。无云同步、自动打卡、付费服务。

批准32文件及完整计划：[docs/V1_2_PLAN.md](docs/V1_2_PLAN.md)。
