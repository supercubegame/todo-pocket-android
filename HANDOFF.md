# 口袋待办：跨账号接续入口

2026-10-14 检查点。先重新读取分支与 CI；这是工程交接，不是 APK、完整源码备份或商业发布。单分支只允许一个写入者。

## 给接手助手的第一条消息

继续开发 supercubegame/todo-pocket-android。先读本文件及下方不可变历史交接，核对产品分支与候选工作流，再读最新运行的原始失败或成功回执。沿用已经批准的十一文件受控激活范围，不重建项目，不重复询问同一授权，不默认让我上传文件或运行脚本。按完整集成与原主机验证、实际提交并精确核对远端、同最终产品提交 API26/API34 验收推进。不能用文档或旧绿灯替代交付；不自动合并、发布、换密钥、启动外部应用或操作手机数据。

## 当前三个版本

- 产品分支 `feature/v1.2-activity-notes-ledger`：最近核验仍是 `3a5a17e1fdc570c73804007cd9a4d2ef36c0966b`。本轮没有产品推送。PR：https://github.com/supercubegame/todo-pocket-android/pull/4 。
- 候选分支 `ci/shortcut-storage-preflight-4d8742`：最新提交 `f763cbf133c2eb6d8eb877a9836b852c56b178c9`，只更新现有 `.github/workflows/shortcut-storage.yml`。文件 20883 字节，blob `decd15df701220640e05e207fce4d7b907931935`，SHA256 `3285e5ae6a109f804af1d7e6d586abbb3ec99498a15f89e39f38d5eaa5c3b770`；本地摘要、写入响应、独立不可变提交目录回读一致。
- 最新已交付手机包仍是 `PocketTodo-v1.2-preview-4d8742d5671f.apk`，不是上述两个版本。不要清除应用数据或卸载；私有备份不能抵御清数据/卸载。

## 第一件事：读新运行

https://github.com/supercubegame/todo-pocket-android/actions/runs/38533872559

来源必须为完整 f763cbf 提交，push，attempt 1。本检查点只确认运行已启动，尚未读取最终主机、构建、设备或汇总结果。不能把上一轮成功挪给本轮。若失败，保留首个原始输出，最小修复后新提交；不无改动重跑或放宽预算。

## 本轮真正新增的代码

工作流在固定产品 3a5a 的临时检出上重建完整候选，不直接覆盖产品分支。继承已通过的后台数据库读取、加载/错误页、单次连接移交、销毁清理与保存状态。

新增差异落在现有 MainActivity.java、Schema4DeviceTest.java、tools/verify_shortcuts.py：

1. MainActivity 增加仅进程内的布尔测试入口，固定使用 `schema4-startup-ui.db`，仍走真实默认后台启动方法；没有 Intent、偏好设置、文件开关或调用方选择路径。数据库名在 UI 线程捕获，后续重置标志不会把排队任务导向手机数据库。
2. 设备测试启动真实 Activity，等待真实待办控件或错误页；检查新文件只建 schema3、旧 schema3 全部历史类型化单元格不变、损坏文件字节保留、schema4 历史和关联不变、重新打开及独立进程重启一致、手机数据库始终不存在。
3. 新设备证据为 `STARTUP_NATIVE_PASS`：seed 6 项、reopen 2 项，另外保留原 97+16=113 项 SHORTCUT 标签契约。新增八项尚未设备验收，不能提前报成 121 项通过。
4. 同一个 parse_phase 被实际设备入口及独立汇总调用，要求新标签完整、唯一、有序。旧完整成功日志若漏掉新检查必须拒绝。原有设备日志摘要、来源绑定、APK读回、停止进程与数据库回放保留。

限制：新增启动夹具当前由设备中的独立 SQLite 读回比较，不另外收集该新数据库进行报告侧回放；原四类数据库回放仍保留。没有新增默认启动旋转/快速退出设备用例，相关后台所有权仍主要由 Java 替身测试覆盖。没有完成显式激活确认界面或覆盖升级。

## 本地已跑的检查，不冒充设备证明

- 新回执解析：4 个正向、32 个负向通过；原旧解析器能接受缺少新检查的日志，新解析器拒绝该日志。
- 真实 JDK AST：八个实际 Java 检查调用匹配；逐个移除的八个变异体均被同一检查器拒绝。仅解析，不是 Android 编译。
- 修改后实际启动成员：14 项 Java 检查、5 个有正向见证的实现变异对照通过；Android/数据库使用明确替身。
- YAML、11 个 shell 区块、外层与嵌套生成 Python 驱动语法通过。完整仓库主机和双 API 只以新运行结果为准。

## 上一轮已核验的成功

候选 `af4abf74661bc8c73c2e82d69a65e6035b928a0d`：
https://github.com/supercubegame/todo-pocket-android/actions/runs/38531511482

主机、可读回执、API26、API34、汇总五个作业全部 success；两档 Android 构建与既有回归实际成功，未跳过。完整新 UI 集成主机回执已读，原21命令均一次、300秒预算、退出0、无超时：
https://github.com/supercubegame/todo-pocket-android/runs/115747172492

候选归档：https://github.com/supercubegame/todo-pocket-android/actions/runs/38531511482/artifacts/11877649219

这证明 af4abf 编译与旧回归，不证明它已覆盖真实默认启动流程；因此才有 f763cbf。af4abf 的完整设备原始 ZIP 和全部汇总快照本轮未独立逐项审计。

恢复 af4abf 的五文件：AppDatabase 139068 字节/blob 0aaa2875c9c445800f25a7a0caa594541a24bec3；Schema4Store 39699/blob 1b88780386f99597bfc34dd40457a5730f2f4cd6；Schema4DeviceTest 57152/blob 251155aa169c681beac01a3849eb2dd8a37d99fc；verify_shortcuts 111849/blob 73c556d39736115e624153c398e064f171ec6c0c；MainActivity 38264/blob 3e0cfb326ad17d1638b805518187cae91f118218。这不是 f763cbf 的最终五文件身份，新身份必须读新回执。

## 永久恢复与历史

完整上一版交接、十一文件精确授权、21条命令、APK摘要、历史失败和待办范围均保留在不可变版本：
https://github.com/supercubegame/todo-pocket-android/blob/9a6c72f8c67e2ae3520398833dc1ace7bcfcddf4/HANDOFF.md

工作流永久源包含哈希绑定的完整代码片段及集成驱动：
https://github.com/supercubegame/todo-pocket-android/blob/f763cbf133c2eb6d8eb877a9836b852c56b178c9/.github/workflows/shortcut-storage.yml

它钉住 af4abf（20440 字节，SHA256 c921773dd62a5245e3d97af44c11ab8a52d20801e8ec9c31782e5d978ebbda38）的 UI 材料与 56e57 的后端材料，再按既有依赖链重建。必须验证每个不可变源摘要；不要猜路径或跳过旧检查。Actions 归档保留14天，不是永久备份。沙箱目录不会跨账号继承，完整产品源码应从 GitHub 读取。

## 接下来按依赖推进

1. 读取 f763cbf 原始主机回执、全部五文件身份、实际 Android 构建、两档原生启动日志及最终汇总；修首个失败。
2. 收口真实默认启动设备覆盖；补旋转/快速退出及原生错误恢复边界，不让局部测试冒充全链路。
3. 接通 TodayScreen 的明确激活入口、备份完成后的确认/取消；处理重复点击、过期状态、销毁、旧回调与成功后整屏替换。提交后重新打开失败不能宣称数据未变。
4. 实现稳定签名旧 APK 覆盖到新 APK 的验收。直接打开数据库不是覆盖升级证明。
5. 同步 AGENTS.md/CLAUDE.md 与产品工作流，完成原21主机、原子非强制产品提交、精确远端核验、同最终产品提交 API26/API34，才交付新 APK。
6. 再收口剩余功能、UI易用性、真实图片/大字体/输入法、性能、存储失败与商业签名分发等。历史十一父任务未重新统计，不报整体完成百分比。

## 权限与账户边界

10月11日18:34十一文件授权继续有效，详见历史交接，不需重复确认同范围。必须明确选择激活，不得普通启动自动迁到 schema4；备份先校验、失败关闭、不清数据，保留原断言、输出、预算与失败。现有授权连接即可，不新增令牌，不合并、不发布、不操作手机。

换 ClickUp 账号不需要 fork、迁移 owner 或改变仓库公开性；新账号要有自己的授权 GitHub 连接，不能假定继承旧账号的技能、记忆、文档、聊天、Agent或沙箱。先只读核对本文件、源码和报告，再在真正授权的下一次提交上核对写入与报告送达。禁止两个账号同时写同一分支。不要复制任何密钥值。

此前查到的 ClickUp 支持说明：Brain用量限制按Workspace计算，同一Workspace换用户不会重置；实际套餐/余额未读取。没有配置新的自动进度通知或后台开发者；对话结束不代表助手继续开发。

## 优化建议与未解决风险

优先完成默认界面、激活、覆盖升级这一条交付链，别继续积累无法安装的新后端候选。保留快检查在前、双API并行和首错停止；交接只更新当前状态与不可变证据链接，不每轮重写全部聊天。

历史 API26 ADB255 和独立 API34 导出系统 ANR 的根因仍未证明。后续绿灯、合成文件非复现均不能宣称修复。三字节媒体夹具不代表真实照片兼容性；私有备份不代表卸载安全、断电持久化或异机恢复。商业交付仍未完成。
