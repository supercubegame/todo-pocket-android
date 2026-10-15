# 口袋待办：当前接续入口

2026-10-15 14:14继续轮。单分支一个写入者；新账号独立授权GitHub，不假定继承沙箱/记忆/技能。没有新APK、产品提交、合并或发布。

## 首要动作：读e44b83本候选的首轮结果

[提交e44b83bd4f25f2e083ecca5f6420af9400916105](https://github.com/supercubegame/todo-pocket-android/commit/e44b83bd4f25f2e083ecca5f6420af9400916105)，[CI38691647981](https://github.com/supercubegame/todo-pocket-android/actions/runs/38691647981)，push、attempt1、run51、check suite104847489924。最近读取为in_progress，尚无本候选完整主机/双API/报告结论，不能用bfb设备绿灯或512263全绿替代。

仅提交既有隔离分支ci/shortcut-storage-preflight-4d8742的.github/workflows/shortcut-storage.yml。16726字节，blob714714aba10c6f98742b57bb99be34cbdf8c9778，SHA25650eeb976d6195ddb49606f2d1f3b953318b43c6194bc825d190024eadc74154f；本地、写入响应、独立不可变目录核验一致。无待处理安全确认。

只追加既有verify_shortcuts.py生成内容的报告契约修复，不改产品Java，不改bfb设备测试，不改旧报告发布器。require_ui_evidence现在严格接受原7字段加queue/life两字段，逐项与原始流解析结果相等，再把原7字段交给原校验器核验。不是允许任意额外字段，不是删除新证据，不是跳过失败。旧测试有意使用旧producer，仅在原selftest链try/finally内配对旧checker，结束恢复新checker；实际设备/报告仍严格走新入口。

永久selftest增加实际producer->JSON往返->实际checker：原UI evidence exact fields红灯、4正例、76精确拒绝反例，覆盖每字段缺失、未知字段、两新族伪值、原身份/旧标签/原始流摘要；两处整新字段验证省略见证先过好输入，再错误接受坏值，真实checker拒绝。该门在设备作业之前运行，减少再到报告阶段才发现字段不兼容的浪费。

本地上述4/76通过，旧UI4/56、生命周期4/18及Java AST、组合4/36/两旁路/一晚绑定、旧启动/激活解析继续通过。另执行实际publish-ui-evidence.py源的1正例/9反例（明确旧标签夹具和GitHub传输替身）：保留双API失败可见性、身份拒绝、缺reopen、缺queue/life标签、精确回写拒绝。该发布器本地检查不是实际GitHub网络或新增双库SQLite验收。尝试本地全selftest时，片段Source缺parents导致夹具能力错误，未算通过；改为明确有限旧解析器测试，完整checkout交给CI。

工作流逐字恢复bfb全部42个run脚本(host24/device9/report9)，步骤/环境/原命令/预算/首次失败保留，只有集成前追加修复。materializer精确逆向还原、shell语法检查通过。hook SHA2560587014e4554016c8d77307756143b3a410a52ac394fff8fea63e0992a3265e1。

## bfb230：主机和设备通过，但报告失败，不能叫整轮通过

[原CI38677741594](https://github.com/supercubegame/todo-pocket-android/actions/runs/38677741594)，提交bfb2300b6e3ff133e2626b930c7e89814a8a833b。host116235080962成功；API26 116237979538/API34 116237979594实际构建及设备作业成功；report116239179371在最后发布精确UI证据步骤失败。没有无改动重跑。

[API26原失败](https://github.com/supercubegame/todo-pocket-android/runs/116239240144)、[API34原失败](https://github.com/supercubegame/todo-pocket-android/runs/116239244988)完整output已直接读取。二者相同首错误AssertionError: UI evidence exact fields，source_status PASS、phases空、NOT_VERIFIED；只保存到seed流，reopen尚未进入读取。两端完整seed明确含原97标签、启动6、激活8、life3、queue2以及最终PASS。因此可称队列场景实际设备执行通过，不能称本轮完整报告/双库证据回读验收完成。没有把这个报告错误说成产品数据失败。

根因：bfb的ui_phase_evidence新增activation_queue_labels/activation_life_labels，旧require_ui_evidence仍要求恰好7字段。旧自测范围恢复旧producer，故21主机没有触及新producer与旧checker的不兼容。已在本地用同一组合复现原报错，然后最小修复并增加新永久门。

全21主机回执[上半](https://github.com/supercubegame/todo-pocket-android/runs/116237962085)/[下半](https://github.com/supercubegame/todo-pocket-android/runs/116237966080)已完整读取，均一次、300秒、return0、无超时。host21 elapsed127.52439687399999秒、stdout17390字节/SHA256e0989c04219eace01fed0f3a4e379d37f56b553651e07aeb7b240e8da36ccd16/blob956e6d397a3dd4fee8d03ec24d8ef00a2b0dfcff，stderr空。artifact11947192080未下载，未逐字读完整host21 stdout。

bfb DeviceTest81260字节/blob00c19198bc59dcc9a8f3911da394ee3bd686a339/SHA256cb9ca2c3f14e0abee11b032637a78392d2eb82a1b86ab2aa8c34a441f1042372；verifier269924/blobc1d697a25b71618e0dc4ae27511ddff28ad21a58/SHA256f0defa978ba61b0f64b5ed32c4e267f3f04aa09607f4e43804a3e678a3c45854。四份产品Java与512263相同。

队列场景限定：准备或确认请求在真实screen执行器排队，旧Activity销毁/screen关闭/executor shutdown先于latch释放；随后旧任务完成且无迟到dialog/plan/attempt，schema3历史及确认备份不变，重开再次核验。不是业务动作/SQLite事务执行中、文件写入中、主线程回调排队销毁、进程杀死、手机或覆盖升级。

## 最新完整已验收仍512263

[512263 CI38675713479](https://github.com/supercubegame/todo-pocket-android/actions/runs/38675713479)八作业/检查全绿，全21及API26/API34真实预览完成后rotation/recreate/finish、双库独立回放、精确报告读回全部通过。完整JSON和seed/reopen已直接读取。[上一版完整交接](https://github.com/supercubegame/todo-pocket-android/blob/0b086585651abe8078bcc9d2b15496a8527e9ccb/HANDOFF.md)保存全部主机/源码/数据库/原始流摘要与链接，其bfb pending由本文替代。更早05fc、c91原失败从该文链接永久追溯，不重跑覆盖。

## 实际剩余交付顺序

先验e44b83自己的原21、两端实际构建/所有场景、完整seed/reopen、新两族字段、双库回放和源码身份。失败先读第一实际错误，最小修复，不靠重试。之后继续真实prepare/commit执行中与回调排队销毁，稳定签名旧APK覆盖升级，AGENTS/CLAUDE同文且不超200行，最终产品完整集成/21主机/原子非强制推送/精确远端读回/同最终提交双API及升级，之后交付新APK。文档不能替代代码，旧绿灯不能接受新候选。

产品最近核验仍3a5a17e1fdc570c73804007cd9a4d2ef36c0966b，近期产品推送0；手机仍4d8742阶段预览。ADB255/ANR根因未证实。剩余功能、照片/EXIF/输入法/大字体、性能、存储失败、易用性、商业签名和分发未全验；没有可靠整体百分比。

沿用[十一文件授权与原21命令](https://github.com/supercubegame/todo-pocket-android/blob/9a6c72f8c67e2ae3520398833dc1ace7bcfcddf4/HANDOFF.md)：现有凭据、明确同意、先验证备份、普通启动不自动迁移、失败关闭；不清数据、不卸载、不操作手机、不启动外部应用、不合并发布。原UI片段缺IOException，不可覆盖修复后的完整类。完整重建依赖不可变工作流，不依赖短期artifact或沙箱。对话结束不表示助手继续开发。
