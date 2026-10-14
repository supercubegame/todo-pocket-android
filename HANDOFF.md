# 口袋待办：当前接续入口

2026-10-15 02:01用户确认后，数据库采集与独立回放候选已实际提交并精确核对远端。单分支一个写入者；新账号独立授权GitHub，不假定继承技能、记忆或沙箱。不是完整交付、新APK或发布声明。

## 第一件事：读取本候选首轮结果

[c91aa961提交](https://github.com/supercubegame/todo-pocket-android/commit/c91aa961933438e16acef6382355eee0ef0bc8c9)，[CI38612152149](https://github.com/supercubegame/todo-pocket-android/actions/runs/38612152149)。最后观察主机116017958541执行原后端验证中，新增数据库接线步骤尚未到达。没有本候选完整主机、设备或独立回放验收结论，不得沿用61e4绿灯。push，attempt1，没有重跑原失败。

仅更新现有隔离分支ci/shortcut-storage-preflight-4d8742的.github/workflows/shortcut-storage.yml；materialize时修改现有tools/verify_shortcuts.py。工作流27776字节，blob2a5e5ef91022ae497874427e0be957d65ba65d58，SHA2567c2f13c163d25e6f2dbc51753f7d9afba45e94d6752904bc40a3b1d43be5eafb。本地、写入响应、独立不可变目录读回一致。原暂停提交在用户明确批准后才执行，无待处理确认。

产品最近核验仍3a5a17e1fdc570c73804007cd9a4d2ef36c0966b，本轮产品推送0；手机仍4d8742阶段预览。没有新APK、合并、发布、新凭据或手机操作。

## 前序61e4已通过，原始UI流已完整读回

[61e4运行38600355606](https://github.com/supercubegame/todo-pocket-android/actions/runs/38600355606)八个作业/检查全部成功，包含主机、实际API26/API34构建与seed/reopen、原汇总和两个新增精确回写检查。旧pending已过时。

[API26完整原始流](https://github.com/supercubegame/todo-pocket-android/runs/115984330118)、[API34完整原始流](https://github.com/supercubegame/todo-pocket-android/runs/115984340696)均已完整读取：每端原SHORTCUT seed97/reopen16，另有启动seed6/reopen2、激活seed8/reopen2。显式未勾选拒绝、取消、旧确认回调、备份篡改拒绝、成功后实际Activity重建、重复进入与独立进程历史保留均有对应标签。不是覆盖升级或产品交付。

两端verifier SHA256 c03d4161aa2472d7f9b12f403e652e180243a1ed2a0c9e245767e9dce5a0dcae。API26 seed6114字节/SHA2560046c92bcd8cba96c6520deab37ad94cd3e9c5cb29a8d7d2ed328d6d75cac430，reopen1188字节/SHA25641995c1b653dbfa8b122c117c2664ee633c7871cab26a76f128d7f8f7a0b9890。API34同字节数，seedSHA25625ffd6874f99f7a61b0015609de3d561d1f9b75fb2561014150a7c685569f35b，reopenSHA25668b60879a9cc7fc268ec6a5207c0479a1ee68fb2606332dc109058bd4a009a0e。

b060此前21主机和双API通过；实际源码生命周期8场景/4变异使用Java AST与明确Android/DB替身，不可称真实旋转并发验收。历史回执与原失败见上一交接。

## 新候选做了什么

在android()每个seed/reopen进程停止、旧UI快照完成之后，追加采集schema4-activation-ui.db、存在时的同名WAL、files/activation-ui-expected.bin。沿用原command封装与一次尝试、原预算、完整流保留，不启动应用、不清数据、不改产品行为。

新增activation_ui_snapshots字段，分别保存文件字节数/SHA256与独立SQLite快照。原18表的列、rowid、整数/null/text/blob逐项比对Java格式预迁移oracle，要求schema4、精确表集合、空category_shortcuts。两phase快照必须相同。原有receipt、解析、命令和数据库回放均保留。

report()在原replay_shortcut_databases调用后直接追加replay_activation_ui，不重绑旧bridge_receipt，避免污染旧selftest夹具。独立读回文件摘要，拒绝缺文件、未登记WAL、篡改摘要/单元格/伪造快照。原始UI紧凑回写也追加独立数据库回放结果、18表数量和单元格摘要。

本地真实Java编码器、真实SQLite通过：两phase采集、两phase报告回放、13个精确反例，其中含只有相邻WAL携带已提交变更的对照；读取前后DB/WAL字节不变。源码接线正例及4个整体遗漏变异通过。local入口是合成android/report骨架，不是完整checkout；首次完整源码接线和Android采集仍待c91 CI。

本地首次逆向检查误把其他同文函数调用算成重复，提交前已修复为按AST位置插入与按确切位置逆向删除，逐字恢复原verifier。不是产品故障。所有shell语法与前序嵌套loader逆向对照通过。新增真实JDK/SQLite/接线测试已经随现有verifier selftest接入候选，不仅保存在沙箱。

## 下一步与边界

先读取c91原始首轮结果：完整21主机、实际候选源码接线4遗漏、双API实际编译/采集、原汇总与紧凑数据库回写。失败先读完整首个输出再最小修复，不无改动重跑。API绿灯但独立回放未过不能算完成。

仍欠native-startup UI数据库独立回放、真实旋转/快速退出/确认中销毁、稳定签名旧APK覆盖升级、AGENTS/CLAUDE同文且不超过200行、产品工作流集成、原子非强制产品提交与精确读回，以及绑定同一最终产品提交的双API/升级验收，之后才给新APK。后续还有剩余功能、照片/EXIF/输入法/大字体、性能、存储失败、易用性和商业签名分发。ADB255/ANR根因仍未证实，没有可靠整体完成百分比。

[上一不可变交接](https://github.com/supercubegame/todo-pocket-android/blob/2917b5bf10848052f17c35f725b28b48c1136374/HANDOFF.md)保留b060、61e4和更早证据链接。原始UI片段缺IOException，由已提交不可变修复补齐，不能直接覆盖产品文件。完整重建依赖不可变工作流，不依赖短期归档或某账号沙箱。

沿用10月11日18:34原十一文件授权，[授权及21命令](https://github.com/supercubegame/todo-pocket-android/blob/9a6c72f8c67e2ae3520398833dc1ace7bcfcddf4/HANDOFF.md)。只用现有凭据；显式同意、先验证备份、普通启动不自动迁移、失败关闭。不清数据、不卸载、不启动外部应用、不操作手机、不合并发布。对话结束不代表助手继续开发。
