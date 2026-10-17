# 口袋待办：当前接续入口

2026-10-17，15:16六文件批准后的实际执行检查点。异步结果拒绝提示、编辑器IME和待办视口修复已实现并提交到隔离交付流程。最新实际读取：完整原21项远端验证正在运行；尚未读取本轮新产品更新回执或新设备验收，不宣称新APK可用。不要重复提交或重跑未变化的CI。

## 当前提交与接续顺序

隔离提交 [09ff2255f1b7a80bcd71a2718730211abc4033d2](https://github.com/supercubegame/todo-pocket-android/commit/09ff2255f1b7a80bcd71a2718730211abc4033d2)，仅更新既有 ci/shortcut-storage-preflight-4d8742 分支的 .github/workflows/shortcut-storage.yml。

[实际运行39014243730](https://github.com/supercubegame/todo-pocket-android/actions/runs/39014243730)：run73、attempt1、suite105732312489、job117342927670。固定来源恢复和实际改造交付器控制均成功；Full original21 once then atomic exact product delivery仍in_progress。原命令各一次、300秒，未增加预算或重试。

不可变目录独立核对：工作流17663字节，blob 2c011a0eb2ffedb98980f8f3955446a01909d26f，SHA256 704099ef02bd14727efe12cc1a4278f03644d970a26448323453aea88d40a27b。内嵌repair.py、prepare.py、gate_additions.py载荷34720字节，SHA256 81d8f6f13953aa0d78742b54e899728a73e58feca51ed8132399e42b286451fb。从不可变工作流恢复前先核对身份，勿依赖临时沙箱。

1. 先读取同suite的Result and viewport repair delivery分段check，以及result-ui-delivery归档，确认最终21项、五个产品文件身份、产品ref更新次数和dispatch结果。
2. 成功后独立核对产品ref、单父、完整树和五个blob；不以交付器自报替代独立核对。
3. 读取绑定新产品SHA的主回归、快捷双API和既有覆盖升级。失败保留首失败命令、预算、输出，定位原路径，再做最小修复。不得沿用8f或7920绿灯。
4. 只有同最终SHA的设备与升级验收完成，才交付验收APK。手机仍4d8742，不卸载、不清数据、不操作手机、不合并或发布。

## 已批准范围和实现

用户批准 approve_result_ime_viewport_batch，消息80180082440248，线程80180077935853，trigger815c4158-c49a-4dbc-8f2b-e32abf849a37。六个既有目标：产品MainActivity.java、TodayScreen.java、tools/emulator_gate.py、AGENTS.md、CLAUDE.md，加既有隔离shortcut-storage工作流。不重复请求该范围批准；没有待批准安全事项。

MainActivity保留后台异步打开数据库。screen尚未附着时只保留一个已知请求类别的整数拒绝提示，不保存Intent、URI、数据、操作或同意；清理旧pendingImage/pendingShare，拒绝destroyed/finishing。附着screen后消费提示，destroy清零。原TodayScreen notice身份保护让更早的异步load不能覆盖新拒绝提示。

TodayScreen编辑成功先用仍附着的field token隐藏IME，再clearFocus、dismiss、success刷新。验证失败、保存失败保持编辑；未改取消行为，没有让测试盲按Back。普通待办ScrollView加唯一todo-list-scroll身份。

emulator_gate的named_todo改为当前viewport内精确checkbox查找：核对package、class、enabled、非空todo身份、bounds，单一20秒截止，两个方向各最多8手势；相同帧停止该方向，缺失显式失败。手势始终在实际列表范围内，不凭count3假定第三条身份。

AGENTS/CLAUDE保持逐字相同且不超过200行。未改ActivitiesScreen、产品android.yml、数据库、权限、签名、21项命令或设备预算。

## 本地验证与证明限制

第一版集成候选完整原21项主机命令各一次通过，每条300秒预算；第21项229.268455101秒、return0、无超时。工具等待达到300秒时进程仍在正常运行，随后读取完整21项回执确认结束，没有重启或重复该命令。

此后仅补充了已有notice防覆盖路径的实际源码测试，未再改两份产品Java。最终候选专项验证通过：JDK AST提取实际MainActivity/TodayScreen方法，17场景、2个原始失败对照、8个有正向见证的变异；导航2正向、13拒绝、5有见证变异和3整调用遗漏。最终文件完整21项由上述远端运行重新审验，不能把本地前一版21项说成最终字节全部验收。

第一次导航测试夹具把absent模式也随滚动显示目标，正确暴露测试错误；已修正并保留原输出。测试使用明确Android/DB/IME替身和合成几何，不证明Android时序或触摸物理。实际现有work/message的异步队列测试验证新提示不被旧load覆盖，去掉notice守卫会红。

交付程序使用真实Git及替身网络/业务命令验证成功、host失败、分支漂移、额外路径、远端字节不符四种边界，已改为实际五文件目标群。保留独立验证worktree、发布目录零未跟踪、HEAD差异含暂存区、模式不变、完整远端树、单父、force=false和所有blob逐字节读回。

最终候选身份：
- MainActivity.java：40991字节，blob7efc019e9cf18acdc3490543b336ee6ecbd4d619，SHA256 52ffb0033edb9d598867820a5b3405e89516fb902641326efa3ff7ea71078601。
- TodayScreen.java：30821字节，blobe1f13eaa04747f5a1de273499209ea9745382b06，SHA256 0cf19ed8a1c598308a236da61032ab9b0519ab485e48f282b1581e446dac2409。
- tools/emulator_gate.py：162514字节，bloba643da3f28ff3e4e6f6d742ec8cfd7a825572495，SHA256 c58140e34befa88cb17eb1450ef97fd7294adb8d69d224868657528117d3e7f8。
- AGENTS.md及CLAUDE.md：各15192字节，blob5bd35a3437c0a6f73989f2260fee97c573b4d62c，SHA256 5ea6cf1e1a707aea09a5534d5446aa600aff72fddb2664cc92927e104a743652。

## 产品基线8f和原始失败

最后独立读取产品ref为 [8f1eab2ee1a4a52dfa5f007be550abc8b2077403](https://github.com/supercubegame/todo-pocket-android/commit/8f1eab2ee1a4a52dfa5f007be550abc8b2077403)，单父c9d905b37061c0f52f57be54c318ce275ef0f1fa，tree117f54ac15905e7c04a0daeb760526f1c53c1fb4。完整GitHub源码ZIP已下载，按文件字节和可执行模式重建完整Git树，身份精确一致。

0f/39007573640原21项通过、精确四文件8f提交及两次dispatch完成。旧交接的产品c9/0f仍运行已过期。8f主回归 [39008004576](https://github.com/supercubegame/todo-pocket-android/actions/runs/39008004576)失败，upgrade skipped，未打包验收APK。

两个主API均seed155/reopen25 PASS，只说明这次未复现c9 seed180秒超时，不是根因已修复。API34编辑活动路径后键盘仍可见，详情viewport只有2px，原截图已目视确认；API26创建After backup后count3但仅两行可见，原named_todo不滚动。第三条确切内容没有在失败现场独立读库，不能由计数断言。

两个导出早期报告均记录29后端+22实际预览标签通过，后续PDF系统保存器保留、旧进程SIGKILL后返回新Activity，预期拒绝提示丢失。实际onActivityResult在screen空时直接return；实际三方法主机RED复现ready通过/delayed丢提示。未直接追踪原Android回调时序；未到达后续目标文件空字节/新同意断言，不能宣称这些已通过。

主报告379652字节/blob7155d23813ab1b33bbf08a44676d70e7e059cb2a，导出早期报告1354270字节/blobcf36f1f2fea83695e0bf4eef8f9416fd8dedb686，均完整下载校验；导出原日志内嵌部分明确截断，非完整原始仪器流。原Actions ZIP本轮未下载。

8f快捷运行 [39008002946](https://github.com/supercubegame/todo-pocket-android/actions/runs/39008002946)成功。本轮读取reports/shortcuts-8f1eab2ee1a4a52dfa5f007be550abc8b2077403-39008002946-1.json，blob5051e02252495819ee93b26aacebf93ecde155ad，报告PASS但工具输出截断，尚未完整审阅双API全部原流及独立数据库回放。exact8f actions曾报告9条，尚未完整枚举，勿声称只有两个运行。

## 安全、历史和剩余工作

无手机操作、自动迁移、外部应用启动、合并、发布或新PR评论。覆盖升级重建f42旧源并用当前固定密钥，属于REBUILT_OLD_SOURCE_SAME_FIXED_KEY_OVERWRITE_NOT_EXISTING_PHONE_CERTIFICATE，不证明手机原4d证书兼容或原4d包覆盖后再显式激活组合。

旧ADB255、旧系统ANR、c9 seed180秒超时分别未定因。全v1.2功能、真机UX、性能与商业分发仍未完成，不编百分比。

[上轮完整交接](https://github.com/supercubegame/todo-pocket-android/blob/f22706a7b0595ad5548897aea68c8bb6dc91e101/HANDOFF.md)保留分页/超时修复及原证据恢复。[7920验收与候选身份](https://github.com/supercubegame/todo-pocket-android/blob/12a9b7779dca1cd2477c8aee1d00a54d1698a686/HANDOFF.md)保留旧隔离验收；[十一文件授权与原21命令](https://github.com/supercubegame/todo-pocket-android/blob/9a6c72f8c67e2ae3520398833dc1ace7bcfcddf4/HANDOFF.md)。Actions自行运行不等于助手在对话结束后继续开发。
