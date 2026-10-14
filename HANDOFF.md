# 口袋待办：当前接续入口

2026-10-15继续轮。单分支一个写入者；新账号独立授权GitHub，不假定继承技能、记忆或沙箱。不是完整交付、新APK或发布声明。

## 第一件事

读取[61e4dd53新运行38600355606](https://github.com/supercubegame/todo-pocket-android/actions/runs/38600355606)的首个结果。最后观察主机前置集成进行中，尚无本候选完整主机、设备、回写验收结论，不能沿用b060绿灯。

[新提交61e4dd53](https://github.com/supercubegame/todo-pocket-android/commit/61e4dd53c0127c3eb4fc27180048a5951fba04dc)仅修改现有隔离分支ci/shortcut-storage-preflight-4d8742的.github/workflows/shortcut-storage.yml，materialize时扩展现有tools/verify_shortcuts.py，并给原report增加紧凑证据回写。工作流18439字节，blob f7f43cd8ab1bfbf6bfcd9a785e71043f11c54867，SHA256 b9ba6b656b87588c51c3b6d735faeb30753d6251bc641aee3f16fc14028629e1。本地、写入返回、独立不可变目录读回相符。push，attempt1；没有取消或重跑旧失败。

产品最近核验仍3a5a17e1fdc570c73804007cd9a4d2ef36c0966b，产品推送0；手机仍4d8742阶段预览。没有新APK、合并、发布、新凭据或手机操作。

## b060已通过，不再pending

[b060运行38563332551](https://github.com/supercubegame/todo-pocket-android/actions/runs/38563332551)本轮新读六个作业全部成功：主机115849662681，完整回执115854369965/115854375716，API26 115854394573，API34 115854394829，汇总115856483490。两端真实Android编译、设备seed/reopen步骤和汇总均通过，非跳过。

[回执1/2](https://github.com/supercubegame/todo-pocket-android/runs/115854369965)、[回执2/2](https://github.com/supercubegame/todo-pocket-android/runs/115854375716)完整读回：原21命令一次、300秒预算、退出0、无超时。host21耗时83.12915068799998秒，stdout7757字节，SHA256 4feca37d22d1eefa4038e46f53e35ea592e40178fb40c2f04a0816913e91ed91，stderr空。原归档11894060345。本轮未独立下载stdout全文，不能声称逐字读过新增8场景/4变异那一行；此前本地真实JDK8/4通过，新CI已执行包含它的完整selftest。

候选verifier151259字节，blob8af5f29a58e7cc9673075c512b0412b35c3324e9，SHA25608e15c0fa6e5d0bfe560e559e86a7d8ab07c1be6dc77a0e0b6b7707f63c14718。其余五个Java文件身份与a727一致。生命周期检查从实际候选Java AST提取work/close，Android、widgets、DB仍是明确替身，不是真实旋转证明。

## 本轮实改：新UI验收不再藏在旧报告后面

旧parse_phase严格验证新增8个native启动及10个activation UI标签，却仍只返回旧SHORTCUT结果。61e4保留所有旧parser、返回类型、命令和预算，新增ui_phase_evidence独立序列化旧标签、新启动标签、新激活标签及原始流字节数/SHA256。

新增永久selftest：原旧报告缺字段RED；四个phase/API组合GREEN；56个字段遗漏、错误标签、错phase/API、错长度/摘要对照命中精确失败。原组合解析4正例、36遗漏、3变异也本地通过。回写器本地1正例/7反例验证缺reopen、串commit/run/attempt、失败receipt、漏activation标签、读回被篡改；使用真实扩展组合、明确legacy与GitHub transport替身，不能算远端验收。

report作业在原发布步骤之后always执行新增回写，按当前commit/run/attempt/API绑定result.json，重新解析原seed/reopen，生成两个完整小JSON及GitHub Checks，并逐字读回。超出传输预算会明确失败并保留文件，不截断冒充完整。现有原大报告保留，新增文件随independent-shortcut-report上传。源数据/设备失败仍为失败，不靠发布成功掩盖。此次没有修改产品运行时行为。

待新CI完成，要实际读取两个Exact UI device evidence检查的原始流，核对十个激活标签和八个启动标签；若失败，先读首个完整输出，再最小修复，不无改动重跑。

## 独立数据库回放接线已定位，尚未实现

只读审计确认：android()每phase先instrument，再stop，再列databases及采集。旧receipt["ui_snapshots"][phase]=database_snapshot(folder/"schema4-ui.db")之后是新增activation采集的接线点，继续使用原command封装，一次尝试、40秒默认预算、完整stdout/stderr保留。

需每phase采集schema4-activation-ui.db、存在时的同名-wal，以及files/activation-ui-expected.bin；增加独立receipt字段和产物摘要，不覆盖旧ui_snapshots。replay_shortcut_databases(folder,receipt,phase)追加专用activation回放，不能直接复用要求非空快捷关系的旧database_snapshot。源码身份已含MainActivity/TodayScreen/DeviceTest，expected.bin是运行产物，需要单独绑定。

SQLite mode=ro可能自动读取相邻WAL；未显式checkpoint不代表WAL未验证。下一步需实际WAL对照，不能沿用错误推断。现有activation-snapshot-reader.py/test原型本地Java编码器对照真实SQLite，1正例16反例通过，但未接设备采集或报告，仍欠真实原始产物回放。native启动UI库也需独立回放。

## 剩余承重工作与约束

继续真实旋转/快速退出/确认中销毁、UI数据库独立回放，再做稳定签名旧APK覆盖升级、AGENTS/CLAUDE同文且不超过200行、产品工作流集成、原子非强制产品提交与精确读回，绑定同一最终产品提交双API及升级验收，之后才给新APK。后续还有剩余功能、真实照片/EXIF/输入法/大字体、性能、存储失败、易用性、商业签名分发；没有可靠总完成百分比。ADB255/ANR根因仍未证实。

[上一不可变交接](https://github.com/supercubegame/todo-pocket-android/blob/55631c00fe5577c5c83a441577b040260ae9b5e9/HANDOFF.md)保留a727、be26、12de原失败与源码身份。原应用UI片段缺IOException，由已提交不可变修复补齐，不能直接覆盖产品文件。完整重建依赖不可变工作流，不依赖短期Actions归档或某账号沙箱。

沿用10月11日18:34原十一文件授权，[授权及21命令](https://github.com/supercubegame/todo-pocket-android/blob/9a6c72f8c67e2ae3520398833dc1ace7bcfcddf4/HANDOFF.md)。只用现有凭据；显式同意、先验证备份、普通启动不自动迁移、失败关闭。不清数据、不卸载、不启动外部应用、不操作手机、不合并发布。对话结束不代表助手继续开发。
