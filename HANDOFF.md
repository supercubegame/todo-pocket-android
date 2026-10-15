# 口袋待办：当前接续入口

2026-10-15 11:10批准接续轮。只允许一个写入者；新账号独立授权GitHub，不假定继承技能、记忆或沙箱。不是产品交付、新APK或发布声明。

## 第一件事：读取512263本次修复自己的验收结果

[修复提交51226379913c352b806fa071e46cbd8f5dbfca01](https://github.com/supercubegame/todo-pocket-android/commit/51226379913c352b806fa071e46cbd8f5dbfca01)，[CI38675713479](https://github.com/supercubegame/todo-pocket-android/actions/runs/38675713479)，push、attempt1、run49、check suite104804690092。最近读取时主机116228724414正在跑前置后端检查；尚无本候选完整主机或双API结论，不能借用e9bf绿灯。

用户11:10明确批准后已记录安全批准并原样重试成功，无待处理安全确认。仅修改隔离分支ci/shortcut-storage-preflight-4d8742既有.github/workflows/shortcut-storage.yml。19281字节，blob f4c7d7cb8782397b364e446cd520805b2a3f935f，SHA256 f76acefdc2fa5bc4ce83bcceea4ab5d990283aeae4322f99b99a82d64aea8a77。本地、写入响应、独立不可变远端目录身份完全一致。

修复仅为既有verify_shortcuts.py生成内容增加Activity四个方法及Resources、Configuration、ActivityInfo声明；不是产品运行Java修改，也没有改05fc设备Java。保留旧声明红灯，增加完整实际源码的声明RED/GREEN及八个逐项省略对照。实际Android编译仍使用真实SDK，不使用主机替身。

另外把此前本地执行测试接入永久selftest：JDK AST从实际候选DeviceTest抽取activationLifeNeed、awaitActivationRetired、activationLifecycle三方法，真实Java执行，Android为明确替身。三场景、17断言、13故障反例和三个整段谓词省略变异；每个省略变异先过正常输入，再证明漏掉对应坏数据，同一检查器识别。已在本地通过，完整候选CI尚未读到结论。

工作流逐字恢复不可变05fc的34个run脚本，host20/device7/report7，保留步骤边界、环境、原命令/预算/首失败，只追加声明和实际方法检查。materializer精确逆向还原和shell语法本地通过。新hook SHA256 cc54169fe5b1dc5815f33020c0e2debb49067269eb7261eae3beb72c0218cb44。原21主机命令各一次、300秒不变。

## 05fc已经失败，不再pending

[原失败CI38663135001](https://github.com/supercubegame/todo-pocket-android/actions/runs/38663135001)，提交05fc58b7c50b243efa0bd72ffeb5d022de2b4f78。首20主机通过，21为python3 tools/verify_shortcuts.py selftest，attempts1、budget300、elapsed22.25180070099998秒、return1、无超时。实际失败是activation_shape_selftest调用compile_with(STUBS)时七条javac缺声明错误；不是产品运行或设备故障。设备跳过，报告缺结果是级联，未无改动重跑。

缺失的是isDestroyed、getResources/getConfiguration/orientation、setRequestedOrientation、recreate、ActivityInfo两个方向常量。前面的19条旧声明错误是预期RED，不是19个新缺陷。先前解析器、线程、DB回放、真实report/SQLite及触摸检查已输出PASS。

[命令回执](https://github.com/supercubegame/todo-pocket-android/runs/116191526482)、[完整4792字节stderr](https://github.com/supercubegame/todo-pocket-android/runs/116191532086)已直接读取。stdout8292字节/SHA256 eec4063a835df1a83a548e3773cb3982f2f820afacfc40177e78a2e1857a3407，stderr SHA256 3eac26dc4bcaf3bd5620a4d7589aa63f138831a6253f87d3bd10279cc292a8f6。[原artifact11940311278](https://github.com/supercubegame/todo-pocket-android/actions/runs/38663135001/artifacts/11940311278)未下载，15426字节完整集成日志只读到尾部，不能称全日志已读。

## 真实生命周期场景的范围

05fc设备代码在备份预览完成、已勾选、尚未确认时依次测试真实方向变化、显式recreate、finish。确认Activity实际替换、旧Activity销毁、旧启动及screen执行器退出；调用保留的旧确认监听器，要求schema3完整类型化历史及备份原字节不变。旋转还要求资源orientation确实改变。新增ACTIVATION_LIFE_PASS精确seed三项，reopen零项；原所有标签与流保留。

这些真实Android场景尚未取得通过结论。不是prepare进行中、commit进行中、回调排队销毁、进程杀死、手机或覆盖升级验收。新修复的主机替身执行不能代替设备结果。

## 最新已接受隔离候选仍为e9bf

[e9bf CI38627964450](https://github.com/supercubegame/todo-pocket-android/actions/runs/38627964450)八作业/检查全部通过，全21命令均一次/300秒/return0/无超时。host21耗时69.119621789秒，stdout8806字节/SHA2566615c7634b4ea2fade135a52e4ad7091f05fabb451c30409000f4490a139a053，stderr空；artifact11925366534未独立下载。

[API26完整证据](https://github.com/supercubegame/todo-pocket-android/runs/116078111640)、[API34完整证据](https://github.com/supercubegame/todo-pocket-android/runs/116078121024)完整JSON、seed/reopen原流和启动/激活双库回放已读取。每端旧标签97/16、启动6/2、激活8/2；18旧表保持精确，启动关系[[7,10],[8,10]]，激活空关系。当前停止快照没有登记WAL，不能把主机WAL对照说成设备WAL。

[完整上一版交接及源码/数据库摘要](https://github.com/supercubegame/todo-pocket-android/blob/ac253a6987909f07274d517d941944d6f0be7fa4/HANDOFF.md)永久保留，其05fc pending由本文替代。[更早交接](https://github.com/supercubegame/todo-pocket-android/blob/b2bbe165e47cb674a65f1e2303985b4a0c6580bb/HANDOFF.md)保留e484、cc06及c91原失败证据。不得拿旧验收接受新候选。

## 接续顺序与未完成边界

先读512263自己的首结果及21完整回执。红灯先读第一条实际错误，保留原输出和预算，最小修复，不靠重试。绿灯后继续API26/API34真实构建、三生命周期场景、全部旧回归、双库独立回放和完整原始流/源码身份。随后补准备/提交/回调期间销毁、稳定签名旧APK覆盖升级、AGENTS/CLAUDE同文且不超200行、产品工作流集成、原子非强制产品提交及精确远端读回、同一最终产品提交的双API和升级，再交付APK。

产品最近核验仍3a5a17e1fdc570c73804007cd9a4d2ef36c0966b，近期产品推送0；手机仍4d8742阶段预览。没有新APK、产品交付、合并或发布。ADB255/ANR根因未证实；剩余功能、照片/EXIF/输入法/大字体、性能、存储失败、易用性、商业签名和分发仍未全部验收，不给虚构整体百分比。

原UI片段缺IOException，已提交不可变修复补齐，不可用原片段覆盖完整产品。完整重建依赖不可变工作流，不依赖短期artifact或账号沙箱。沿用[十一文件授权与原21命令](https://github.com/supercubegame/todo-pocket-android/blob/9a6c72f8c67e2ae3520398833dc1ace7bcfcddf4/HANDOFF.md)：现有凭据、显式同意、先验证备份、普通启动不自动迁移、失败关闭；不清数据、不卸载、不操作手机、不启动外部应用、不合并发布。对话结束不代表助手继续开发。
