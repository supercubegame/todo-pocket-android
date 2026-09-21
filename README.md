# 口袋待办 v1.2 开发中

**尚无可交付 v1.2 APK。** 内部包用于数据库/文件测试，主界面仍继承 v1.1，不是新版 UI 验收。[v1.1 已发布预览](https://github.com/supercubegame/todo-pocket-android/releases/tag/preview-35575804413-1) · [v1.2 草稿 PR](https://github.com/supercubegame/todo-pocket-android/pull/4)。main、旧发布和 PR3 未改。

## 当前实现

领域规则：分类/应用关联、精确账本、打卡日历、字段、有序图文引用。Android 数据库：系统 SQLiteOpenHelper+FK/WAL/事务，分类顺序、应用/活动、路径/标签、账本批次重试/撤销、日期/录入时间、笔记顺序/私有标志/媒体登记。

本轮 schema2 增加字段定义/有序选项/活动字段值、字段笔记关联、独立普通待办与旧备份导入记录。字段复用领域验证，改名不换ID；归档保留已有内容，拒绝新增值和笔记。多选去重保序，false 与未填区分，空列表明确清空。新待办与长文本不继承旧格式的500条/200字限制，但仍受设备资源约束，不承诺物理无限。

旧备份先验证，再事务追加为普通待办，不覆盖现有记录、不伪造活动/打卡/金额。导入身份来自备份摘要，条目ID加来源前缀；同一份备份再次导入为无操作，第二条冲突也整批回滚。**内容修改后的备份视作另一来源，可能追加相似待办；未来界面必须先预览明确告知。** 导入界面和导入撤销尚未实现。

schema1到2是新增表迁移，测试夹具冻结旧版完整建表语句，不通过当前onCreate伪造旧库。检查旧分类、活动、私有笔记和打卡保留，用户修订号不变，字段可用、外键无损。更高未知版本仍拒绝打开，不清空重建；异常迁移和断电覆盖尚待加强。

文件层已实现内容摘要复制/去重/校验、锁保护的私有目录原子重命名、ZIP清单/大小/摘要/预算验证及新目录暂存。合成文件不是图片解码验收，登记媒体也不等于文件有效。ZIP状态仍为待数据库解释的数据，不是完整业务备份恢复。

## 验证

快速命令：`python3 tools/verify.py v12`，JDK17，原54+领域82+文件49项。

设备：`gradle --no-daemon --console=plain assembleDebug assembleDebugAndroidTest lintDebug`，再在 GitHub 隔离 runner 运行 `TEST_API=26 python3 tools/emulator_gate.py`（另一档34）。固定独立包com.supercubegame.pockettodo.v12.preview，1.2/code3，min26/target34，desugar_jdk_libs2.1.5。seed/reopen分别运行，中间强停并验证进程不存在；不是写入中杀进程、系统重启或断电测试。

上一基线41165adf /35613984527，两档各50项设备检查通过。新增字段测试先行e35624ef6dc66869c39aa6f9b6ede4824ae4ce40 / [35615624880](https://github.com/supercubegame/todo-pocket-android/actions/runs/35615624880)：API34通过先前seed38项后因缺少defineField失败；API26是启动时单次adb查询超时，没到字段测试，不能说成同一种失败。本轮修复启动轮询，仅在原240秒总时限内重试未完成的启动探针，不忽略产品断言。最新结果以对应SHA的evidence报告为准。

历史硬链接在两档Android被拒绝，现已改同私有目录原子重命名，加JVM锁/持久OS锁，在锁内检查目标不存在；拒绝覆盖已有文件。只支持协作的私有写入者，不用于其他App可写目录，SAF从已验证快照另行复制。不等于断电耐久性。

产品交付入口`python3 tools/verify.py build`继续故意阻断；错误字符串为保护断言保留，不表示内部APK没有编译。只上传日志、不上传APK、不创建Release。报告ui.devices是真实设备结果，ui.status=NOT_TESTED表示未测UI，release_ready=false。

## 待完成

计划/快捷关联/模板/搜索、全数据与媒体备份恢复、原生Today/Activities/Calendar/NoteEditor、图片选择/解码/缩略图/裁剪遮挡、PDF/分段图片/Markdown+assets分享、真实UI自动验收/截图/真机试用。账本汇总仍全量加载，规模优化未做；8MiB备份元数据/状态限制是暂定保护，不是容量测量。

备份未加密，摘要不证明作者；分享过滤不是截图遮挡，分享包不得带未遮挡原图。无云同步/自动打卡/付费服务。长期签名需要用户可信本地生成备份和配置，密钥不得进聊天/代码/日志。debug不是长期升级通道。

批准32文件及完整计划：[docs/V1_2_PLAN.md](docs/V1_2_PLAN.md)。
