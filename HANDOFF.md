# 口袋待办：当前接续入口

2026-10-17，13:30五文件批准后的执行检查点。修复已提交隔离分支并核对不可变工作流身份，实际CI正在完整原21项验证阶段。尚未读取成功产品更新回执，不宣称新产品已提交、设备已通过或新APK可用。

## 先读当前运行，不要重复提交或无变化重跑

[修复提交0f108f577637c803c2d102201d90f7dba0735554](https://github.com/supercubegame/todo-pocket-android/commit/0f108f577637c803c2d102201d90f7dba0735554)，[CI39007573640](https://github.com/supercubegame/todo-pocket-android/actions/runs/39007573640)，run70，attempt1，suite105714795373，job117323067645。提交时间2026-10-17T05:47:53Z。只更新既有隔离分支ci/shortcut-storage-preflight-4d8742的.github/workflows/shortcut-storage.yml。

工作流17863字节，Git blob 28d28bc342fd03a5feb9ecb83a1748a45a57d609，SHA256 306e4e435da9788f4a0fcfc2a3041baee4f07562f1c1dfbd42d856045df991d7；独立不可变目录读取与本地一致。内嵌repair.py/prepare.py载荷36936字节，SHA256 9e17a32db63b37be6dad851502cd1771742866f96ecdd6e25c56089f8e488ad5。恢复时先验证摘要再执行，不依赖上次沙箱临时目录。

最新实际读取：checkout、固定来源恢复、实际改造交付器控制均success；Full original21 once then atomic exact product delivery仍in_progress。原21命令各一次、每条300秒预算，验证在保留的独立worktree执行，发布目录继续零未跟踪保护。提交前后分支、完整树、模式、单父、force=false和远端每个blob字节读回保留。通过后单次更新产品四文件，再分别dispatch shortcut-storage.yml和android.yml；dispatch不是设备验收。

交付回执通过同suite的Readiness repair delivery分段check发布，包含各命令原输出身份及失败尾部；完整输出和候选保存在readiness-timeout-delivery归档。先读最终回执，再独立读产品ref、父/tree、四文件及同新SHA的实际设备运行。失败先读首失败，不绕过、不增加预算、不重试到绿。

## 五文件批准与实现范围

用户于2026-10-17 13:30批准approve_paged_readiness_timeout_batch，消息80180082410214，线程80180077935853。四个产品文件为tools/verify_paged_exports.py、tools/emulator_gate.py、AGENTS.md、CLAUDE.md，第五个是现有隔离工作流。原十一文件激活授权继续有效。不重复请求已批准范围。

分页测试修复：真实Activity的idle、等待与初次快照移入原try/finally；主线程观察非空且非busy的screen，检查finishing/destroyed；10000ms观察上限和50ms间隔仅是卡死保护，不是实测性能结论，仍在原180s仪器命令中。主线程捕获数据库引用，exportState仍离开主线程执行。保留原29后端和22预览断言，不修改产品启动代码。

超时留证：只包装verify_database的原seed/reopen调用，保留原命令、180s、单次调用和原TimeoutExpired对象；原始部分stdout/stderr不解码，保存device-<phase>-timeout-stdout.txt和stderr.txt，并在device-<phase>-timeout.txt保存captured/type/bytes/hash。原device-*.txt上传规则覆盖这些文件；缺失流明确标记，不把空输出当无错误。留证写入失败不替换原超时。这不是API34超时根因修复。

永久主机控制：JDK AST从当前完整JAVA提取真实helper字节，检查预览调用、两个快照和finally归属；7种场景、4个有正向见证的变异、4个整调用遗漏，以及原null-screen RED。Android类/时钟是明确替身，不是设备证明。超时helper有7种替身场景、3个有成功见证的变异、1个真实主机子进程超时、1个留证二次失败；另检查实际180s调用、跨文件注册与上传遗漏。集成器还执行原/新完整verify_database函数的ADB替身对照。

本轮本地重建与上述有限控制通过；完整改造交付器使用真实Git、替身GitHub/业务命令验证成功及host失败、分支变化、额外树路径、远端字节不符四种故障。本地不是完整checkout，也没有Android验收。上轮未提交临时脚本已丢失，本轮从已提交源码和保留附件重建并重新运行，未沿用旧本地通过结论。

## 产品基线和原始失败

产品最后独立读取为[c9d905b37061c0f52f57be54c318ce275ef0f1fa](https://github.com/supercubegame/todo-pocket-android/commit/c9d905b37061c0f52f57be54c318ce275ef0f1fa)，父3a5a17e1fdc570c73804007cd9a4d2ef36c0966b。28ee/38916090823已完成原21项、精确八文件提交与两个dispatch，旧交接的产品3a5a/交付pending已失效。

[c9主运行38917276308](https://github.com/supercubegame/todo-pocket-android/actions/runs/38917276308)四个设备job失败，upgrade明确skipped，没有新APK。database API26、export API26和export API34共同首失败为PagedContractTest.state读取空MainActivity.screen；原测试把UI idle误当成异步startupIo完成。原29后端记录存在，预览未完成。database API34另在V12DeviceTest seed原180s预算超时，根因未知，不能并为分页NPE、历史ADB255或系统ANR。

[原证据恢复38975861159](https://github.com/supercubegame/todo-pocket-android/actions/runs/38975861159)已completed/success；[完整发布索引117225709207](https://github.com/supercubegame/todo-pocket-android/runs/117225709207)。0b69恢复七个固定原始ZIP，保留原身份，不重跑业务。此前84b246因传输丢失digest三字符而正确拒绝，0b69固定来源loader恢复字节后成功。

API34主归档12054130666只有build.log、lint报告、device-package.txt、emulator.log、isolated-trace-host.log、setup.log、ui.log七项，未列出部分seed输出、logcat或ANR文件。原emulator_gate只在run返回后写device-seed.txt。该证据缺口不代表所有其它来源也不存在。

[c9快捷运行38917272644](https://github.com/supercubegame/todo-pocket-android/actions/runs/38917272644)四job成功。本轮已完整读双API seed/reopen原始流：seed各97个legacy SHORTCUT标签及启动/激活/生命周期/队列/回调/在途/postDDL标签，reopen各16个legacy标签及启动/激活标签，均INSTRUMENTATION_CODE:-1。证据check为117225253776、117225391087、117225133027、117225268918。大result的独立DB回放及56段aggregate尚未完整复核，不把原流阅读等同完整最终验收，也不沿用其接受新提交。

## 安全与尚未完成

手机仍4d8742，无新验收APK。只用既有凭据；不清数据、不卸载、不操作手机、不自动schema3到4迁移、不启动外部应用、不合并或发布。明确同意与验证备份先于激活，失败关闭。没有待批准安全事项。

覆盖升级脚本仍重新构建f42旧源并用当前固定密钥，属于REBUILT_OLD_SOURCE_SAME_FIXED_KEY_OVERWRITE_NOT_EXISTING_PHONE_CERTIFICATE；它不证明原4d手机包证书兼容，也不覆盖4d原APK到新APK再显式激活组合。旧ADB255、旧系统ANR、新API34 seed超时各自未定因。全v1.2、真机UX、性能和商业分发未完成，不编整体百分比。

[上一交接原文](https://github.com/supercubegame/todo-pocket-android/blob/10531cfeaec41f464d81027a575a4d9c1d8b9501/HANDOFF.md)保留42f2、4281与28ee目录隔离历史；[7920验收与候选身份](https://github.com/supercubegame/todo-pocket-android/blob/12a9b7779dca1cd2477c8aee1d00a54d1698a686/HANDOFF.md)保留六源文件和旧完整隔离验收；[十一文件授权与原21命令](https://github.com/supercubegame/todo-pocket-android/blob/9a6c72f8c67e2ae3520398833dc1ace7bcfcddf4/HANDOFF.md)。已提交Actions自行运行，不表示助手在对话结束后继续开发。
