# 口袋待办：当前接续入口

2026-10-14 最新工程检查点。不是发布或全部任务完成声明。单分支一个写入者；换ClickUp账号须自行授权GitHub连接，不能假定继承旧账号的技能、记忆、沙箱或权限。

## 先读这两个来源

完整本轮开发说明、精确授权、局限和剩余任务：
https://github.com/supercubegame/todo-pocket-android/blob/3e6e078f589e5bcde62643269606fa527dac108a/HANDOFF.md

更早的完整历史、十一文件授权、原21主机命令及APK摘要：
https://github.com/supercubegame/todo-pocket-android/blob/9a6c72f8c67e2ae3520398833dc1ace7bcfcddf4/HANDOFF.md

上面两份为不可变历史。凡与本页冲突，以本页的新提交与验收边界为准。不要重建项目，不要重复询问已批准范围，不默认让用户运行本地脚本或上传文件。

## 最新候选：ab5162，不是f763

分支 `ci/shortcut-storage-preflight-4d8742`。

提交：https://github.com/supercubegame/todo-pocket-android/commit/ab5162f847db4a2b88229b156c3702c31707a4ac

新运行：https://github.com/supercubegame/todo-pocket-android/actions/runs/38535075337

刚读到：来源ab5162完整提交、push、attempt 1、pending，无最终结果。保留原串行并发配置，前一运行不取消。下一轮第一件事是读此运行及原始回执，不得使用旧提交绿灯替代。

实际工作流 `.github/workflows/shortcut-storage.yml` 为20887字节，Git blob `2b7bd69ff516d4f1a85c6b52afc52df09c9d4f51`，SHA256 `892892019cd20e7e911b595269fcb306d87358cba83d8636ff71fdb46abf4176`。本地计算、写入返回和独立不可变提交目录回读一致。嵌入载荷SHA256 `23fdb39708af369ac7cd23761f6f7ddc44508445e965073b2d428cbae94ab8e0`。

## f763到ab5162只修了什么

f763新增原生启动测试后，把新日志放在合成fixture最前面。旧测试以“交换前两行”构造乱序输入，因而会测试新标签而不是旧标签，削弱旧对照的原含义。这是测试夹具问题，不是已证实的产品故障，也不是远端设备失败。

本地已复现 `ORIGINAL_FIXTURE_PREFIX_RED`；最小修复让旧fixture保持完整前缀，新检查追加在后面，新乱序/重复对照精确操作自己的标签，并永久断言旧前缀保持。修复后4正向/32负向解析和真实JDK八检查/八缺失对照通过。产品Java与设备测试内容没有因本次夹具修复改变，原命令、预算、重试次数未放宽。

完整仓库与真实Android仍必须等ab5162运行，不能用这些局部测试宣布通过。上一份资料中的f763身份、pending状态和20883字节仅是历史。

f763原运行：https://github.com/supercubegame/todo-pocket-android/actions/runs/38533872559 。最后观察为原后端主机阶段成功，新增完整集成阶段in_progress；尚未读最终结果。未重跑、未取消、失败若出现必须保留。

## 本轮实际交付边界

本轮新增默认启动的固定进程内隔离测试路由、真实Activity测试及强制原生日志检查。六项seed、两项reopen原生检查覆盖新建schema3、旧schema3数据保留、损坏文件保留、schema4数据与关联、重新打开及独立进程重启、手机数据库不被触碰。原113项设备标签契约保留，新增八项未验收，不可提前称121项通过。

此前af4abf已通过完整21主机、API26/API34 Android构建和既有回归、汇总：
https://github.com/supercubegame/todo-pocket-android/actions/runs/38531511482

完整主机回执已读，每条一次、300秒预算、退出0、无超时：
https://github.com/supercubegame/todo-pocket-android/runs/115747172492

这不是ab5162验收。最新产品分支 `feature/v1.2-activity-notes-ledger` 最近核验仍为3a5a17e1fdc570c73804007cd9a4d2ef36c0966b，本轮产品推送0。最新手机APK仍是4d8742。没有新APK、合并、发布或手机操作。

## 准确下一步

1. 读取ab5162的主机首个实际结果、完整五文件身份、两档Android构建与原生日志及汇总。若红，保留原失败后最小修复新提交，不无改动重跑。
2. 补齐真实默认启动旋转/快速退出等缺口。新启动数据库当前在设备内比较，未额外收集给报告侧回放，不能宣称该层已完成。
3. 完成TodayScreen明确激活入口、校验备份后的确认/取消、过期/销毁/重复点击、旧回调失效、成功后整屏替换。迁移提交后重新打开失败不能称数据未变。
4. 完成稳定签名旧APK覆盖到新APK验收、AGENTS/CLAUDE一致更新和产品工作流；原21主机通过后原子非强制提交产品并核对远端，再验同最终产品提交的API26/API34，才给新APK。
5. 再收口剩余功能、UI易用性、真实媒体/大字体/输入法、性能、存储失败和商业签名分发。全部任务仍未完成，不报虚构百分比。

## 不得跨越的边界

沿用10月11日18:34十一文件明确授权，见历史原文。普通启动不自动激活schema4；备份先验证、失败关闭、不清数据。现有GitHub连接优先，不换密钥、不外部启动、不操作手机、不合并或发布。不要清除应用数据或卸载，私有备份不具备卸载安全。

历史ADB255与API34系统ANR根因未证明，后续绿灯不等于修复。三字节媒体夹具不证明照片兼容性。现有恢复资料不是完整技能/源码/APK备份；工作流的不可变提交是重建材料，Actions归档14天不是永久备份。

同一Workspace换用户不会重置此前查到的Workspace用量限制；实际套餐/余额未读取。没有配置新的自动通知或后台开发者，对话结束不代表助手仍在开发。

优化优先级：完成默认启动、明确激活、覆盖升级这条交付链，而不是堆积更多不可安装候选。按真实提交、实际CI结果与阻塞更新短交接，历史只留不可变链接。
