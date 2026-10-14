# 口袋待办：当前接续入口

2026-10-14继续轮，已核验至a727双API成功、b060新CI启动。单分支一个写入者；新账号独立授权GitHub，不假定继承技能、记忆或沙箱。不是完整交付、新APK或发布声明。

## 第一件事

读取[b060055f新运行38563332551](https://github.com/supercubegame/todo-pocket-android/actions/runs/38563332551)的原21主机回执及双API设备结果。此候选是新增实际源码生命周期验证，不是产品功能改动。最后观察in_progress，尚无它自己的完整主机或设备结论，不得套用a727绿灯。

[b060提交](https://github.com/supercubegame/todo-pocket-android/commit/b060055fdda76b408ba7023ba2014279651ef86d)只更新现有分支ci/shortcut-storage-preflight-4d8742的.github/workflows/shortcut-storage.yml。16281字节，blob 1a79175fddaed4c68329672b9ff1912bd29a9dc0，SHA256 e6fe424d64dc2cf055e20f46d1a0a25602fcf148510fdb296a4e0a6dd097114c。本地、写入返回和独立不可变目录读回一致。push、attempt1，未取消原运行。

产品最近核验仍3a5a17e1fdc570c73804007cd9a4d2ef36c0966b，产品推送0；手机仍4d8742阶段预览。没有新APK、合并、发布、新凭据或手机操作。

## 已确认：a727坐标修复候选通过双API

[a727运行38561435393](https://github.com/supercubegame/todo-pocket-android/actions/runs/38561435393)六作业全部成功。原21主机命令均一次、300秒预算、退出0，无超时；[回执1/2](https://github.com/supercubegame/todo-pocket-android/runs/115847133618)、[回执2/2](https://github.com/supercubegame/todo-pocket-android/runs/115847142175)均已完整读取。host21耗时66.715321366秒，stdout7664字节，stderr空。

API26作业115847166776、API34作业115847166919实际Android编译和设备步骤均成功；汇总115849194052成功。API26完成12:20:46Z，API34完成12:21:35Z，汇总完成12:21:48Z。不是设备被跳过。

[不可变汇总报告](https://github.com/supercubegame/todo-pocket-android/blob/44969bb3b99a212345e528bbb3fbc8e84ad10605/reports/shortcuts-a72753a2ac0d175ae1ee357baa471369eb8e1676-38561435393-1.json)，blob e0d8e7c346847ac474a8419940409f9184f27be8。工具读取大报告被截断，不能称本轮逐字审计了全部快照或双API原始流。报告保留旧scope文字；新parser严格要求额外8个native启动及10个activation UI标签，但返回旧parser结果，汇总没有直接列出新增标签。这是可读性缺口，不应编出已读到的标签。下一步补紧凑原始seed/reopen回写，并把新标签保存到报告。

主机候选AppDatabase/Schema4Store/TodayScreen/MainActivity身份沿用be26；DeviceTest71664字节/blob d1faa66b1b273b5cc9df3bb908f33dd2eaad0f7b/SHA256 59f765e24e7dda831f2f0059f4670419dc66e922fad572ef2e1aa6099528ff2f；verifier139518字节/blob9016ee5d18005275d38cbef1c6d786e2ee483925/SHA2568254916c99ca1e974421444a3d62291761abb712bbebc3684a498568bf67850b。原归档11892327610。

## 原失败和修复边界

be26运行38558758574原21主机与双API编译成功，但两端都在activation_ui_unchecked_cannot_commit断言失败，不再pending。12de只读提取按原ZIP和seed哈希校验并回读：[原26流](https://github.com/supercubegame/todo-pocket-android/runs/115841687631)、[原34流](https://github.com/supercubegame/todo-pocket-android/runs/115841698565)。没有重跑原失败。旧复合断言不能区分提示文字和旧单元格哪个条件失败。

a727仅改新测试的弹窗触点：原先误把根视图坐标当屏幕坐标，现以getLocalVisibleRect加getLocationOnScreen偏移计算一次DOWN/UP，没有重试或预算放宽。同时拆分提示、schema、旧单元格诊断，保留原十标签和断言。真实双API现在通过；没有为迁就测试改产品行为。

## 本轮新提交：不再验证work/close抄本

b060把activation-lifecycle-gate接进现有tools/verify_shortcuts.py selftest。Java编译器AST从实际候选TodayScreen提取两个work重载与close，而非硬编码抄本；激活成员取自同一候选。Android、widgets、DB仍明确是替身，不可称Android并发验收。

CountDownLatch确定性验证8种时序：prepare前关闭、prepare完成回调前关闭、finishing、destroyed、可见同意失效、确认排队时关闭、提交后回调前关闭、失败后回调前关闭。4个变异分别删除弃用计划清理、尝试计划失效、finishing守卫、close中的清理；每个必须先有正常见证，再命中精确断言，编译或超时不算击杀。本地真实JDK通过8场景/4变异，AST注释/嵌套诱饵及遗漏成员对照通过；不是完整仓库本地主机或Android证明。CI首次对完整候选执行仍在进行。

所有原命令、失败、预算、6文件身份与设备流程保留；工作流变换已验证反向移除新增hook后逐字恢复旧集成程序，前序不可变脚本内容精确一致。

## 剩余承重工作

先读b060首个原始结果。随后完成真实旋转/快速退出/确认中销毁，以及报告侧独立UI数据库回放。现有activation-snapshot-reader.py/test原型本地Java编码器对照真实SQLite，1正例16反例通过，但尚未接入设备采集或汇总。每phase需收schema4-activation-ui.db、可选WAL、activation-ui-expected.bin，独立比对全部旧类型、schema4、空快捷关系，并补采集/回放整体遗漏对照。native启动UI库也需同样回放。

再做稳定签名旧APK覆盖升级、AGENTS/CLAUDE同文且不超过200行、产品工作流集成、原子非强制产品提交与精确读回，绑定同一最终产品提交双API及升级验收，之后才给新APK。后续还有剩余功能、真实照片/EXIF/输入法/大字体、性能、存储失败、易用性、商业签名分发；没有可靠总完成百分比。三字节媒体不证明真实照片兼容，ADB255/ANR根因仍未证实。

[上一交接及旧源码包入口](https://github.com/supercubegame/todo-pocket-android/blob/b9218c031d1c4a5478728703c0c6abd0ca769d83/HANDOFF.md)保留be26、e8、de8、cbbc历史。原应用UI片段缺IOException，由已提交不可变修复补齐，不能直接覆盖产品文件。完整重建依赖不可变工作流，不依赖短期Actions归档或某账号沙箱。

沿用10月11日18:34原十一文件授权，[授权及21命令](https://github.com/supercubegame/todo-pocket-android/blob/9a6c72f8c67e2ae3520398833dc1ace7bcfcddf4/HANDOFF.md)。只用现有凭据；显式同意、先验证备份、普通启动不自动迁移、失败关闭。不清数据、不卸载、不启动外部应用、不操作手机、不合并发布。对话结束不代表助手继续开发。
