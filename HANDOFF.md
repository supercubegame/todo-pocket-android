# 口袋待办：当前接续入口

2026-10-15继续轮。单分支一个写入者；新账号独立授权GitHub，不假定继承技能、记忆或沙箱。不是完整交付、新APK或发布声明。

## 当前候选：e484原生启动数据库回放

[e4843a73提交](https://github.com/supercubegame/todo-pocket-android/commit/e4843a7353fe3bd1fc9fbe9e40481208d136c57d)，[CI38625576878](https://github.com/supercubegame/todo-pocket-android/actions/runs/38625576878)，push、attempt1、run46。最近读取主机116063753914：新增原生启动采集接线步骤已完成，正在执行完整21项集成主机验证；双API尚未开始。必须读取本候选自己的最终结果，不能用cc06绿灯替代。

仅修改现有隔离分支ci/shortcut-storage-preflight-4d8742的.github/workflows/shortcut-storage.yml，materialize时扩展现有tools/verify_shortcuts.py，Java运行代码未改。29319字节，blob f0b2553893bbedb1984c5549d7f52d08c88a7766，SHA256 780bd293e87c456ac46c39c88dfd08d1dbe92861dd7c91647dee4964fc4ce016。写入响应和独立不可变远端目录读取一致。

原生启动采集schema4-startup-ui.db、可选相邻WAL、files/startup-ui-expected.bin。oracle来自实际bridgeCells格式：18张旧表的类型化单元格后，附int32关系数和int64关系对，固定夹具要求[[7,10],[8,10]]；不能套用激活空关系解析器。只读SQLite核验完整表集合、全部旧值/类型/rowid、schema4和两条关系，两phase文件身份与快照都绑定receipt，实际report独立读取。

本地通过：真实Java编码器和主机SQLite读取正例1/精确反例20、仅WAL关系删除、整体关系断言遗漏；两phase采集与回放13反例；实际native report正例1/反例7、发布失败、整段回放遗漏；旧14报告例和实际activation report原1/7继续通过；真实接线3处整体遗漏均能拒绝。其他旧I/O、Android和GitHub是明确替身，本地不是完整checkout或Android验收。工作流保留前序24段独立run步骤、原21命令/300秒预算/一次执行、原失败发布；本地错误设备步骤数6已改为解析得到的5，修复前没有远端写入。

## cc06已完整通过，不再pending

[cc06运行38618514789](https://github.com/supercubegame/todo-pocket-android/actions/runs/38618514789)八作业/检查全部成功，完整21项主机、实际API26/API34构建和设备seed/reopen、独立报告及精确回写均通过。两段完整主机回执116043635644/116043646186已读，21命令均一次执行、每项300秒预算、无超时。host21耗时61.11888464100002秒，stdout8198字节/SHA256 02077af8dbfa946c2b8df824c00ee13cc61b25399e29e7225c0f5fc64132d507，stderr为空，artifact11922445321。

[API26完整证据](https://github.com/supercubegame/todo-pocket-android/runs/116046292671)、[API34完整证据](https://github.com/supercubegame/todo-pocket-android/runs/116046301304)已独立读回。两端原SHORTCUT seed97/reopen16，native-startup seed6/reopen2，activation seed8/reopen2；完整原始流未截断。激活数据库两phase各184320字节，oracle2735字节；18张旧表完整类型化历史一致，schema4，快捷关系为空。

验收verifier SHA256 bd2b8dafc89371197d128ce0ed400633d50a3fc1f2ea17e90f843f3e4518b26a；oracle SHA256 84a8073b8831cd7a71015b447ac2db712878962834afdaa73e60667bfa98cbb4；旧单元格汇总SHA256 92d1a6d935f75c43fed428c091ede652ef884dd2b9d80a538e099f4d3afce23b。API26数据库SHA256 7b0ebf79503655dfb7e03cea316d478041add7dcc7241c9f139bd84c8dacff01，API34为8f82278047ebf2008cc5673b21f8820f5201d43ec89374af8f876fcf599e3dcd，每端seed/reopen一致；不同API物理字节不同不代表旧历史不同。本次停止后快照未登记WAL，WAL行为另有真实主机SQLite对照。

cc06只在旧report_selftest的局部scope绑定legacy_activation_report_double，不绕过生产回放。新增真实report入口/真实SQLite正例、7精确反例、发布失败与整段回放遗漏守卫，保留旧14例及业务/启动变异。已接受激活回放与旧报告兼容，不代表原生启动数据库回放、真实旋转、稳定覆盖升级或产品交付。

cc06工作流实际21794字节，blob93a051e95e02d9057a35ff335ffc3e3e2714f6f1，SHA25688f6cba903bfd2d4c9bc8caa48670200003cd0c7f2a4d81cc007f08e556a5b5c。相对本地21795仅省略末尾空行，完整YAML和可执行脚本一致，未为无语义空行追加提交。

## c91首次失败保留

[c91原运行38612152149](https://github.com/supercubegame/todo-pocket-android/actions/runs/38612152149)首20主机通过，host21因旧report夹具没有新激活数据库而失败；设备未执行，不是设备数据失败。[完整9333字节日志](https://github.com/supercubegame/todo-pocket-android/runs/116022420171)、[命令流回执](https://github.com/supercubegame/todo-pocket-android/runs/116022412292)，artifact11918543537，未重跑覆盖。

首断言valid actual report entry，外层wrong startup replay witness是次级错误；新增13回放反例/4接线遗漏/8生命周期场景4变异当次已通过，但不等于整体通过。host21一次执行、300秒预算、30.107662626999968秒、无超时；stdout4328字节/SHAfa986deea4cbbe8009cac2b4b1594aa36e56e8086c75ebf74c719a9023a68e43，stderr2749字节/SHA5c7916fe1ea3492a7d4c380f94b98e47328c6f0c56ad023ded7ea082553cee50。

## 接续顺序和未完成的一半

先读e484自己的完整21主机、实际双API设备及native_database_replay两phase，核对18旧表/schema4/两条关系、原激活回放和源代码/运行身份。失败先读完整首次输出再最小修复，不无改动重跑，不让报告绿灯掩盖设备未执行。

之后补真实旋转/快速退出/准备或确认中销毁。已发现旧closeShortcutUi和activationUiSeed两个位置在非主线程读取shortcutTestScreen，尚未修改，也未证明实际竞态。native close helper已在主线程读取。b060的8场景4变异是实际Java AST成员加Android/DB替身，不是真实旋转。

仍欠稳定签名旧APK覆盖升级、AGENTS/CLAUDE同文且不超过200行、产品工作流集成、原子非强制产品提交及精确读回、绑定同一最终产品提交的双API/升级验收，之后才给新APK。产品最近核验3a5a17e1fdc570c73804007cd9a4d2ef36c0966b；本轮产品推送0。手机仍4d8742阶段预览，未操作手机。

剩余功能、照片/EXIF/输入法/大字体、性能、存储失败、易用性、商业签名分发仍未全部验收。ADB255/ANR根因未证实；没有可靠整体完成百分比。原始UI片段缺IOException，已提交不可变修复会补齐，不可用原始片段覆盖产品。完整重建依赖不可变工作流，不依赖短期归档或某账号沙箱。

[前序交接和修复细节](https://github.com/supercubegame/todo-pocket-android/blob/4354c4d6d9ac9ab4294ac62545a86de65b9d2e07/HANDOFF.md)。沿用10月11日18:34[十一文件授权与21命令](https://github.com/supercubegame/todo-pocket-android/blob/9a6c72f8c67e2ae3520398833dc1ace7bcfcddf4/HANDOFF.md)。只用现有凭据；显式同意、先验证备份、普通启动不自动迁移、失败关闭。不清数据、不卸载、不启动外部应用、不操作手机、不合并发布。无待处理安全确认。对话结束不代表助手继续开发。
