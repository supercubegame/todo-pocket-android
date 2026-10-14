# 口袋待办：当前接续入口

2026-10-14 18:00继续轮的工程检查点。不是发布、全部完成或新APK声明。单分支一个写入者；新账号须独立授权GitHub，不假定继承技能、记忆或沙箱。

## 最新候选与第一步

最新候选：[de8cbb1c](https://github.com/supercubegame/todo-pocket-android/commit/de8cbb1cc75cd81770b46422aa1a291010a6c71a)，[运行38547762007](https://github.com/supercubegame/todo-pocket-android/actions/runs/38547762007)，push、attempt1，最后观察pending，尚无新候选主机或设备验收结论。分支 `ci/shortcut-storage-preflight-4d8742`，实际改动现有 `.github/workflows/shortcut-storage.yml`，通过不可变载荷重建六文件产品候选，不是产品分支提交。

工作流11180字节，blob `b84dac06fa4b71bba9c8c7277115e437cda5bbea`，SHA256 `cd4b9999f95f85797b10f56ac0bcedb21d9a2e29870be6f02cc03e6425f913d1`。本地、写入返回及独立不可变目录读回一致。

第一步读取最新运行及全部分片主机回执，核对六文件身份、原21命令一次/300秒/完整输出，再读实际API26/API34构建、十项新增激活UI标签和汇总。红则保留第一失败、最小新提交修复；旧绿灯不接受新候选。

产品最近核验仍为 `3a5a17e1fdc570c73804007cd9a4d2ef36c0966b`，本轮产品推送0；手机APK仍4d8742阶段预览。没有新APK、合并、发布、凭据或手机操作。

## 已提交的显式激活界面

TodayScreen增加显式入口、已验证备份预览、内部备份会随卸载/清数据消失的提示、勾选同意后确认、取消、重复/过期/关闭/finishing保护。普通启动不自动迁移。确认成功由MainActivity重建整个Activity，弃用旧schema3 facade；失败后关闭旧界面，明确格式可能已变，不谎称数据未变。

Schema4DeviceTest增加独立 `schema4-activation-ui.db` 固定进程内路由，不接收Intent或任意路径，不打开手机数据库。新增8项seed和2项独立进程reopen检查：预览仍schema3、未勾选不提交、取消保留备份和历史、旧确认失效、备份变化拒绝、确认后真实Activity重建且历史精确不变、重复入口无操作、手机数据库不存在、独立进程历史精确、独立进程手机数据库不存在。对话框通过实际窗口观察，动作使用可见边界单次DOWN/UP；原113契约及八项原生启动检查保留。尚未证明新十项在Android通过。

本地真实JDK/显式Android与数据库替身12行为检查及3有见证变异通过；解析器4正向/36负向，Java AST十个实际调用和十个遗漏变异通过。实际嵌套解包逐字核对六载荷、保留API缺失RED，但最后完整集成子进程被拦截，不是完整仓库验收。新六文件最终身份必须从CI回执读取。

## 本轮两个不同问题

1. 首次提交 [cbbc66ec](https://github.com/supercubegame/todo-pocket-android/commit/cbbc66ec225157ace12dc56402445390beb1df66) 少了两处嵌套字符串反斜杠，29380字节/blob `b72879364d180397e06857650fd246c3644ff357`，而本地候选29382字节/blob `7ded9ebe7dca9e669e6dd4f6b906191f1ef957a0`。远端独立核对发现，不能报精确提交成功。[原运行38546973764](https://github.com/supercubegame/todo-pocket-android/actions/runs/38546973764)在集成脚本解析处SyntaxError，设备跳过；[完整失败尾部](https://github.com/supercubegame/todo-pocket-android/runs/115797027408)404字节，未截断，原归档11884947498。原运行未重跑或取消。
2. 核对实际MediaRepository源码发现构造函数声明IOException，而新UI的activationMedia未声明，最初的本地替身漏掉这一契约。用真实异常签名复现Java编译RED：unreported exception IOException。最小修复是UI方法声明throws java.io.IOException，并同步替身；修复后12行为/3变异通过。没有吞掉异常或削弱断言。de8工作流将绑定原MediaRepository blob、先复现缺声明RED，再执行修复GREEN；实际Android编译仍待CI。

中间传输修复 [a37a972b](https://github.com/supercubegame/todo-pocket-android/commit/a37a972bd31bd0ad4fa0b82005f26a91bc07b9fc)，[运行38547271970](https://github.com/supercubegame/todo-pocket-android/actions/runs/38547271970)，最后观察主机执行中。其工作流11570字节/blob `cb33818dafc911ec79e490491ff58fb8734741cd`，独立身份已核对。固定读取cbbc原文件，仅修两处转义并要求修后整体SHA256 `8ba546250800b9d2f752cf70446f11de83bdebd137acde6cf771621b5f576d2d`；11个原shell块本地逐字一致，原预算/命令/输出/设备步骤保留。de8在此基础仅补真实异常契约。所有候选工作流均非强制更新原分支。

## 上一轮验收已确认，不再pending

[87d3运行38539002887](https://github.com/supercubegame/todo-pocket-android/actions/runs/38539002887)六作业成功：主机、两片回执、API26、API34、汇总；两个实际Android构建和设备步骤成功。已读取回执后半及API26原生seed标签，并经a87只读取证验证21命令；未完整逐项审计两档全部原始快照，不能宣称131项新激活UI通过。a87仅取证，无产品提交。

## 余下交付与边界

先收口显式UI完整主机/双API，再补旋转、快速退出、确认中销毁、报告侧新UI数据库独立回放；现有替身不证明真实生命周期。之后完成同最终产品提交的旧APK稳定签名覆盖升级、AGENTS/CLAUDE一致更新、产品工作流和原子非强制产品提交，验收后才给新APK。再处理剩余功能、真实照片/EXIF/输入法/大字体、性能、存储失败、UI易用性、商业签名及分发。没有可靠总完成百分比。

沿用10月11日18:34原十一文件授权；[授权与21命令](https://github.com/supercubegame/todo-pocket-android/blob/9a6c72f8c67e2ae3520398833dc1ace7bcfcddf4/HANDOFF.md)。[前一完整检查点](https://github.com/supercubegame/todo-pocket-android/blob/5fbb6fa782635e7c9856913a12a54648c2519514/HANDOFF.md)保留ab5162测试竞态、f763验收、原始证据和更早历史。只用现有凭据；失败关闭，不清数据，不卸载、不启动外部应用、不操作手机、不合并发布。历史ADB255和ANR根因未证明，三字节媒体不证明照片兼容。

永久重建依赖不可变工作流，不依赖14天Actions归档或当前账号沙箱。下载包不是完整仓库/APK/技能备份。没有新增后台开发或自动通知；对话结束不代表助手继续开发。
