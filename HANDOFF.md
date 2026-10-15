# 口袋待办：当前接续入口

2026-10-15 19:12继续轮。当前隔离候选已提交并精确核验，CI尚未验收。没有新APK、产品推送、合并、发布或手机操作。单分支一个写入者；新账号独立授权GitHub，不假定继承沙箱/记忆/技能。

## 首要动作：读5df73a自己的首轮CI

[修复提交5df73a51e744646adda4a161d929a97a2c1c3109](https://github.com/supercubegame/todo-pocket-android/commit/5df73a51e744646adda4a161d929a97a2c1c3109)，[CI38725988182](https://github.com/supercubegame/todo-pocket-android/actions/runs/38725988182)，run53、push、attempt1、check suite104941307363，最近读取in_progress。不能使用e44旧验收替代本候选。

只更新既有隔离分支ci/shortcut-storage-preflight-4d8742的.github/workflows/shortcut-storage.yml。17939字节，blob577434a7442eb5321456492445f5eebbc8efc815，SHA256 bb4582619bfedac974f7ba13e0958722c4f4fc80fe2cb802ab48e5c810b4e421。本地、写入响应、独立不可变目录核验一致。无待处理安全确认。

修复仅给既有verify_shortcuts.py主机Activity声明补public boolean isFinishing(){return false;}，不修改产品Java、不修改设备测试、不提高预算、不取消旧检查。新增callback_shape_selftest使用原syntax_selftest函数及完整候选，原声明应因isFinishing缺失红灯，修复声明应绿灯，整条声明省略必须再次红灯；精确逆向证明除这一声明外未变化。它置于本selftest行为检查之前，减少同类编译错误晚发现。不是提前到全部21命令之前，也不是实际Android模拟行为。

本地用真实JDK及MainActivity继承Activity的有限声明探针复现同名缺失RED、最小GREEN、整声明省略RED。该本地验证不是完整checkout或Android；完整候选语法和全部原21门在本轮CI运行。保留5f9dab全部50个run脚本(host28/device11/report11)、原步骤边界/环境/命令/预算/失败；逆向materializer和shell语法检查通过。hook SHA256 6a611db79e123b9b47e65bba40e104c1c8c40420b9431f1b62900b3f3f91a1e2。

## 5f9dab原失败已读取，不是产品故障证据

[原CI38704367280](https://github.com/supercubegame/todo-pocket-android/actions/runs/38704367280)的host116319985587失败，device116323622777跳过，report116323621265失败。没有无改动重跑。第21命令python3 tools/verify_shortcuts.py selftest，一次、300秒、31.432721861999994秒返回1、未超时。

[命令收据2/3](https://github.com/supercubegame/todo-pocket-android/runs/116323591270)、[完整失败日志3/3](https://github.com/supercubegame/todo-pocket-android/runs/116323597997)已读取。首次实际失败链selftest -> lifecycle_shape_selftest -> compile_with(STUBS) -> syntax_selftest：MainActivity缺少isFinishing()，1个编译错误。前面9条javac错误属于故意使用更旧生命周期声明的RED对照，不能误称9个新故障。

新callback实际方法/真实JDK执行器/ZIP加明确Android/DB替身的9故障检查通过；producer-consumer 4/20、JDK AST整调用省略、原queue 4/16和12故障、原life执行17断言/13故障/3整谓词变异、原report 4/76均已在CI stdout读取到通过。随后全候选主机声明缺失导致未进入真实Android构建/设备运行，回调场景仍未设备验收。

原host21 stdout4779字节，SHA2561361ae60fdc9f1f56bc8b9114f645fcd2a7ea49cefd7d6bf921dc6d975b09a4f，blob9485ff8ef6f96e0c55a192b6cfe3cc0fbd6505c3；stderr2428字节，SHA25605689668ba368b9426808a4184d3020e559b8bff3a2bbfcc3014095bb4a03989，blobe1f9ac256384af791e77b110925a3d2aa22e23cf。完整integration failure log9478字节，tail_is_partial false；artifact11958710435未下载。

5f9dab设备候选84765字节/blobc6b3c13abf01a6b2ebbb99d15231ec8041e8adc2/SHA256433936ddc5d8e4a4cbe929953fe719f0d369549781c8d36f100f06d81f7bca6d。verifier287409字节/blob7a5f55f8e2beba032986dc082469837e60afdf19/SHA25604c0462b14a7dcf355b88e28b9732308e4762eff537d008c6a66573ce6930582。四产品Java与e44相同。

## 最新完整验收仍e44b83

[CI38691647981](https://github.com/supercubegame/todo-pocket-android/actions/runs/38691647981)八作业/检查全通过，完整21项均一次、300秒、无超时；实际API26/API34、原始seed/reopen、life3和queue2、9字段严格报告、启动与激活双库独立回放及精确读回已验收。报告修复已通过，不能再写pending。

[API26](https://github.com/supercubegame/todo-pocket-android/runs/116284078080)、[API34](https://github.com/supercubegame/todo-pocket-android/runs/116284084079)。[上一版不可变交接](https://github.com/supercubegame/todo-pocket-android/blob/916eef006980712b94451adaf48936bab1878efe/HANDOFF.md)保存完整e44主机/源码/DB/流摘要、5f9dab实现及更早失败链；其5f9dab pending由本文替代。

## 回调场景的实际边界

5f9dab新增activationCallbackLifecycle，同一主线程回合触发真实requestShortcutActivation，等待真实screen io尾部Future完成，核对busy及plan/dialog未接管、恰一新增完整ZIP，真实finish并核对isFinishing，回合结束后允许回调，再检查退出及历史/备份完整、重开一致。finish先于callback dispatch，不保证onDestroy先于callback；不是prepare/SQLite commit执行中，不是进程杀死、触摸手势、手机或覆盖升级。固定fixture主线程等待2秒为安全截止，不是性能基准，失败先读原证据。

新日志族ACTIVATION_CALLBACK_PASS prepare_complete_finish_before_delivery_exact，seed1/reopen0，producer与consumer均强制解析，原9字段schema不扩展，完整原始流保存。旧测试只在try/finally内恢复旧producer/consumer/fixture，实际报告仍严格新入口。

## 剩余顺序与约束

先验5df73a本候选的完整21、实际API26/API34新场景、完整报告/双库，失败读首错后最小修复。之后补真实prepare/commit执行中退出、稳定签名旧APK覆盖升级、AGENTS/CLAUDE同文且不超200行，最终产品完整集成/21主机/原子非强制推送/精确远端/同最终提交双API和升级，再交付新APK。

产品最近核验仍3a5a17e1fdc570c73804007cd9a4d2ef36c0966b，近期产品推送0；手机仍4d8742阶段预览。ADB255/ANR根因未证实。其他功能、照片/EXIF/输入法/大字体、性能、存储失败、商业签名和分发未全验，没有可靠整体百分比。文档不能代替代码交付，旧绿灯不能验收新候选。

沿用[十一文件授权与原21命令](https://github.com/supercubegame/todo-pocket-android/blob/9a6c72f8c67e2ae3520398833dc1ace7bcfcddf4/HANDOFF.md)：现有凭据、明确同意、先验证备份、普通启动不自动迁移、失败关闭；不清数据、不卸载、不操作手机、不启动外部应用、不合并发布。原UI片段缺IOException，不可覆盖修复后的完整类。重建依赖不可变工作流，不依赖短期artifact或沙箱。对话结束不表示助手继续开发。
