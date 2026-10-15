# 口袋待办：当前接续入口

2026-10-15 16:12批准接续。单分支一个写入者；新账号独立授权GitHub，不假定继承沙箱/记忆/技能。没有新APK、产品提交、合并或发布。

## 首要动作：读取5f9dab本候选首轮结果

[提交5f9dab662a363cf4b10285ee5f4024873261f4ac](https://github.com/supercubegame/todo-pocket-android/commit/5f9dab662a363cf4b10285ee5f4024873261f4ac)，[CI38704367280](https://github.com/supercubegame/todo-pocket-android/actions/runs/38704367280)，push、attempt1、run52、check suite104881894383。最近读取为in_progress，不能把e44旧绿灯当成本候选验收。

只更新既有隔离分支ci/shortcut-storage-preflight-4d8742的.github/workflows/shortcut-storage.yml。22672字节，blob e1699c740913a897c4d9109ded615edba82b46e2，SHA256 95c094aa0347b9730582e24ec33866c5227498162af4f4e30d848f84ae1448b1。本地、写入响应、独立不可变目录核验一致。用户安全确认已记录，原提交完全相同重试成功，没有待处理确认。

新增实际设备场景activationCallbackLifecycle：在同一个主线程回合调用真实requestShortcutActivation，通过真实screen io执行器尾部Future证明prepare工作及callback投递已完成；此时busy仍为true且plan/dialog尚未被界面回调接管。核对恰有一个新增备份及可读非空ZIP，调用真实finish并核对isFinishing，然后主线程回合结束允许回调执行。随后等待旧Activity/执行器退出，无迟到dialog/plan/attempt，schema3所有旧cells和备份字节不变，再重新打开核对历史。

边界必须精确：finish先于callback dispatch，不保证onDestroy先于callback，不是prepare/SQLite commit正在执行时退出，不是进程杀死，不是手机或覆盖升级。测试主线程等待上限2秒是用于固定fixture的安全截止，不是性能基准；若超时先读原失败，不提高预算掩盖。反射触发实际方法，不是触摸手势验收。产品Java未改。

新日志族：ACTIVATION_CALLBACK_PASS prepare_complete_finish_before_delivery_exact，seed恰1、reopen恰0。实际producer和consumer都强制解析它，保留原9字段schema，原始流包含新记录，不再新增序列化字段导致旧契约不兼容。旧测试仅在try/finally内恢复旧producer/consumer/fixture，实际设备和报告走新入口。

本地主机验证：原缺少新族RED；producer->JSON->consumer 4正例/20精确拒绝反例；旧入口整新族省略见证；JDK AST真实seed调用和整调用注释变异；从实际设备候选用JDK AST提取方法后，在真实Java Executor和真实ZIP、明确Android/数据库替身上执行，9故障反例；整历史/备份断言省略变异先过好输入，再被坏备份接受见证抓住。不是实际Android通过，也未运行本地完整checkout的21项。完整集成及Android声明编译由本轮CI验收。

工作流逐字恢复e44全部46个run脚本(host26/device10/report10)，保留步骤边界、环境、原命令/预算/失败。materializer和设备片段逆向还原及shell语法检查通过。hook SHA256 730341b71011fbb0be8c0efe8279287638501473a3a7bbea3cce4b621ec956bf。

## 最新完整已验收：e44b83

[CI38691647981](https://github.com/supercubegame/todo-pocket-android/actions/runs/38691647981)绑定e44b83bd4f25f2e083ecca5f6420af9400916105。八作业/检查成功，包括实际API26/API34构建、设备、聚合报告和精确读回。报告契约修复已经通过，不再pending。

[主机收据1](https://github.com/supercubegame/todo-pocket-android/runs/116282319588)、[主机收据2](https://github.com/supercubegame/todo-pocket-android/runs/116282323997)完整读取：21原命令均一次、300秒预算、return0、无超时。host21耗时136.96486437399994秒，stdout17486字节，SHA256 471884cb75e4dcb1a32db228205dc30dc6f081bde8590668fe3192bcf64d6252，blob cc15424cf64a449827a02a4ee2ba7b24496c33cd，stderr空。artifact11952602899未下载，未直接读取完整host21 stdout；4/76报告自测本地已读，CI集成成功，但没有单独读取其完整stdout。

[API26完整证据](https://github.com/supercubegame/todo-pocket-android/runs/116284078080)、[API34完整证据](https://github.com/supercubegame/todo-pocket-android/runs/116284084079)的完整output JSON及seed/reopen原始流均直接读取。seed旧97、启动6、激活8、life3、queue2；reopen旧16、启动2、激活2、life/queue空。原真实旋转/重建/完成后退出和准备/确认排队退出均通过。

两端seed6480字节，API26 SHA256 341726c194fb862611cf054c0cd7f5700303d910f64fdecaaf85619fac5fbbb6，API34 f96c31c3447feb7f9478b230bc1b5914510b7748e8d15cfcd7071b761221e1cb。reopen1188字节，API26 41995c1b653dbfa8b122c117c2664ee633c7871cab26a76f128d7f8f7a0b9890，API34 68b60879a9cc7fc268ec6a5207c0479a1ee68fb2606332dc109058bd4a009a0e。

启动和激活双库在seed/reopen均独立SQLite回放通过，18张旧表typed cells一致；启动关系[[7,10],[8,10]]，激活关系空。旧cells SHA分别a670d8086e51e17d9e382d2fead7f2684f9cce91daf96c7d7c23b0139ff1455a与92d1a6d935f75c43fed428c091ede652ef884dd2b9d80a538e099f4d3afce23b。DB/oracle身份延续上一接受基线，详见完整API输出。不能说设备WAL已经发生。

e44 verifier273834字节/blob f459cc488473d36216eeca017f1d1868ccc5ceef/SHA256 fd11b2c5e201f2a0a6cf25e86c5e9644d78db8743ff53c1b5a8a6b0e6ee63a0a。DeviceTest81260字节/blob00c19198bc59dcc9a8f3911da394ee3bd686a339/SHA256cb9ca2c3f14e0abee11b032637a78392d2eb82a1b86ab2aa8c34a441f1042372。四产品Java与512263相同。

## 历史失败及完整恢复链

[上一版交接](https://github.com/supercubegame/todo-pocket-android/blob/cb3f3f49b0f4b375459cf78c2def7c5adb099a9f/HANDOFF.md)保存bfb原报告字段失败、e44修复细节、512263及更早原失败、源码身份和完整恢复链接。其e44 pending由本文替代。bfb仍是设备PASS、报告FAIL的历史事实，未无改动重跑或抹除。

## 继续顺序与未完成边界

先读5f9dab首轮21项、实际双API新场景及完整报告/双库。失败先定位第一实际错误，不用重试隐藏。然后继续真实prepare/commit执行中退出、稳定签名旧APK覆盖升级、AGENTS/CLAUDE同文且不超200行，最终产品完整集成/21主机/原子非强制推送/精确远端/同最终提交双API及升级，再交付新APK。

产品最近核验仍3a5a17e1fdc570c73804007cd9a4d2ef36c0966b，近期产品推送0；手机仍4d8742阶段预览。ADB255/ANR根因未证实。其他功能、照片/EXIF/输入法/大字体、性能、存储失败、商业签名和分发未全验，没有可靠整体百分比。文档不能替代代码交付，旧绿灯不能接受新候选。

沿用[十一文件授权与原21命令](https://github.com/supercubegame/todo-pocket-android/blob/9a6c72f8c67e2ae3520398833dc1ace7bcfcddf4/HANDOFF.md)：现有凭据、明确同意、先验证备份、普通启动不自动迁移、失败关闭；不清数据、不卸载、不操作手机、不启动外部应用、不合并发布。原UI片段缺IOException，不可覆盖修复后的完整类。完整重建依赖不可变工作流，不依赖短期artifact或沙箱。对话结束不表示助手继续开发。
