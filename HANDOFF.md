# 口袋待办：当前接续入口

2026-10-14 19:41继续轮。单分支一个写入者；新账号独立授权GitHub，不假定继承技能、记忆或沙箱。不是完整交付、新APK或发布声明。

## 最新候选

[be26b103](https://github.com/supercubegame/todo-pocket-android/commit/be26b10321ce46d6d9808b9e8fb9f7b6cbfde860)，[运行38558758574](https://github.com/supercubegame/todo-pocket-android/actions/runs/38558758574)，push、attempt1；最后观察原后端主机验证执行中，尚无完整候选主机或双API结论。

现有分支 `ci/shortcut-storage-preflight-4d8742`，只修改 `.github/workflows/shortcut-storage.yml`。工作流11195字节，blob `a1847d0f255df5089593c897634fb298537325e7`，SHA256 `bdacbbf0e6e0e75356f23d05146b46b2400ccd3d05fc794ba00cb1b27304c0b4`，本地、写入返回、独立不可变目录读回一致。通过固定历史载荷物化六文件候选，不是产品分支提交。

第一步读取本运行所有作业及完整分片回执，核对六文件身份和原21命令一次/300秒，随后实际API26/API34构建、原113契约、八项默认启动和十项激活UI检查、最终报告。缺失/跳过不是通过；原失败保留，不用不变重跑掩盖，不用旧绿灯接受新提交。

产品最近核验仍 `3a5a17e1fdc570c73804007cd9a4d2ef36c0966b`，本轮产品推送0；手机仍4d8742阶段预览。没有新APK、合并、发布、新凭据或手机操作。

## 本轮已修的首个阻塞

[e8原运行38554785947](https://github.com/supercubegame/todo-pocket-android/actions/runs/38554785947)已失败，不再pending。此前解析器组合修复已实际通过：组合4正向/36遗漏/3变异、native 4正向/32负向、activation 4正向/36负向、8+10 Java调用遗漏检查、12行为/3变异均通过。

随后host21的全源码Java编译碰到缺失的Android声明替身：AlertDialog、ActivityMonitor和addMonitor。不是解析器故障复发，不是已证实的实际Android产品编译失败。host21一次/300秒，38.24010874499993秒，退出1，无超时，设备被跳过。

[完整stdout/stderr](https://github.com/supercubegame/todo-pocket-android/runs/115825115065)，[候选身份及完整8940字节集成日志](https://github.com/supercubegame/todo-pocket-android/runs/115825119343)，原归档11890171667。stdout3617字节/SHA256 `0c6629a48daa0eb20a167b01214f16570079e56082a74cf36bf4a2a06e00005c`，stderr2928字节/SHA256 `81dac9477023a3251d8b3f82b3baf493125c67dfebc538674e3b3bf663173a7d`。原运行没有重跑或取消。

be26最小补齐声明替身：AlertDialog.getWindow，Instrumentation.ActivityResult/ActivityMonitor及addMonitor、waitForMonitorWithTimeout、removeMonitor。保留原全源码编译入口、全部旧自测和预算，新增原缺声明RED、全源码GREEN、四个方法逐一遗漏反例。没有用替身宣称Android行为通过，没有修改本轮应用运行代码。本地实际JDK小探针的原RED/GREEN/四遗漏通过，工作流实际嵌套变换和输出片段逐字验证通过；完整候选结果仍须本次CI。

## 等待CI时推进的准备工作，尚未接入CI

[本轮增量交接包](https://u300734028.p.clickup-attachments.com/u300734028/e7aafd27-64ee-5391-84f5-21e352c9e2fd/PocketTodo-be26b103-handoff.zip?view=open)：34份源码、检查点和日志加哈希清单，不是完整仓库或APK。包含确切已提交工作流与历史依赖片段；应用UI原片段仍由不可变工作流补IOException声明，勿直接把原片段覆盖仓库。

activation-async-gate.py：实际work/close成员体配合明确Activity、DB、widget替身，CountDownLatch控制6种排队/退出时序，3个变异有正常见证并被精确断言拒绝。覆盖准备前关闭、准备完成后回调前关闭、finishing、可见同意失效、确认执行前关闭、提交后回调前关闭。不是Android旋转或真实数据库并发证明；下一步嵌入现有verifier并从实际候选抽取成员，随后补设备生命周期场景。

activation-snapshot-reader.py及test：激活UI数据库独立只读复核原型，按实际设备cells格式解码18旧表全部类型、列名和rowid，再独立读SQLite，要求schema4、19表、空快捷关系及旧单元格精确一致。实际Java编码器体产生NULL、64位整数、中文/emoji和二进制对照，真实主机SQLite正例+16负例通过，原库字节不变。尚未连接android采集和最终report，不能算设备证据。下一步每phase采集schema4-activation-ui.db/WAL及activation-ui-expected.bin，绑定预算/身份，报告端独立重读并补整个采集/回放被删的反例。

## 产品行为与剩余顺序

已实现的候选UI：用户显式入口、已验证备份预览、内部备份随卸载/清数据丢失的警告、勾选后确认、取消及过期回调保护，普通启动不自动迁移。成功重建整个Activity、弃用schema3旧facade；失败明确格式可能已变化，不能谎称未变化。新增固定进程内schema4-activation-ui.db路由，不接收Intent任意路径、不打开手机库。真实十项新UI检查尚未通过。

先收口新候选完整主机/双API，补实际旋转/快速退出/确认中销毁和报告独立回放；然后同最终产品提交的稳定签名覆盖升级、AGENTS/CLAUDE一致更新、产品工作流、原子非强制产品提交与逐字读回；验收后才给新APK。再处理剩余功能、真实照片/EXIF/输入法/大字体、性能、存储失败、易用性及商业签名分发。没有可靠总完成百分比。

[87d3旧基线](https://github.com/supercubegame/todo-pocket-android/actions/runs/38539002887)六作业成功，包括实际双API构建和设备测试，但不含新激活UI，不能代替当前验收。[前一检查点](https://github.com/supercubegame/todo-pocket-android/blob/872e6b6e40f16c127a30c540464faa71baf2ea24/HANDOFF.md)保留解析器晚绑定RED/GREEN、de8失败、cbbc转义和媒体异常签名修复历史。

沿用10月11日18:34原十一文件授权，[授权及21命令](https://github.com/supercubegame/todo-pocket-android/blob/9a6c72f8c67e2ae3520398833dc1ace7bcfcddf4/HANDOFF.md)。只用现有凭据；失败关闭，不清数据、不卸载、不启动外部应用、不操作手机、不合并发布。ADB255/ANR根因仍未证实，三字节媒体不证明真实照片兼容。

永久重建依赖不可变工作流，不依赖14天Actions归档或当前账号沙箱。对话结束不代表助手继续开发。
