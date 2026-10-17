# 口袋待办：当前接续入口

2026-10-17，17:52实际RelationEditor修复及18:41测试接口追加批准均已执行。最终候选完整原21项本地主机验证全部通过，各一次、300秒、无超时，最后一项239.7053898839995秒；候选文件验证后未变化。隔离工作流已实际提交并独立核对，远端完整21项仍运行中，尚未读取本轮新产品提交回执或新设备验收。不要重复提交或无变化重跑。

## 当前实际提交

隔离提交[b1d3f5502d6c2cb430f8a8458bf0ffa057c526e3](https://github.com/supercubegame/todo-pocket-android/commit/b1d3f5502d6c2cb430f8a8458bf0ffa057c526e3)，分支ci/shortcut-storage-preflight-4d8742，仅既有.github/workflows/shortcut-storage.yml。

[运行39026184501](https://github.com/supercubegame/todo-pocket-android/actions/runs/39026184501)：run76、attempt1、suite105763884581、job117377512785。固定来源恢复和实际五文件交付器控制成功；完整原21项步骤仍in_progress。完整主机成功后才允许原子产品提交，随后绑定新SHA dispatch主回归及快捷双API。

不可变目录独立核对工作流17160字节、blob1e5555540b60db395e1a7f1eeea3e17010f7966c，与本地一致。SHA25685af3fd1c4d2597c7d730dd97fa90a57c14673629b6c6c15f6cf0ba4e45f7d86。内嵌repair.py、prepare.py、gate_additions.py、fixture_patch.py载荷35240字节，SHA256941b61e0781e696614c49077e3434c1c485c254007fb28da9b208ec5f3ed4598。可从不可变工作流恢复，无需依赖临时沙箱或用户上传。

## 授权与修复范围

approve_relation_editor_callsite_repair，消息80180082454009；追加approve_relation_fixture_extension，消息80180082455509，trigger251f6244-9737-4206-9d98-a40e4ba1902b。共五个产品目标：ActivitiesScreen.java、tools/emulator_gate.py、tools/verify_app_catalog.py、AGENTS.md、CLAUDE.md；第六个目标是隔离工作流。没有新增仓库路径，不重复询问已批准范围。无待批准安全事项。

实际路径/标签入口使用ActivitiesScreen.RelationEditor，不是上轮已修的TodayScreen.editor。成功和明确取消时，在input仍附着时隐藏IME、清焦点，再导航；保留plan关闭、生命周期、单次提交、验证失败及保存失败行为。取消恢复后的After backup查找改用既有有界named_todo，后续独立精确SQLite断言保留。未改数据库、同意、签名、权限、设备预算或手机。

## 验证与首失败

JDK AST提取完整当前RelationEditor并检查实际renderDetail调用者。原类正常无效输入对照通过，保存/取消的IME顺序原始RED，恢复取消原直接find被拒绝。最终专项12场景、5有正向见证的Java变异、2编辑器调用遗漏、实际恢复调用1正向/2负向、原find拒绝、整恢复断言遗漏和parser注册遗漏均通过。

首轮完整验证在命令1 python3 tools/verify_app_catalog.py selftest 停止：46.795962912秒，return1，无超时，命令2至21未跑。原因是原relation_host_selftest提取真实类，但旧Android替身没有Context、InputMethodManager、getSystemService、getWindowToken、clearFocus。原输出已保留，不是重试变绿。

18:41批准后补齐该既有文件的关系编辑器替身和行为测试。原23后端/17UI检查、11变异全部保留通过；增加2个可观察保存/取消测试、5个整API遗漏编译拒绝、2个有正向见证的静默事件替身变异通过。随后最终字节原21项各一次300秒全部通过。Android/DB/IME仍是明确替身，几何合成，不等于真实设备时序或SQLite验收。

初始专项夹具把Fresh milk误作创建标题，实际是Buy milk后改名；修正并保留首错误。第一版变异锚点碰到自身字符串，改为真实调用行锚点，保留首次输出。交付器真实Git加网络/业务替身的成功与4故障边界通过，目标集合确为五个产品文件。

## 最终候选身份

完整66文件候选树按原始Git路径及模式独立重建：6293597d2b130606e8db92b958cff02ea6789a6a。此为预期树，尚非本轮远端产品提交成功声明。

- ActivitiesScreen.java：58424字节，blobadfe1a3aee0efdda338a7019f5b5c49ae4024f02，SHA25635cc039abbf70fbf493f167ff0f8edad1a5f53116efd454a7067726b172feaef。
- tools/emulator_gate.py：180137字节，blob41ab5025e2ee3f36a73ca0c166af12d81fd4b93b，SHA2568a3b7426243490321d3d79ad69ba27db4f125c847a46c4ec1a9f9fbc70eba2dc。
- tools/verify_app_catalog.py：193269字节，blob64a46bf7da8b71ad347b5d0a5e5527a9b2b3e277，SHA256492d00c5d8bf5b5e4f69a4f20a3c1929ca5a32a3ddde3b663e2d1b6a3d1b1c00。
- AGENTS.md及CLAUDE.md：各16855字节，blobf1cf541fc9aa60b9283fd19e09e16efeb5ca6f42，SHA25690033dc1545b8ba74d0d030d6d1e7567538d5242e89c794fd905d661cb06dba5，配对相同且不超过200行。

## 已确认产品49及前一轮结果

09ff交付39014243730已完成原21项并提交[49aac61dcf63876800d838d2a1880888e7f11980](https://github.com/supercubegame/todo-pocket-android/commit/49aac61dcf63876800d838d2a1880888e7f11980)，单父8f，完整66文件树4580d0e992280453e0b339b34cbf1c40d5147fe5已独立重建一致。旧交接的09ff仍运行/产品8f已过期。

[49主回归39014673122](https://github.com/supercubegame/todo-pocket-android/actions/runs/39014673122)失败：API26到取消恢复后仍用直接find找屏外待办；API34实际RelationEditor没有IME清理。两主API seed155/reopen25通过，导出job绿、[快捷39014671707](https://github.com/supercubegame/todo-pocket-android/actions/runs/39014671707)绿，但完整原始导出/快捷流与数据库回放未全部独立复核。upgrade跳过，没有新验收APK。

## 接续顺序与边界

1. 先读39026184501同suite的分段交付check及relation-ui-delivery归档，核对完整原21项、一次产品ref更新和dispatch结果。
2. 成功后独立读取产品ref、单父49、完整树6293597d2b130606e8db92b958cff02ea6789a6a及五blob，不只信交付器自报。
3. 读取同最终产品SHA的主回归、快捷API26/API34和既有覆盖升级，检查原始失败及证据；不沿用49或旧7920绿灯。
4. 验收齐全才能交付新APK。旧ADB255、c9seed超时及系统ANR仍独立未定因；全v1.2和商业交付未完成，不编百分比。

手机仍是4d8742已验收阶段预览，不卸载、不清数据、不操作手机、不合并发布、不新增PR评论。既有覆盖升级是重建f42旧源并用当前固定密钥，不证明原手机4d证书兼容，也未覆盖原4d包覆盖后再显式激活组合。Actions继续运行不等于助手在对话结束后继续开发。

[前轮完整交接](https://github.com/supercubegame/todo-pocket-android/blob/184c558558c9cc2d805e9f3bbb132963f5b23301/HANDOFF.md)保留09ff及8f原失败；[分页和超时交接](https://github.com/supercubegame/todo-pocket-android/blob/f22706a7b0595ad5548897aea68c8bb6dc91e101/HANDOFF.md)；[7920验收](https://github.com/supercubegame/todo-pocket-android/blob/12a9b7779dca1cd2477c8aee1d00a54d1698a686/HANDOFF.md)；[十一文件授权及原21命令](https://github.com/supercubegame/todo-pocket-android/blob/9a6c72f8c67e2ae3520398833dc1ace7bcfcddf4/HANDOFF.md)。
