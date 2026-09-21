# 口袋待办 v1.2 开发中

**没有可交付 v1.2 APK。** 主入口已改为真正的原生 TodayScreen/ActivitiesScreen，不再展示继承的 v1.1 界面，但只接通待办、分类、手动活动路径和当天打卡这一小段，不能当完整 v1.2。[已发布 v1.1](https://github.com/supercubegame/todo-pocket-android/releases/tag/preview-35575804413-1) · [v1.2 草稿 PR](https://github.com/supercubegame/todo-pocket-android/pull/4)。main、PR3、旧发布及手机数据不变。

## 当前原生界面阶段

普通待办新增、编辑、勾选与筛选；分类新增、改名及上移/下移；分类内手动创建活动，多行有序操作路径，当天完成或跳过。今天使用中国时区，录入时间独立保存。不会自动操作其他应用，不会从打卡生成账目，没有虚构示例数据。分类拖拽、应用目录/字段/日历账本/笔记、删除排序、恢复与分享入口仍待做。

SQLite 读写放到单一后台执行器，主线程只显示结果；保存期间阻止重复提交，关页后按排队顺序关闭数据库。独立 pocket-v12.db 不读旧包或旧 SharedPreferences。本阶段未保留旧 UI 的导入导出按钮，避免把 Todo-only 恢复误用于完整活动数据库；安全恢复确认流程接好后再开放。输入框不加旧200字限制，列表暂为全量渲染，规模性能和大字体尚未专项验证。

真实测试命令仍为 tools/emulator_gate.py，先跑数据库 seed/reopen，再启动 MainActivity，用 adb 实际点击/输入完成操作与强停重开，最后独立读取 Android 产生的 SQLite/WAL 核对身份、标题、分类、路径与打卡，无测试后门或直接给界面塞数据。真实 screencap 截图和简版 native 报告按源码SHA/run/API写回 evidence，并逐字节读回。截图用合成测试内容，不含真实用户记录。

先行测试7daac867 / [35623884882](https://github.com/supercubegame/todo-pocket-android/actions/runs/35623884882)：两档均完成原158项数据库检查，新界面检查因仍显示旧版、缺少v12-home而失败。首个界面实现3d929587 / [35624525564](https://github.com/supercubegame/todo-pocket-android/actions/runs/35624525564) 编译成功，但lint拒绝用数字0表示字体常量；改为Typeface.NORMAL，未压制lint。当前提交是否通过，必须读其实际报告，不将这份实现说明当验收结果。

## 已有数据能力与边界

原生 Java，SQLiteOpenHelper schema2、FK/WAL/事务。分类与应用关联、活动、路径/标签、分精度账本和重试/撤销日志、打卡日期与录入时间、私有/公开有序图文块、媒体登记、自定义字段及字段笔记、独立普通待办。字段改名不换身份，归档保留旧值和笔记，禁止新值/新关联笔记；原笔记仍可编辑。新记录不继承旧500条/200字限制，但受设备和Cursor内存限制，不承诺物理无限。

旧备份先验证后事务追加，保留原有待办，按来源摘要重映射ID，同一备份重试不重复。不同内容备份可能追加语义相似的待办；预览告知、确认界面及撤销导入尚待接入。不会凭空生成活动/打卡/账目。schema1到2采用非破坏性新增表迁移；独立旧DDL夹具验证部分旧实体和私有内容保留，不是全部异常升级覆盖。

## 全数据库和媒体字节备份恢复适配器

AppDatabase.exportState/exportBackup/restoreBackup 的固定版本格式包含schema2完整18表及列顺序，逐值标记SQL类型，严格UTF8、长度/尾随校验；拒绝未知表，避免漏备份。在一个SQL事务内形成一致快照，保留ID、排序、私有标志、修订号、账目批次载荷/撤销墓碑及旧导入记录。备份含私有内容且未加密，不能当分享包。

恢复先在由可信代码建表的临时内存数据库中验证SQL约束、外键、字段值（包括已归档字段）、日期、有序记录和账本日志，再核对媒体集合、大小、摘要。不执行备份提供的SQL或DDL。复制不可变媒体并回读之后，在一个数据库事务中替换全部业务记录并做规范字节回读。临时目录在提交前清理，避免清理失败被误报为已提交数据恢复失败。

这是替换型底层接口，不是已交付手机恢复流程。失败不删除/更改旧媒体，数据库回滚；可能留下新复制但未引用的文件，安全垃圾回收待做，不承诺物理目录不变。只支持schema2完整快照，旧Todo格式独立导入；拒绝未知未来schema。8MiB状态/清单预算是暂定资源保护，不是容量实测。断电、写入中杀进程、磁盘写满、真实照片解码、SAF/云盘、预览过期保护和撤销恢复均未验收。摘要只防损坏，不证明来源可信。

设备夹具18表均非空，用独立编码器比较完整快照，实际生成ZIP及验证媒体字节。合法ZIP内的缺/多媒体、未知schema、尾随、非法字段/日期/顺序/账本日志必须拒绝并保留旧数据库；后置SQLite触发器故障须命中精确注入原因并回滚，再验证成功、重复恢复和重开后撤销/导入幂等。媒体仍为合成字节，不是照片。

历史先行7203da45 /35619172618：直接读到API26完成原76项seed后缺exportState，两档任务失败，但API34尾部读取不完整，不宣称同因已直接核实。24801c3b /35619931896 暴露非法日期底层异常越过公开错误边界，统一包装并保留cause，未放宽日期规则或测试。d3b7fea5 / [35620932028](https://github.com/supercubegame/todo-pocket-android/actions/runs/35620932028) 已验证两档各158项数据库/媒体字节检查。

## 验证与未完成部分

快速：`python3 tools/verify.py v12`，真实JDK17执行旧核心54、领域82、文件49。设备：`gradle --no-daemon --console=plain assembleDebug assembleDebugAndroidTest lintDebug`，随后隔离CI上分别运行`TEST_API=26 python3 tools/emulator_gate.py`和34。核对独立包、版本、无权限、签名并安装；seed/reopen之间强停且检查进程不存在。恢复解析器要求关键检查名、实际PASS数量及正常退出；另有解析器正负自测，不计入设备产品功能数。

报告将完整数据库/媒体字节恢复、有限原生交互、完整产品验收分开。缺失或未执行绝不算通过。顶部JVM scope仍描述快闸门，设备和原生UI结果在ui.devices/ui.native，简版截图索引为reports/native-<SHA>-<run>.json。产品release_ready=false；UI部分通过不代表SAF、图片或三格式分享通过。

仍待完成：分类拖拽、计划/快捷关联/模板/搜索、普通待办删除/排序、应用/字段/Calendar/NoteEditor界面、真实图片选择/解码/缩略图/裁剪遮挡、PDF/分段图片/Markdown+assets分享、SAF恢复预览确认/过期保护/撤销、旋转时弹窗草稿/写入生命周期、大字体/规模与真机验收。账本汇总仍全量加载。分享过滤不是截图遮挡，不能夹带未遮挡原图。

内部包com.supercubegame.pockettodo.v12.preview、1.2/code3、min26/target34/compile35，desugar_jdk_libs2.1.5。`python3 tools/verify.py build`继续阻断产品交付，历史错误文本与保护断言耦合，不表示内部编译没跑。不上传APK、不创建Release。长期签名需可信本地生成与备份，密钥不进聊天/源码/日志。无云同步、自动打卡或付费服务。批准范围：[docs/V1_2_PLAN.md](docs/V1_2_PLAN.md)。
