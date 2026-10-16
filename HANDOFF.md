# 口袋待办：当前接续入口

2026-10-16 17:53继续轮。9e938双API完整崩溃栈已读并定位测试观察器错误。已提交最小测试连接修复7920bbe3，独立远端内容一致，首轮CI正在执行。未修改产品运行Java、未关闭数据保护、无新APK、产品推送、合并、发布或手机操作。

## 首要动作：读取7920bbe3首轮完整验收

[修复7920bbe315a61cdfd7c8af78cc54f30cee254da8](https://github.com/supercubegame/todo-pocket-android/commit/7920bbe315a61cdfd7c8af78cc54f30cee254da8)，[CI38884051157](https://github.com/supercubegame/todo-pocket-android/actions/runs/38884051157)，run62、push、attempt1、suite105375795571，最近读取in_progress。提交2026-10-16T09:57:56Z，tree d3df7a4b290ee613246637435790d11722cf803b。

只更新ci/shortcut-storage-preflight-4d8742既有.github/workflows/shortcut-storage.yml，21062字节，blob095664be07cfc453e32f259ce0b971d453d10a0f，SHA256 c591e61ecee350109876d270e413efce1e698adaa25fcafdfa06a375ba8117bd。本地、写入响应及独立不可变目录相符。没有待批准安全事项。

## 已证实的是新诊断运行中的测试错误

[API26完整栈116902915904](https://github.com/supercubegame/todo-pocket-android/runs/116902915904)：3387字节，SHA256 82ab9b8611db2b2ec6f937ae88692d429e4e4fad48bc1c6cf693a942a7cde4f2。[API34完整栈116902978986](https://github.com/supercubegame/todo-pocket-android/runs/116902978986)：3417字节，SHA256 00540a0923db49c6d3e079241e4af42d82cb492e2026282d24f2a6a3b2b557e1。两者完整读取，绑定9e93888af2ed2450a6d1077379edfc3595913f04/run38877832949/attempt1。

两端都是实际preview进程的线程池FATAL EXCEPTION：Schema4DeviceTest测试Provider.engineDigest第895行调用AppDatabase.getReadableDatabase，经Schema3Store及startupDatabase进入schema3保护，因当前DDL已写到schema4抛出IllegalStateException: Startup schema changed; preserve database。测试第899行把它包成AssertionError抛出，逃出产品只捕获Exception的work，导致进程崩溃。栈同时包含Schema4Store.confirmActivation149、activationDigest81和AppDatabase.confirmShortcutActivation167，证明已在真实确认路径。不能通过放宽产品schema保护或笼统捕获Error修这个测试错误。

[API34完整instrumentation](https://github.com/supercubegame/todo-pocket-android/runs/116903094226)还保存原97条SHORTCUT标签、6条STARTUP_NATIVE标签后相同失败；API26仍只有Process crashed：[原始流](https://github.com/supercubegame/todo-pocket-android/runs/116903089268)。API34采集收据116902984348已完整读取，wait0，logcat结束255但已保留3417字节完整栈，原测试return1、observer已结束。这个logcat结束码不等于旧ADB255问题根因已解决。

[实际AppDatabase源码窗口](https://github.com/supercubegame/todo-pocket-android/runs/116417941553)也已读取：139068字节、SHA256 f3be495c2d4ca175b10b446eacab69d46d2588c8fdc74eecb34c0c84f8ac886c，startupDatabase198至204只允许已有开放schema3连接。此产品源码身份与10b原候选一致。10b首次没有保存崩溃栈，不能把9e938新日志冒充10b原现场；新诊断已复现并证实上述机制。

## 最小修复及证明

仅在activationPostDdlScenario内，在确认前通过原screen执行器取得同一facade的既有SQLiteDatabase连接，后续测试Provider在真实worker内直接读取这份连接的inTransaction和version4。保留所有原断言、两个提交/回滚结果、原5秒观察与10秒释放预算、Provider清理、旧cells和备份精确保留、重开及原完整测试。没有新增产品测试入口，也没有在迁移后绕过产品保护去继续业务写入。

主机闸门改为JDK AST提取实际候选AppDatabase.startupDatabase方法放入执行夹具，而不是原先永远返回DB的过宽替身。每次先把实际测试方法还原旧调用，要求出现同一个schema保护错误RED，再执行修复后的实际方法/双场景调用者GREEN及原13故障、2整段断言省略、1调用省略。本地已通过。当地startupDatabase输入为从不可变源码窗口抄取的明确夹具；CI读取实际完整AppDatabase文件并经AST提取。Android/SQLite仍为替身，真实JCA、线程池、latch、文件和Java实际方法执行不能冒充Android验收。

本次恢复9e938全部70个原脚本(host37/device17/report16)并逐项本地比对，再增加测试组装修复步骤。原21主机命令、300秒预算和作业预算不变。保留崩溃采集；同时修正诊断wrapper的成功条件：原测试成功且采集进程正常结束时，空crash缓冲区不再把它判失败，仍记录NO_CRASH_BYTES_NOT_VERIFIED，不据此证明没有崩溃。原测试非零必须原样返回；等待失败/采集超时/超限仍失败。新增原成功且零崩溃字节的行为对照，原真实子进程1正例、5反例及整段失败守卫省略测试全部保留并通过。这里变更一个既有诊断脚本的返回语义，不宣称所有脚本执行字节完全未变。

本地文件/home/user/work/startup-ui：postddl-connection-repair.py、build-postddl-connection.py、postddl-connection-device.java、postddl-connection-hook.py、postddl-connection-local.log、build-connection-workflow.py、connection-workflow.json、connection-candidate.yml、connection-loader-emitted.sh。跨账号从不可变GitHub工作流及校验载荷恢复，不假定这些路径存在。

## 基线、历史证据与后续

最新完整验收隔离基线仍fa12481ce8013304aa47d9d848025496ab1242d3，[CI38865507655](https://github.com/supercubegame/todo-pocket-android/actions/runs/38865507655)。原21主机、双API seed/reopen、确认消费同意前退出、双库独立回放及汇总已复核。不能用旧绿灯接受7920。

[上一份不可变交接a0d08a39](https://github.com/supercubegame/todo-pocket-android/blob/a0d08a39f8b49c53f9ab237901281a16fc183a4d/HANDOFF.md)保留10b原失败及完整21主机收据、4a只读恢复成功、两个原归档身份、原实际Android构建、9e938诊断设计。其9e938 pending和未知根因由本文替代；9e938完整21主机回执本轮尚未重新逐项读取，不编造新主机结论。

[更早交接8f279530](https://github.com/supercubegame/todo-pocket-android/blob/8f279530eea0b2c5b1aa3187f41f0dd9894f0a3d/HANDOFF.md)保存fa全部身份、10b两场景设计与旧链入口。postDDL场景只涵盖正常finish下最终摘要检查点的提交/回滚，不是任意SQL点、进程强杀、断电；最终独立数据库回放不等于中间两场景单独导出回放。

下一步：读取7920原21完整主机收据、双API完整seed/reopen、两个postDDL标签、双库独立回放、汇总和采集收据；失败先读首失败而非重跑。通过后重点转已批准产品集成、AGENTS/CLAUDE同文不超200行、完整21主机、原子非强制推送、独立远端核对、同最终产品提交双API和稳定签名覆盖升级，最后交付APK。不继续任意扩展无关测试。

产品最后核验3a5a17e1fdc570c73804007cd9a4d2ef36c0966b，手机4d8742预览，近期产品推送0、无新APK。旧ADB255/ANR根因仍未证实，剩余功能/真机UX/性能/商业分发未全验，无可靠整体百分比。

沿用[十一文件授权与原21命令](https://github.com/supercubegame/todo-pocket-android/blob/9a6c72f8c67e2ae3520398833dc1ace7bcfcddf4/HANDOFF.md)：既有凭据，明确同意，已校验备份先于迁移，普通启动不自动迁移，失败关闭，不清用户数据、不卸载、不操作手机、不启动外部应用、不合并发布。单分支一个写入者；对话结束不表示助手继续开发。
