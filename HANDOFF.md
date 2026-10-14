# 口袋待办：当前接续入口

2026-10-14 工程检查点。不是发布、全部任务完成或新APK声明。单分支一个写入者；新ClickUp账号须独立授权GitHub，不能假定继承技能、记忆、沙箱或权限。

## 最新实际提交与第一步

当前候选工作流提交：[87d3cfd2](https://github.com/supercubegame/todo-pocket-android/commit/87d3cfd2a9b8c8728919013d081682cf9ee5394e)。分支 `ci/shortcut-storage-preflight-4d8742`，只修改原有 `.github/workflows/shortcut-storage.yml`。

[运行38539002887](https://github.com/supercubegame/todo-pocket-android/actions/runs/38539002887)：已核对精确来源87d3cfd2、push、attempt 1，最后观察in_progress，尚未确认最终主机或设备结果。第一步读此运行、所有分片主机回执、API26/API34实际构建与设备步骤、汇总。不能使用f763或af4abf的绿灯替代。

工作流15104字节，Git blob `1d2c6ffaebca97c215a3e7eb834930e1c845f824`，SHA256 `d47e797e26a8377664150fa06b10b180a5f35467b45a92bb32069766f3dd3b10`。本地计算、写入结果和独立不可变目录读取一致。

产品分支 `feature/v1.2-activity-notes-ledger` 最近核验仍为 `3a5a17e1fdc570c73804007cd9a4d2ef36c0966b`，本轮产品推送0。手机APK仍为4d8742阶段预览，无新APK、合并、发布或手机操作。

## ab5162的两个独立失败已定位

[原运行38535075337](https://github.com/supercubegame/todo-pocket-android/actions/runs/38535075337)已失败，不再是pending。原后端主机步骤成功，新增集成失败，设备被跳过。原运行未重跑或取消。

1. 测试时序问题：`gate.py` 的 `transfer_not_reclaimed` 在 `stopStartup()` 排队关闭后立即读取关闭次数，没有等待后台完成。原日志先显示第一轮14项/5变异通过，第二轮变异却报 `no_reoffer_after_take` 而不是预期 `transfer_not_reclaimed`。这是测试见证竞态，不是已证实的产品故障。最小修复在原断言前等待同一executor终止，沿用5秒预算并要求等待成功；不放宽断言、不接受任意异常、不重试。
2. 回执通道问题：集成在重置receipt前失败，留下的大份后端回执触发原 `len(body.encode())<60000` 断言，实际没有发布可读check。现在保存完整集成stdout/stderr到artifact，并把完整JSON分片发布，各片仍小于原限制、逐片读回比对；失败明确标记失败，尾部若截取则标明partial，完整原日志保留。

原主机日志31366字节，SHA256 `f4d7d46cc1cde5423b15fd39d2f1b109d733754d10b5fe262a312a992804c265`。完整日志由只读取证提交 [c845b6f7](https://github.com/supercubegame/todo-pocket-android/commit/c845b6f7e2ca5d24038a013948c5e5d6abe2138c)发布四片，不代表测试通过。核心原始失败见 [第3片](https://github.com/supercubegame/todo-pocket-android/runs/115766690334) 和 [第4片](https://github.com/supercubegame/todo-pocket-android/runs/115766695916)。原候选归档：[11879958418](https://github.com/supercubegame/todo-pocket-android/actions/runs/38535075337/artifacts/11879958418)，291783字节，ZIP摘要 `ab3d1f1d098256005f4031587d5685fd5256b7e8783936de9d95d7a691ccfe88`。

只读取证自身也有两类已记录问题：GitHub CLI拒绝带ANSI控制字符的日志输出，改为只将原字节捕获到文件、报告转义显示；原2000字符窗口跨过前一步边界而误匹配两次，改为完整日志分片、不猜边界。1646、78df、7da取证失败均保留，没有修改产品来迁就它们。

## 本地验证与准确边界

修复前原始CI红灯已经保留。真实Java/显式Android数据库替身的14检查、5实现变异全部通过；修改后的原生测试路由成员也通过同一检查。另用可控executor和latch复现：原测试确定性落到错误断言，修复后确定性在预期断言抓住同一个变异体，无sleep或重试。该可控调度对照保存在下载包的 `race-local-test.py`，目前不是产品永久闸门；CI继续执行已修复的原14/5检查。

实际固定ab5162和af4abf工作流解包路径在模拟网络传输下执行，输出gate与原生载荷逐字匹配，末尾完整集成子进程被拦截；这不是本地完整仓库验收。大份中文JSON回执的失败7片、成功6片经模拟API完整重组、结论和长度检查通过；这不是远端回写成功证明。YAML、11个shell块、Python与嵌套脚本语法通过。

87d3cfd2没有修改产品Java、设备测试、原21命令、单次300秒预算、Android步骤或重试次数。它从不可变ab5162重建候选，修正其引用的af4abf测试见证。候选五文件身份必须从新回执读取。

## 前一候选f763现已读到成功，但不替代最新修复验收

[f763运行38533872559](https://github.com/supercubegame/todo-pocket-android/actions/runs/38533872559)：五个作业成功，两档实际Android构建和设备步骤成功。完整[21项主机回执](https://github.com/supercubegame/todo-pocket-android/runs/115755471032)已读，均一次、300秒原预算、退出0、无超时。

[不可变汇总](https://github.com/supercubegame/todo-pocket-android/blob/43d2992e6ce69a149fd4b8f5d6af4e163082f5ed/reports/shortcuts-f763cbf133c2eb6d8eb877a9836b852c56b178c9-38533872559-1.json)为PASS；读取在API26快照中被截断，新增八项原生日志和API34完整原始ZIP本轮未逐项审计，不报121项已独立确认。报告scope仍继承后端候选旧文案，不能据此声称产品或完整UI已发布。

f763到ab5162的夹具前缀修复依然有效：保留旧日志完整前缀，旧乱序对照仍针对旧标签，新对照精确操作自己的标签。f763绿灯不能证明旧负向对照语义未削弱。

## 继续开发的顺序

1. 先验87d3cfd2完整21主机、五文件身份、实际双API和八项新原生日志；红则保留第一失败，最小新提交修复。
2. 完成TodayScreen显式激活入口与验证备份后的确认/取消，过期、销毁、重复点击、旧回调失效，成功后整屏替换。迁移提交后重开失败不能说数据未变。
3. 默认启动旋转/快速退出、新启动UI数据库的报告侧独立回放仍有缺口，现有主机替身不证明设备生命周期。
4. 完成稳定签名旧APK覆盖到新APK、AGENTS/CLAUDE一致更新、产品工作流。原21主机通过后原子非强制提交产品、核对远端，再验同最终产品提交的API26/API34和覆盖升级，才给新APK。
5. 再收口剩余功能、真实媒体/大字体/输入法、性能、存储失败、UI易用性与商业签名分发。不要虚构总完成百分比。

## 授权、历史与安全边界

[上一完整接续入口](https://github.com/supercubegame/todo-pocket-android/blob/d9f0261aded8f8db0b33edaaaad73fb6865f50ef/HANDOFF.md)及其不可变历史保留所有先前范围。原十一文件授权与21条主机命令见 [9a6c72历史](https://github.com/supercubegame/todo-pocket-android/blob/9a6c72f8c67e2ae3520398833dc1ace7bcfcddf4/HANDOFF.md)。沿用10月11日18:34明确授权，不重复问同范围。

普通启动不得自动激活schema4；备份先核验、失败关闭、不清数据。仅现有凭据，不外部启动、不操作手机、不合并发布。不要清除数据或卸载，私有备份不具备卸载安全。历史ADB255和系统ANR根因未证明，后续绿灯不等于修复，三字节媒体不证明照片兼容性。

不可变工作流是重建来源；Actions归档14天不是永久备份。下载包不是完整源码/APK/技能备份。没有新增后台开发或自动通知；对话结束不代表助手继续开发。同Workspace换账号不重置此前查到的共享用量，实际套餐/余额未读取。
