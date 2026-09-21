# 口袋待办 v1.2 开发分支

**当前不是可安装的 v1.2 成品。** 基于 v1.1 7146894687f785a7191b84e7c62070fe0fe6aa8d 分阶段开发，PR #4 以 v1.1 工作分支为比较基线，未合并 main，也没有替换旧 APK。

## 当前能执行的内容

使用 JDK 17 运行 `python3 tools/verify.py v12`：先运行原有 54 项核心回归，再从干净临时目录编译运行 V12CoreTest。前一实现提交 3cc34712ae6237226cfa6cab07f9a9bd05d0442d 的实际运行取得 82/82 新契约通过；此数字属于纯 Java 数据规则，不是 82 项 Android UI 验收。

已实现的领域模块：分类稳定 ID/改名/排序、应用跨分类快捷关联、活动归档；金额按分计算、实际与预计隔离、多日筛选、批量校验和重试幂等、受保护的最新批次撤销及显式更正；按星期日历、打卡与补记；有序图文块、快照及私有块分享筛选；基础类型自定义字段。

尚未实现/验收：这些模块的数据库持久化、图片实际复制和大图加载、笔记编辑界面、日历交互、PDF/图片/Markdown 导出、媒体备份恢复、v1.1 备份迁入、独立 v1.2 APK 和真机体验。路径/标签/活动完整状态等产品功能也仍需接入扩展，不能把小型分类模型当作完整活动管理。

当前 `build.gradle` 和旧 Activity 仍来自 v1.1。`python3 tools/verify.py build` 在此分支会明确拒绝执行，防止把旧界面重新命名为 v1.2。CI 只有 core 和 evidence report，并将 Android、导出、恢复全部标为 NOT_TESTED，不发布 APK。转换到下一阶段时必须同步修改这些状态和断言，不能只删保护就发布。

## 数据与交付边界

原版 com.supercubegame.pockettodo、v1.1 com.supercubegame.pockettodo.safe.preview 均保留。v1.2 计划使用独立 com.supercubegame.pockettodo.v12.preview，Android 8.0 起；尚未生成该包。只使用合成测试数据，不能把用户真实截图、账本、应用清单放到公开仓库。

预览使用一次性 debug 签名，不承诺以后覆盖升级。稳定包和长期签名待用户本地安全生成、备份和配置 Secrets，私钥不得进入聊天、源码、附件或日志。v1.1 用户反馈“安卓测试好像正常”不能外推为 v1.2 或所有功能逐项通过。

## 计划与证据

详见 [批准的32文件计划](docs/V1_2_PLAN.md)。失败和通过均回写 evidence 分支 `reports/<source-SHA>-<run-ID>.json`，钉住运行并逐字节读回。仅阶段通过不等于完整验收。第一轮缺少 Ledger 的真实红灯、集合空值检查失败与后续修复证据均保留。

构建兼容性注意：领域逻辑使用 Java 集合不可变 API，Android 8.0 支持必须在 APK 阶段通过适当代码/API desugaring 和真实设备测试验证，纯 JDK 17 通过并不替代它。
