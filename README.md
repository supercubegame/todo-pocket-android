# 口袋待办 v1.2 开发中

**没有可交付 v1.2 APK。** 主界面仍继承 v1.1，数据库与媒体字节验证不等于新版界面、真实图片或产品验收。[已发布 v1.1](https://github.com/supercubegame/todo-pocket-android/releases/tag/preview-35575804413-1) · [v1.2 草稿 PR](https://github.com/supercubegame/todo-pocket-android/pull/4)。main、PR3、旧发布及手机数据保持不动。

## 当前实现

原生 Java，SQLiteOpenHelper schema2、FK/WAL/事务。分类与应用关联、活动、路径/标签、分精度账本和重试/撤销日志、打卡日期与录入时间、私有/公开有序图文块、媒体登记、自定义字段及字段笔记、独立普通待办。字段改名不换身份，归档保留旧值和笔记，禁止新值/新关联笔记；原笔记仍可编辑。新记录不继承旧500条/200字限制，但受设备和Cursor内存限制，不承诺物理无限。

旧备份先验证后事务追加，保留原有待办，按来源摘要重映射ID，同一备份重试不重复。不同内容备份可能追加语义相似的待办；预览告知、确认界面及撤销导入尚待接入。不会凭空生成活动/打卡/账目。schema1到2采用非破坏性新增表迁移；旧DDL独立夹具验证部分旧实体和私有内容保留，并非全部异常升级情形覆盖。

## 本轮：全数据库和媒体字节备份恢复适配器

新增 AppDatabase.exportState/exportBackup/restoreBackup。备份格式固定版本、schema2、完整18表及列顺序，逐值标记SQL类型，严格UTF8、长度/尾随校验；拒绝未知表防止悄悄漏备份。读取在一个SQL事务内形成一致快照，保留ID、排序、私有标志、修订号、账目批次载荷/撤销墓碑及旧导入记录。备份含私有内容且未加密，不能当分享包。

恢复先在由可信代码建表的临时内存数据库中验证SQL约束、外键、字段值（包括已归档字段）、日期、有序记录和账本日志，再核对媒体集合、大小、摘要。不执行备份提供的SQL或DDL。复制不可变媒体并回读之后，在**一个数据库事务**中替换全部业务记录并做规范字节回读。临时目录在提交前清理，避免清理失败被误报为已提交数据恢复失败。

**重要边界：**这是替换型底层接口，未来界面必须预览并确认，不是已交付的手机恢复流程。失败不删除/更改旧媒体，数据库回滚；可能留下新复制但未引用的内容文件，安全垃圾回收尚待做，不承诺物理目录完全不变。只实现schema2完整快照，旧普通待办格式走独立导入；不接受未知未来schema。8MiB状态/清单限制是暂定资源保护，不是容量实测。断电、写入中杀进程、磁盘写满、真实照片解码、SAF/云盘、预览过期保护和撤销恢复均未验收。

## 验证与实际失败记录

快速：`python3 tools/verify.py v12`，真实JDK17，旧核心54、领域82、文件49。设备：`gradle --no-daemon --console=plain assembleDebug assembleDebugAndroidTest lintDebug`，再在隔离CI上分别运行`TEST_API=26 python3 tools/emulator_gate.py`和34。构建后验证包/版本/无权限/签名并安装，seed/reopen之间强停且检查原进程不存在。

原字段阶段a009f749 /35616574786，两档各94检查通过。本轮先行7203da4529714567915fc720ee3e9410501957e6 / [35619172618](https://github.com/supercubegame/todo-pocket-android/actions/runs/35619172618) 两档通过原76项seed后因缺少exportState失败；首个实现24801c3b / [35619931896](https://github.com/supercubegame/todo-pocket-android/actions/runs/35619931896) 能导出完整快照，但非法日期直接冒出底层DateTimeParseException。修复在候选数据校验边界统一包装并保留原始cause，没有放宽日期规则或测试捕获。

新增设备夹具每表都有数据，用独立编码器比较完整快照，实际生成ZIP并验证原媒体字节。合法ZIP内装缺媒体/多媒体/未知schema/尾随/非法字段/日期/顺序/账本日志等坏数据，必须拒绝且旧数据库完整不变；后置SQLite触发器故障必须命中精确注入原因并回滚，再验证成功、重复恢复和重开后的原账目撤销/导入幂等。

设备报告只有同时具备全部关键恢复断言、计数匹配和正常instrumentation退出才标`SCHEMA2_DB_MEDIA_BYTES_PASS`。解析器另做正负夹具自测，不计入产品设备功能数。两个API必须都通过才汇总恢复通过；`ui.status=NOT_TESTED`仍表示未测界面，`release_ready=false`。完整实际结果以对应提交的evidence报告为准，不把当前文字当通过证据。

## 仍待完成

计划/快捷关联/模板/搜索、普通待办删除/排序、原生Today/Activities/Calendar/NoteEditor、真实图片选择/解码/缩略图/裁剪遮挡、PDF/分段图片/Markdown+assets分享、SAF恢复预览确认、真实界面测试/截图/真机试用。账本汇总仍全量加载，规模优化未做。分享过滤不是截图遮挡，不能夹带未遮挡原图。

固定内部包com.supercubegame.pockettodo.v12.preview、1.2/code3、min26/target34/compile35，desugar_jdk_libs2.1.5。`python3 tools/verify.py build`继续故意阻断产品交付，内部测试构建独立执行；不上传APK、不创建Release。长期签名需可信本地生成与备份，密钥不进聊天/源码/日志。无云同步、自动打卡或付费服务。批准范围：[docs/V1_2_PLAN.md](docs/V1_2_PLAN.md)。
