# 口袋待办：当前接续入口

2026-10-16继续轮。当前隔离候选6c3cb63已提交、精确远端核验、完整21主机通过；最近读取API26/API34仍在设备环境准备，尚未设备验收。没有新APK、产品推送、合并、发布或手机操作。单分支一个写入者；新账号独立授权GitHub，不假定继承沙箱、记忆或技能。

## 首要动作：读6c3cb63自己的双API结果

[提交6c3cb63beb685b63e15dc8b121863be3e9ab169d](https://github.com/supercubegame/todo-pocket-android/commit/6c3cb63beb685b63e15dc8b121863be3e9ab169d)，[CI38819992690](https://github.com/supercubegame/todo-pocket-android/actions/runs/38819992690)，run56、push、attempt1、check suite105205338081。host116713967441成功；API26 job116717384983、API34 job116717384964最近读取in_progress，构建和设备步骤当时尚未完成。不能用e44旧验收替代当前候选。

只更新既有隔离分支ci/shortcut-storage-preflight-4d8742的.github/workflows/shortcut-storage.yml。22637字节，blob7b613127b35bc2ba2fb182d786b28fbdd3d73172，SHA256 a643462b871d9753c65f56c7051d4c1ad98241707a34664dcaa8ffbb7e267d53。本地、写入响应、独立不可变目录核验一致。无待处理安全确认。

修复仅在实际activationCallbackLifecycle中，原awaitActivationRetired之前增加有截止时间的销毁状态观察：5秒截止，主线程读取isDestroyed，未销毁时在仪器线程睡眠10ms，然后必须断言已销毁，再运行原退休断言。finish只调用一次，不重试业务动作，不删除旧断言。原300秒主机命令预算及作业预算不变，但确实新增最多5秒观察窗口，不能称没有新增等待。共享awaitActivationRetired不改，产品运行Java不改。

永久主机闸门用JDK AST提取实际设备方法，显式Android替身模拟finish后第二次主线程观察才销毁。原39dd方法必须因activation lifecycle old Activity destroyed红灯；修复应绿灯；never-destroyed必须命中activation callback destroy observation deadline。保留原14故障、现15故障及完整备份保留/目录布局断言省略变异。CI使用实际BackupArchive和MediaRepository；本地烟测的传输和Android均为明确替身，不是Android证据。本地原RED、延迟GREEN、15故障、两种省略见证实际通过。53个原run脚本原样保留，只修改一个既有组装脚本；逆向及shell语法通过。组合hook SHA256 b0626423acaa0f09ac2d8bdc8c14757dedd5d812f7ecc026b406b2ab781635b4。

## 本候选完整主机收据已读

[收据1/2](https://github.com/supercubegame/todo-pocket-android/runs/116717360460)、[收据2/2](https://github.com/supercubegame/todo-pocket-android/runs/116717366030)完整读取。21项原命令均attempts1、budget_seconds300、returncode0、timed_out false。第21项python3 tools/verify_shortcuts.py selftest耗时122.64372875200002秒，stdout20932字节、SHA256 f88174bb1742617435e686422f0787c2cefb4a38b512a715cfe74bcb4ea71411、blob9eb36467839ab10b9cab707b7853f57b73e74567；stderr空。完整stdout尚未直接读取，不能把收据等同于逐行日志审计。

[host artifact12012741085](https://github.com/supercubegame/todo-pocket-android/actions/runs/38819992690/artifacts/12012741085)未下载。candidate DeviceTest86350字节/blob88b9e745e588c4c1df1346601ed90a29e49bc92f/SHA256 e75ea1025bcdc5615989e150e09811dbfab7e3238f06a717a821873f2b6f85d9；verify_shortcuts302252字节/blob71b82f50d037d7a5b2f673a9d7ec121e3db447eb/SHA256 0536c09dd2ad9140a1d56686ed57d3fd33a7386a3a9a41d3d5684851eb788289。

四个运行Java身份未变：AppDatabase139068/blob0aaa2875c9c445800f25a7a0caa594541a24bec3；Schema4Store39699/blob1b88780386f99597bfc34dd40457a5730f2f4cd6；TodayScreen30505/blobed6c200dc2e6c9f1541621467a182e2820fc1330；MainActivity40053/blob430d1627737df7b14b46d0a0fa60f2c794015ef6。

## 连续失败分开处理，保留首错

5f9dab在完整主机声明编译缺少isFinishing；5df73a仅补声明和原RED/最小GREEN/省略控制，主机及双Android构建通过。其实际双设备随后在activation callback exactly one completed backup失败。没有无改动重跑。

[e1b只读原始证据恢复CI38733808582](https://github.com/supercubegame/todo-pocket-android/actions/runs/38733808582)取回5df原host/API26/API34归档，校验身份及摘要，不运行产品或设备。实际Schema4Store.prepareActivation创建before-shortcuts-UUID.zip和verify-UUID目录；BackupArchive.Snapshot.close只删restore子目录，留下空verify根。原exact-one-new-entry假设错误。5df原日志未列具体新增路径，不能伪称原日志直接证明数量2。

[39dd修复CI38735556408](https://github.com/supercubegame/todo-pocket-android/actions/runs/38735556408)完整主机和双Android构建通过。它严格要求恰2个新条目：一个普通非符号链接ZIP、一个非符号链接空verify目录；完整ZIP及旧数据、备份字节断言保留。两端确实越过这些断言，但随后在原退休检查失败：[API26完整原始流](https://github.com/supercubegame/todo-pocket-android/runs/116431208714)、[API34完整原始流](https://github.com/supercubegame/todo-pocket-android/runs/116431215839)均已读取，首错activation lifecycle old Activity destroyed，awaitActivationRetired line999、callback line907。没有callback PASS、最终seed PASS或成功reopen/双库报告，status NOT_VERIFIED。报告callback complete ordered checks是缺失PASS的次生错误，不是设备首因。

主线程空闲并不保证异步销毁已完成；原日志不证明Activity永久卡住，也没有原始销毁耗时追踪。6c3观察修复仍需实际双API验证，不宣称产品生命周期根因已彻底解决。

## 最新完整验收仍e44b83

[CI38691647981](https://github.com/supercubegame/todo-pocket-android/actions/runs/38691647981)八作业/检查全通过，完整21项均一次、300秒、无超时；实际API26/API34、原始seed/reopen、life3和queue2、9字段严格报告、启动与激活双库独立回放及精确读回已验收。

[API26](https://github.com/supercubegame/todo-pocket-android/runs/116284078080)、[API34](https://github.com/supercubegame/todo-pocket-android/runs/116284084079)。[历史交接83a2b121](https://github.com/supercubegame/todo-pocket-android/blob/83a2b1211c58f8304642b3b4ce04481b3884f3c9/HANDOFF.md)保存5f原失败、5df提交身份及更早链；其中5df pending和单备份条目假设由本文替代。[更早e44完整身份](https://github.com/supercubegame/todo-pocket-android/blob/916eef006980712b94451adaf48936bab1878efe/HANDOFF.md)保留主机、源码、DB、流摘要。

## 回调场景边界及剩余交付

实际callback场景在同一主线程回合反射调用真实requestShortcutActivation，以真实io尾部Future和完整备份检查证明prepare结束且UI未接管，然后finish一次。finish先于callback dispatch，不保证onDestroy先于callback；不是prepare/SQLite commit执行中、进程杀死、触摸手势、手机或覆盖升级。原固定2秒Future截止未改。新标签ACTIVATION_CALLBACK_PASS prepare_complete_finish_before_delivery_exact要求seed1/reopen0，两端实际报告入口均解析，原9字段不扩展。

先读取6c3同提交双API原始seed/reopen、callback标签、双库独立回放及完整报告读回，失败保留首错再最小修复。之后补真实prepare/commit执行中退出、稳定旧APK覆盖升级、AGENTS/CLAUDE同文且不超200行，最终产品完整集成/21主机/原子非强制推送/精确远端/同最终提交双API和升级，再交付新APK。

产品最近核验仍3a5a17e1fdc570c73804007cd9a4d2ef36c0966b，近期产品推送0；手机仍4d8742阶段预览。ADB255/ANR根因未证实。其他功能、照片/EXIF/输入法/大字体、性能、存储失败、商业签名和分发未全验，没有可靠整体百分比。文档不能代替代码交付，旧绿灯不能验收新候选。

沿用[十一文件授权与原21命令](https://github.com/supercubegame/todo-pocket-android/blob/9a6c72f8c67e2ae3520398833dc1ace7bcfcddf4/HANDOFF.md)：现有凭据、明确同意、先验证备份、普通启动不自动迁移、失败关闭；不清数据、不卸载、不操作手机、不启动外部应用、不合并发布。原UI片段缺IOException，不可覆盖修复后的完整类。重建依赖不可变工作流，不依赖短期artifact或沙箱。对话结束不表示助手继续开发。
