# 口袋待办：当前接续入口

2026-10-14，解析器组合修复轮。不是发布、全部完成或新APK声明。单分支一个写入者；新账号须独立授权GitHub，不假定继承技能、记忆或沙箱。

## 当前候选与下一步

最新隔离候选：[e8c31fdd](https://github.com/supercubegame/todo-pocket-android/commit/e8c31fddb720e120fbf1a14cc1044183fab8425e)，[运行38554785947](https://github.com/supercubegame/todo-pocket-android/actions/runs/38554785947)，push、attempt1。最后观察主机原后端验证执行中；尚无本候选完整21主机、Android或设备验收结论。

分支 `ci/shortcut-storage-preflight-4d8742`，修改现有 `.github/workflows/shortcut-storage.yml`，通过不可变载荷重建六文件产品候选，不是产品分支提交。工作流12591字节，Git blob `ad52d74c2552d0da988dfd11d0a81475f017de6f`，SHA256 `43a6393a77dcf8b09e2fb69e3937803e8f2002cc66a16178bf74b65818a644df`。本地、写入返回及独立不可变目录读回一致。

第一步读本运行全部作业与完整分片主机回执，核对六文件身份、原21命令一次/300秒/完整输出，再读实际API26/API34构建、原113契约、八项默认启动检查、十项显式激活检查及汇总。缺失或跳过不是通过，旧绿灯不能接受新候选。红则保留首次输出并最小前向修复，不重跑掩盖。

产品最近核验仍为 `3a5a17e1fdc570c73804007cd9a4d2ef36c0966b`，本轮产品推送0；手机APK仍4d8742阶段预览。没有新APK、合并、发布、凭据或手机操作。

## 本轮实际失败与修复

[de8运行38547762007](https://github.com/supercubegame/todo-pocket-android/actions/runs/38547762007)已失败，不再pending。第一轮后端验证成功，第二轮完整UI候选原21主机中前20成功，第21 `python3 tools/verify_shortcuts.py selftest` 退出1，attempt1、300秒预算、耗时5.387450970000032秒、未超时。两个设备作业未执行。

这是验证脚本组合故障，不是已经证实的Android产品故障：native_startup_parser_selftest使用全局parse_phase；追加activation解析层后全局函数被覆盖，旧legacy-only见证先收到activation缺失错误，原精确断言因此报 `wrong native RED`。新activation解析4正向/36负向、十个Java调用遗漏对照及12行为/3变异此前均已通过，但它们分别通过没有证明组合通过。

[原失败完整回执及六文件身份](https://github.com/supercubegame/todo-pocket-android/runs/115804266703)，[完整集成日志尾部](https://github.com/supercubegame/todo-pocket-android/runs/115804274327)，原host归档11886321117。host21 stdout233字节/SHA256 `b07f84f208898f98cbbc3c0a83570e6e756301a70e561c2b8313e58ca50db679`，stderr1737字节/SHA256 `a23f9f2fad3478361998bfa832cef654f03b2eeb506275835749b0da5bc1722d`，完整集成日志3790字节，未截断。原运行未重跑或取消。

最小修复：两个层专属自测在函数定义时捕获自己的fixture与parse_phase；生产顶层解析器仍同时要求所有新旧标签，未改判词或放松顺序。新增永久组合检查：4个完整正例、36个逐标签遗漏反例、绕过startup/activation的2个有正常输入见证变异，以及恢复错误全局绑定的1个变异；必须分别被目标断言拒绝。新工作流在真实完整候选中先复现旧RED并归档，再修复并执行组合GREEN，随后完整跑原21命令。

本地已执行真实两份扩展的同命名空间组合：精确复现 `wrong native RED`；修后native 4正向/32负向、activation 4正向/36负向、组合4正向/36遗漏/3变异通过；真实JDK解析8+10个调用及对应18个遗漏变异通过；后续再次覆盖全局函数与fixture不能劫持两个专属自测。实际工作流载荷展开、脚本变换、发出的集成块RED/GREEN、所有shell语法均通过。旧日志解析底层在本地为明确替身，不是完整仓库或Android验收；完整验证由本次CI负责。

## 已实现但尚未验收的显式激活UI

TodayScreen显式入口、已验证备份预览、内部备份随卸载/清数据消失的提示、勾选后确认、取消、重复/过期/关闭/finishing保护。普通启动不自动迁移。确认成功由MainActivity重建整个Activity并弃用旧schema3 facade；失败关闭旧界面，明确格式可能已变，不能声称数据未变。

Schema4DeviceTest使用固定进程内 `schema4-activation-ui.db`，无Intent任意路由，不打开手机数据库。8项seed+2项独立进程reopen：预览仍schema3、未勾选不提交、取消保留备份和历史、旧确认失效、备份变化拒绝、成功真实重建且历史精确不变、重复入口无操作、手机库不存在、独立进程历史精确及手机库不存在。对话框实际窗口观察、可见边界单次DOWN/UP。真实Android十项尚未通过。

前一轮两个独立问题已分开修复：cbbc提交丢两处嵌套转义，a37固定原文件身份并精确还原；实际MediaRepository构造函数throws IOException而本地替身曾漏声明，de8保留真实签名编译RED并同步UI声明与替身。e8继承二者，不删除原失败。详见[前一完整检查点](https://github.com/supercubegame/todo-pocket-android/blob/295085bb3804c6675a474704981c0117f4b748cc/HANDOFF.md)。

## 已验收基线与余下交付

[87d3运行38539002887](https://github.com/supercubegame/todo-pocket-android/actions/runs/38539002887)六作业成功，包括实际双API构建与设备测试。已读回执后半及API26原生seed标签，a87只读取证验证21命令；未逐项完整审计两档全部原始快照，且87d3不含新十项激活UI，不能替代当前候选验收。

先收口显式UI完整主机/双API，再补旋转、快速退出、确认中销毁、报告侧新UI数据库独立回放；现有替身不证明真实生命周期。之后同最终产品提交完成旧APK稳定签名覆盖升级、AGENTS/CLAUDE一致更新、产品工作流、原子非强制产品提交与逐字读回，验收后才给新APK。再处理剩余功能、真实照片/EXIF/输入法/大字体、性能、存储失败、易用性、商业签名及分发。没有可靠总完成百分比。

沿用10月11日18:34原十一文件授权；[授权与21命令](https://github.com/supercubegame/todo-pocket-android/blob/9a6c72f8c67e2ae3520398833dc1ace7bcfcddf4/HANDOFF.md)。只用现有凭据；失败关闭，不清数据、不卸载、不启动外部应用、不操作手机、不合并发布。历史ADB255和ANR根因未证明，三字节媒体不证明照片兼容。

工程优化：新增解析层必须连同旧自测整体运行，不能分别绿后直接提交；本轮已把这一点变为永久组合断言。永久重建依赖不可变工作流，不依赖14天Actions归档或当前账号沙箱。下载包不是完整仓库/APK/技能备份。对话结束不代表助手继续开发。
