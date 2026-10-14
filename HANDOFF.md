# 口袋待办：当前接续入口

2026-10-15继续轮。单分支一个写入者；新账号独立授权GitHub，不假定继承技能、记忆或沙箱。不是完整交付、新APK或发布声明。

## 第一件事：读取cc06首轮结果

[cc06d833提交](https://github.com/supercubegame/todo-pocket-android/commit/cc06d83314b629746ac9a5588bcd2e0f581c255d)，[CI38618514789](https://github.com/supercubegame/todo-pocket-android/actions/runs/38618514789)。push、attempt1、run45。最后观察主机116039688868执行原后端验证中；新增报告夹具隔离步骤尚未到达。没有本候选完整主机、设备或数据库独立回放验收结论，不得沿用61e4绿灯。

仅更新现有隔离分支ci/shortcut-storage-preflight-4d8742的.github/workflows/shortcut-storage.yml，materialize时修改现有tools/verify_shortcuts.py。远端21794字节，blob93a051e95e02d9057a35ff335ffc3e3e2714f6f1，SHA25688f6cba903bfd2d4c9bc8caa48670200003cd0c7f2a4d81cc007f08e556a5b5c。写入响应与独立完整文件读回一致。相对本地21795字节候选仅省略最后一个空行，穷举单字节删除命中远端blob，解析后全部YAML字段和可执行脚本逐字一致；不是转义或代码丢失，没有为了空行追加提交。

产品最近核验仍3a5a17e1fdc570c73804007cd9a4d2ef36c0966b，本轮产品推送0；手机仍4d8742阶段预览。没有新APK、合并、发布、新凭据或手机操作，无待处理安全确认。

## c91已失败，不再pending

[c91原运行38612152149](https://github.com/supercubegame/todo-pocket-android/actions/runs/38612152149)首20项主机通过，第21项python3 tools/verify_shortcuts.py selftest失败。一次尝试，300秒预算，耗时30.107662626999968秒，无超时。设备未执行；不是设备数据失败。

[完整9333字节首失败](https://github.com/supercubegame/todo-pocket-android/runs/116022420171)，[完整命令流回执](https://github.com/supercubegame/todo-pocket-android/runs/116022412292)。stdout4328字节/SHA256fa986deea4cbbe8009cac2b4b1594aa36e56e8086c75ebf74c719a9023a68e43，stderr2749字节/SHA2565c7916fe1ea3492a7d4c380f94b98e47328c6f0c56ad023ded7ea082553cee50，原artifact11918543537保留，未重跑覆盖。

实际首断言是report_selftest的valid actual report entry；外层startup_missing变异探针随后报wrong startup replay witness。新增直接report回放读取真实激活数据库，而旧report自测夹具只模拟旧文件系统，没有新库/oracle。新回放13反例、接线4整体遗漏、真实源码生命周期8场景4变异在这次CI的stdout中已通过，但不代表整体候选通过。

## cc06最小修复及承重验证

仅在旧report_selftest创建runner的scope内绑定显式legacy_activation_report_double，不修改全局生产replay_activation_ui，不添加跳过生产回放的条件。原14个报告正反例、旧业务和启动回放变异锚点均保留。AST定位唯一赋值，插入后逆向删除必须逐字恢复旧代码。

新增activation_report_entry_selftest实际执行当前report.__code__，使用真实Java编码oracle和真实主机SQLite激活数据库。旧数据库家族和发布器是明确替身，不声称真实GitHub或Android。正例必须观察4次真实回放；7个精确反例覆盖缺库、缺oracle、错误文件摘要、刷新摘要后改历史单元格、缺整体/单phase回执、伪造一致快照。API26失败不得掩盖API34，发布失败保留原OSError。

AST整段删除新report回放的变异必须先通过正向见证，再暴露缺库被错误接受且回放次数为0。旧业务回放遗漏仍须击中原精确断言。本地已复现原valid actual report entry红灯，旧14例跑绿、新实际report真实SQLite正例1/精确反例7/发布失败1/整段遗漏见证1通过。本地使用从固定产品源码读取的真实report与report_selftest，但其他旧依赖是替身，不是完整checkout；完整组合由本次CI验证。

工作流从不可变c91下载并核验原13段host脚本，仍逐段放在独立步骤，保留GITHUB_PATH/GITHUB_ENV传播、原21命令、每项300秒预算和失败发布。设备和报告作业仍使用原a37不可变bootstrap，不依赖仅host存在的文件。当前修复只新增既有verifier selftest和旧夹具隔离，不修改Java运行行为。

## 数据库回放契约与已接受前序

c91引入的采集在seed/reopen进程停止及旧UI快照后读取schema4-activation-ui.db、存在时的WAL、files/activation-ui-expected.bin；沿用原command预算与一次执行。独立SQLite读取18张旧表全部列、rowid、null/int64/text/blob，要求schema4、精确表集合、空category_shortcuts、两phase快照相同。文件字节数和SHA绑定receipt，报告从文件独立复核，拒绝缺失、未登记WAL、篡改文件/单元格/快照。真实主机SQLite已证明相邻WAL参与只读查询，不能只复制主库。

[61e4运行38600355606](https://github.com/supercubegame/todo-pocket-android/actions/runs/38600355606)八作业/检查成功，包括21主机、实际API26/API34构建与seed/reopen、原汇总和两个精确回写。[API26完整原始流](https://github.com/supercubegame/todo-pocket-android/runs/115984330118)、[API34完整原始流](https://github.com/supercubegame/todo-pocket-android/runs/115984340696)均完整读回：每端原SHORTCUT seed97/reopen16，启动seed6/reopen2，激活seed8/reopen2。不是新数据库回放、覆盖升级或产品交付验收。

b060此前21主机和双API通过，生命周期8场景/4变异使用实际Java AST成员和明确Android/DB替身，不是真实旋转验收。a727修复测试屏幕坐标后双设备通过；更早失败流保留。

## 下一步与边界

先读取cc06完整21主机、旧报告变异、新实际report门禁、双API编译/采集、原汇总与紧凑数据库回写。失败先读完整首个输出再最小修复，不无改动重跑。API绿灯但独立回放未过不能算完成。

仍欠native-startup UI数据库独立回放，其startup-ui-expected.bin用bridgeCells格式，旧18表后带int32关系数与int64关系对，不能直接套用激活old-cells-only解析器。另欠真实旋转/快速退出/确认中销毁、稳定签名旧APK覆盖升级、AGENTS/CLAUDE同文且不超过200行、产品工作流集成、原子非强制产品提交及精确读回、绑定同一最终产品提交的双API/升级验收，之后才给新APK。

后续还有剩余功能、照片/EXIF/输入法/大字体、性能、存储失败、易用性和商业签名分发。ADB255/ANR根因仍未证实，没有可靠整体完成百分比。原始UI片段缺IOException，由不可变已提交修复补齐，不能直接覆盖产品。完整重建依赖不可变工作流，不依赖短期归档或某账号沙箱。

[上一交接及原数据身份](https://github.com/supercubegame/todo-pocket-android/blob/a5e19a1f3c07fe50237cc62799fc63f9188d54d2/HANDOFF.md)。沿用10月11日18:34原十一文件授权，[授权及21命令](https://github.com/supercubegame/todo-pocket-android/blob/9a6c72f8c67e2ae3520398833dc1ace7bcfcddf4/HANDOFF.md)。只用现有凭据；显式同意、先验证备份、普通启动不自动迁移、失败关闭。不清数据、不卸载、不启动外部应用、不操作手机、不合并发布。对话结束不代表助手继续开发。
