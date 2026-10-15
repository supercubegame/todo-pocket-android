# 口袋待办：当前接续入口

2026-10-15 08:46继续轮。单分支一个写入者；新账号独立授权GitHub，不假定继承技能、记忆或沙箱。不是产品交付、新APK或发布声明。

## 第一件事：读取05fc真实生命周期候选自己的首轮结果

[05fc58b7提交](https://github.com/supercubegame/todo-pocket-android/commit/05fc58b7c50b243efa0bd72ffeb5d022de2b4f78)，[CI38663135001](https://github.com/supercubegame/todo-pocket-android/actions/runs/38663135001)，push、attempt1、run48。最近读取时正在执行前置后端主机检查，尚无本候选完整主机或双API结论，不能沿用e9bf绿灯。

隔离分支ci/shortcut-storage-preflight-4d8742，仅提交既有.github/workflows/shortcut-storage.yml。19865字节，blob2aec5d5f36de30b37dcba31431f2ed876ccf38c6，SHA256c0924779257ec9ebf34ecfd436cdb00a520a6f95a53e421abe5619cf7dc8a472。本地、写入响应、独立不可变远端目录读取身份一致。无待处理安全确认。

新候选materialize修改既有Schema4DeviceTest.java和verify_shortcuts.py，不修改产品运行Java。实际Android测试在已完成备份预览且已勾选同意、尚未确认时依次执行：反向屏幕方向引起的真实Activity替换、显式recreate、finish退出；每次确认旧Activity销毁、旧启动和screen执行器退出，保留旧确认按钮并调用其监听器，断言schema3完整历史和备份原字节不变。旋转还检查真实orientation改变，不能把普通重建叫旋转。随后重新打开继续全部原检查。新增标签前缀ACTIVATION_LIFE_PASS，seed精确三项，reopen无新增项，完整原始流经现有回写保留。

范围限定为已完成preview的旋转/重建/退出。尚未证明正在prepare、正在commit、或回调排队期间销毁；不是进程杀死、稳定覆盖升级或手机验收。实际Android结果还未返回，不能称这三场景已通过。

本地原无生命周期日志红灯已复现；新解析器4正例18精确反例、整族省略见证通过；实际JDK Java AST三断言及三个整体断言省略变异、实际seed调用及整段调用注释变异通过。旧UI序列化4/56、组合4/36加两旁路和一晚绑定变异、旧两层解析器、旧激活十断言AST仍通过。此为真实Python/JDK解析与明确旧日志夹具替身，不是完整checkout或Android编译/执行。

工作流恢复不可变e9bf全部30个run脚本，host18/device6/report6逐字核对，保留每个GitHub步骤边界、环境传递、原命令/预算/失败。只在集成前追加有SHA绑定的生命周期材料；materializer和设备源码均有精确逆向还原断言。原21主机命令每项300秒、一次执行不变。

## e9bf已完整验收，不再pending

[e9bf提交](https://github.com/supercubegame/todo-pocket-android/commit/e9bf430691bda02f4b5dbd2c7cf960c88cc2f6f9)，[CI38627964450](https://github.com/supercubegame/todo-pocket-android/actions/runs/38627964450)八作业/检查全部通过。主机116071872013、API26 116075870280、API34 116075870321、汇总116078006883。全21命令均一次、300秒预算、return0、无超时；host21耗时69.119621789秒，stdout8806字节/SHA2566615c7634b4ea2fade135a52e4ad7091f05fabb451c30409000f4490a139a053/blob3da0a2d908c79e09dde2b7ae31299eae2b50ccb7，stderr空，host artifact11925366534。

[完整主机回执上半](https://github.com/supercubegame/todo-pocket-android/runs/116075836032)、[下半](https://github.com/supercubegame/todo-pocket-android/runs/116075845450)已完整拼接读取。[API26完整证据](https://github.com/supercubegame/todo-pocket-android/runs/116078111640)、[API34完整证据](https://github.com/supercubegame/todo-pocket-android/runs/116078121024)中的完整JSON、seed/reopen原始流、双库独立回放均已读取；外层GitHub app尾部截断不影响完整output.text。未独立下载host ZIP或逐字读取host21 stdout，不假称已读其完整内容。

本轮DeviceTest71981字节/blob97c73143771f1cbfa8dabdc724f0564016604f67/SHA2561d284817f769f6e844562ab569ad521a512c7b9a815ed8ffcf8d16334559442b。verifier233394字节/blob48f95cfd30aaede2a753787b4b5e9f49714886e2/SHA2564f7ce216abc5da350594f2b3348f15f12439aa4a5557c19bff7ac452c7da5f28；双API证据绑定同一摘要。其余四份候选源码与e484相同。

每端旧标签seed97/reopen16，原生启动6/2，激活8/2。原生启动schema4-startup-ui.db各phase184320字节；API26 SHA256e556c4545d894267d1a698f9f6cfb0f08cf43c9a222c3f0f6b6d2bbf2288bee8，API34 ca00fdb4f54981a1b72e38c6aae8ae233dc9e11c78faf3c1306fe19ecf291b3f；各端seed/reopen相同。oracle2771字节/SHA25696d8cad444e96b47fd854cd31b0ea60ee371578b7aed5f63e130e58c9c3f712d；18旧表汇总a670d8086e51e17d9e382d2fead7f2684f9cce91daf96c7d7c23b0139ff1455a，schema4，关系精确[[7,10],[8,10]]。

激活库各phase184320字节；API26 SHA2567b0ebf79503655dfb7e03cea316d478041add7dcc7241c9f139bd84c8dacff01，API34 8f82278047ebf2008cc5673b21f8820f5201d43ec89374af8f876fcf599e3dcd；各端seed/reopen相同。oracle2735字节/SHA25684a8073b8831cd7a71015b447ac2db712878962834afdaa73e60667bfa98cbb4；18旧表汇总92d1a6d935f75c43fed428c091ede652ef884dd2b9d80a538e099f4d3afce23b，schema4，空快捷关系。物理DB在API间不同并非逻辑历史不同；本次停止快照未登记WAL，WAL单独真实主机SQLite对照不能说成设备WAL。

e9bf修复的是设备测试三处screen引用主线程归属，不是已证明的运行时竞态。其本地实际Java线程三场景、三运行变异及两调用点变异的边界保持不变，不等于真实旋转。

## 历史证据不丢失

[此前完整交接](https://github.com/supercubegame/todo-pocket-android/blob/b2bbe165e47cb674a65f1e2303985b4a0c6580bb/HANDOFF.md)保留e484双库验收、cc06报告修复、e9bf实现细节。该文e9bf pending已由本记录更新。

[c91首失败](https://github.com/supercubegame/todo-pocket-android/runs/116022420171)及[原命令流](https://github.com/supercubegame/todo-pocket-android/runs/116022412292)仍保留；旧报告夹具缺新DB，不是产品设备失败。cc06只隔离旧自测替身并增加实际report/SQLite对照，没有绕过生产回放。未无改动重跑覆盖原失败。

## 接续与未完成边界

先验05fc自己的完整主机和双API/独立报告；若红先读完整首次失败再最小修复，不用重试掩盖。之后补prepare/confirm进行中和回调期间销毁，再做稳定签名旧APK覆盖升级、AGENTS/CLAUDE同文且不超过200行、产品工作流集成、原子非强制产品提交/精确读回、绑定最终产品提交的双API与升级验收，之后才给新APK。

产品最近核验仍3a5a17e1fdc570c73804007cd9a4d2ef36c0966b，最近产品推送0；手机仍4d8742阶段预览。没有新APK、产品交付、合并或发布。剩余功能、照片/EXIF/输入法/大字体、性能、存储失败、易用性、商业签名与分发未全部验收。ADB255/ANR根因未证实，没有可靠整体完成百分比。

原始UI片段缺IOException，已提交不可变修复补齐，不可拿原片段覆盖产品。完整重建依赖固定工作流，不依赖短期artifact或某账号沙箱。沿用10月11日18:34[十一文件授权与21命令](https://github.com/supercubegame/todo-pocket-android/blob/9a6c72f8c67e2ae3520398833dc1ace7bcfcddf4/HANDOFF.md)：只用现有凭据；显式同意、先验证备份、普通启动不自动迁移、失败关闭。不清数据、不卸载、不启动外部应用、不操作手机、不合并发布。对话结束不代表助手继续开发。
