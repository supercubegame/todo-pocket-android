# 口袋待办：当前接续入口

2026-10-15继续轮。单分支一个写入者；新账号独立授权GitHub，不假定继承技能、记忆或沙箱。不是产品交付、新APK或发布声明。

## 第一件事：读取e9bf线程修复自己的首轮结果

[e9bf4306提交](https://github.com/supercubegame/todo-pocket-android/commit/e9bf430691bda02f4b5dbd2c7cf960c88cc2f6f9)，[CI38627964450](https://github.com/supercubegame/todo-pocket-android/actions/runs/38627964450)，push、attempt1、run47，最后观察in_progress。尚无本候选完整主机或双API验收结论，不能沿用e484绿灯。

当前隔离分支ci/shortcut-storage-preflight-4d8742，仅提交既有.github/workflows/shortcut-storage.yml。21935字节，blob83a0a60fdb5889355a3447b52d4776c001d4c3d0，SHA256 2bd4ef98dc1c12b76930f3d9d2979bd531afbf49182fe949217238f541b6c838。本地、写入响应、独立不可变远端目录读取三方匹配。无待处理安全确认。

materialize修改既有Schema4DeviceTest.java和verify_shortcuts.py：三处screen引用原来在非主线程读取，旧closeShortcutUi还在finish后才取引用；改为主线程捕获引用，再在测试线程等待executor关闭。新增captureScreenOnMain，只改变测试归属，不修改产品Java运行行为、UI标签、原预算或重试次数。不是已证明的真实设备竞态修复，也不是真实旋转验收。

新永久门禁用Java AST扫描实际测试类，非空读取集合每处必须处于runOnMainSync直接lambda；从实际源码提取captureScreenOnMain/closeShortcutUi，运行同语言Java真实线程测试，Android为明确替身。正常关闭、空引用关闭、缺screen拒绝三场景通过；去掉主线程调度、去掉引用捕获、去掉finish三运行变异，加两个激活调用点退回非主线程的变异，均能拒绝。注释/字符串伪调用不影响扫描。本地先复现真实片段3处OFF_MAIN红灯，再最小修复跑绿。完整测试类的相同RED也已接入本次CI，尚待结果。

工作流逐字复用固定e484原生回放步骤并核验文件及脚本摘要；原设备和报告job完全不变，原21主机命令、300秒预算、一次执行、全部失败发布保留。嵌套materializer和源码patch都有精确逆向恢复检查。没有新增产品文件。

## e484已完整验收，不再pending

[e484提交](https://github.com/supercubegame/todo-pocket-android/commit/e4843a7353fe3bd1fc9fbe9e40481208d136c57d)，[CI38625576878](https://github.com/supercubegame/todo-pocket-android/actions/runs/38625576878)，八作业/检查全部成功，attempt1。完整21项主机、实际API26/API34构建与seed/reopen、独立报告及精确回写通过。主机116063753914、双API116068385400/116068385171、汇总116070450151。工作流29319字节/blobf0b2553893bbedb1984c5549d7f52d08c88a7766/SHA256780bd293e87c456ac46c39c88dfd08d1dbe92861dd7c91647dee4964fc4ce016。

[主机回执上半](https://github.com/supercubegame/todo-pocket-android/runs/116068342748)、[下半](https://github.com/supercubegame/todo-pocket-android/runs/116068353129)完整拼接已读。21命令全部一次、每项300秒、无超时；host21耗时78.37625065600002秒，stdout8706字节/SHA25605bcbfefcc9723a898ef22d7a376ec86aa625296ccbede2ad17a1065ca540176，stderr为空。host artifact11924243806。

[API26完整证据](https://github.com/supercubegame/todo-pocket-android/runs/116070539314)、[API34完整证据](https://github.com/supercubegame/todo-pocket-android/runs/116070546810)中的完整JSON、seed/reopen原始流、启动和激活两种数据库独立回放均已读回；外层GitHub app元数据尾部截断不影响完整output.text。每端旧标签seed97/reopen16，启动6/2，激活8/2。verifier224830字节，blobcc7a8186a446439c86be7452cd508d25ae21fe59，SHA2567944868a29217875942a4b2667fa4d7d804ea76fe7f70a03ee2a8af3d89b9279。

原生启动数据库schema4-startup-ui.db每phase184320字节，API26 SHA256 e556c4545d894267d1a698f9f6cfb0f08cf43c9a222c3f0f6b6d2bbf2288bee8，API34 SHA256 ca00fdb4f54981a1b72e38c6aae8ae233dc9e11c78faf3c1306fe19ecf291b3f；每端seed/reopen相同。oracle2771字节/SHA25696d8cad444e96b47fd854cd31b0ea60ee371578b7aed5f63e130e58c9c3f712d。18张旧表完整类型化历史汇总SHA256a670d8086e51e17d9e382d2fead7f2684f9cce91daf96c7d7c23b0139ff1455a，schema4，关系精确[[7,10],[8,10]]，两phase一致。不同API物理DB字节不同并非旧历史不同。

激活数据库独立回放也保持通过：18旧表，schema4，关系为空，两phase一致；每端DB184320字节，oracle2735字节。API26 DB SHA2567b0ebf79503655dfb7e03cea316d478041add7dcc7241c9f139bd84c8dacff01，API34 8f82278047ebf2008cc5673b21f8820f5201d43ec89374af8f876fcf599e3dcd；oracle84a8073b8831cd7a71015b447ac2db712878962834afdaa73e60667bfa98cbb4；旧表汇总92d1a6d935f75c43fed428c091ede652ef884dd2b9d80a538e099f4d3afce23b。

这些实际停止后快照未登记WAL；真实主机SQLite另有仅WAL修改对照，不能声称本次设备产生过WAL。native oracle为bridgeCells，旧18表后带int32关系数/int64关系对，不可误用激活old-cells-only解析器。新采集/报告保留实际命令、预算、文件身份和缺失即失败；没有只靠设备标签判断数据正确。

## 前序证据与首失败

[cc06运行38618514789](https://github.com/supercubegame/todo-pocket-android/actions/runs/38618514789)此前已通过全部八检查，修复旧report夹具兼容且接受激活独立回放。[完整交接及cc06身份](https://github.com/supercubegame/todo-pocket-android/blob/81c9f8f38c682c3e3cb7dbbd0883dd56bd1531ce/HANDOFF.md)保留细节，里面e484 pending现已由本记录更新。

[c91首失败日志](https://github.com/supercubegame/todo-pocket-android/runs/116022420171)、[原命令流](https://github.com/supercubegame/todo-pocket-android/runs/116022412292)保留：首20主机通过，第21旧report夹具缺少新激活数据库，首断言valid actual report entry，外层wrong startup replay witness为次级错误；设备未执行。artifact11918543537，未无改动重跑覆盖。cc06只在旧自测局部scope放显式旧夹具替身，同时新增真实report/SQLite正反例守卫，不绕过生产回放。

## 下一步与未完成边界

先验e9bf自己的完整主机和双API/独立报告。若红先读取原始首次失败再最小修复，不用重试掩盖、不沿用旧绿灯。之后补真实旋转、快速退出、准备或确认中销毁，以及稳定签名旧APK覆盖升级。b060实际Java AST的8场景4变异仍只是Android/DB替身，不是真实旋转。

仍欠AGENTS/CLAUDE同文且不超过200行、产品工作流集成、原子非强制产品提交/精确读回、绑定同一最终产品提交的双API及稳定覆盖升级，之后才给新APK。产品最近核验仍3a5a17e1fdc570c73804007cd9a4d2ef36c0966b，最近产品推送0；手机仍4d8742阶段预览。没有新APK、产品交付、合并或发布。

剩余功能、照片/EXIF/输入法/大字体、性能、存储失败、易用性、商业签名与分发未全部验收。ADB255/ANR根因未证实，没有可靠整体完成百分比。原始UI片段缺IOException，已提交不可变修复会补齐，不可用原始片段覆盖产品。完整重建依赖不可变工作流，不依赖短期归档或某账号沙箱。

沿用10月11日18:34[十一文件授权与21命令](https://github.com/supercubegame/todo-pocket-android/blob/9a6c72f8c67e2ae3520398833dc1ace7bcfcddf4/HANDOFF.md)。仅用现有凭据；显式同意、先验证备份、普通启动不自动迁移、失败关闭。不清数据、不卸载、不启动外部应用、不操作手机、不合并发布。对话结束不代表助手继续开发。
