# 口袋待办：当前接续入口

2026-10-16 16:47继续轮。10b90458的21项原主机验证通过，但API26/API34实际测试均报Process crashed，不能接受。原始归档只读恢复已完成，未找到足够崩溃栈定因；已提交不改产品和测试源码的崩溃缓冲区采集，绑定新诊断运行。没有新APK、产品推送、合并、发布或手机操作。

## 首要动作：读取新诊断，而非猜测修复

[诊断提交9e93888af2ed2450a6d1077379edfc3595913f04](https://github.com/supercubegame/todo-pocket-android/commit/9e93888af2ed2450a6d1077379edfc3595913f04)，[CI38877832949](https://github.com/supercubegame/todo-pocket-android/actions/runs/38877832949)，run61、push、attempt1、suite105358792481，最近读取in_progress。提交2026-10-16T09:03:25Z，tree70ca3c535e909e7d374b7e6f67541eccaae23ece。

只更新ci/shortcut-storage-preflight-4d8742既有.github/workflows/shortcut-storage.yml。24666字节，blob c4ebc9b185542c900c8b6b0fbc22ae04dec7a27e，SHA256 38fd8d10d9504745f8ff1e16f7c43fb94b95da73268f53a40f3060c85bfe5ed0。本地、写响应、独立不可变目录一致，无待批准安全事项。

不可变10b工作流恢复全部66个原run脚本，host36/device15/report15，逐项本地核对一致。保留原21命令及300秒预算、原作业预算、原源码和测试内容，不修产品、不放宽断言、不无条件重试。步骤显示名称简化，但原脚本及边界未合并。原Android执行命令只调用一次，外部观察器同时等待固定emulator-5554并读取logcat crash缓冲区，记录命令、退出码、时间、字节数、摘要及本次身份。不清日志、不杀ADB服务、不碰手机。结束时只停止自己创建的观察进程。

本地真实子进程1正例、5反例和1整段失败保留守卫省略控制通过，并嵌入设备步骤永久运行。原命令exit7必须仍返回7；移除该守卫后错误变成0，证明控制有效。空数据、等待失败、超时和超限明确不是验证成功。Android行为仍须读取新CI，不能用本地假ADB当实际设备。

新增crash-diagnostic/receipt.json、crash.stdout/stderr、wait.stdout/stderr随原设备归档上传。完整文本分片发布至名为Crash diagnostic API26/API34的检查，逐项独立读回。单成员超过256KiB时拒绝宣称完整发布，完整产物仍保留；采集端4MiB限制会明确标记超限。新日志是新诊断运行的证据，绝不是10b原始崩溃现场，也不是产品修复或验收。CAPTURED只说明有字节，不说明已找到本应用根因。应读取receipt和完整crash.stdout，确认实际包名、线程、异常和调用栈。

## 10b原始失败与恢复结果

[原失败CI38871586910](https://github.com/supercubegame/todo-pocket-android/actions/runs/38871586910)，commit10b90458f365931e6d87df0d389fabca9a9f09d9，attempt1。完整主机收据116880673385、116880679401已读：21命令一次、300秒、return0、无超时；第21耗时206.87365085200003秒。stdout24807字节、SHA256 38e5f6a6d99d7affa6403f0f26cccb900eb615f6c2b978c6d67a5459cf098acc，stderr为空。未逐行读完整stdout。

[API26原失败](https://github.com/supercubegame/todo-pocket-android/runs/116882548549)和[API34原失败](https://github.com/supercubegame/todo-pocket-android/runs/116882554664)完整原始流已读：seed仅74字节，INSTRUMENTATION_RESULT: shortMsg=Process crashed.，INSTRUMENTATION_CODE: 0。postddl complete ordered checks是缺失标签的次生报错，不能拿它定根因。没有新场景PASS、seed/reopen验收或新数据库回放成功。

[只读恢复4a4343d9 / CI38876272396](https://github.com/supercubegame/todo-pocket-android/actions/runs/38876272396)已直接读到success，未重跑设备、未推产品。[完整原始归档清单](https://github.com/supercubegame/todo-pocket-android/runs/116892135139)已读。两个原ZIP的来源、大小、摘要、唯一成员、路径、展开预算、CRC均校验；所有UTF-8文本成员已发布分片。清单没有独立logcat/crash栈文件；API34完整shortcut-android.log四片已读，只有主机自测、SDK/模拟器启动、原控制流程和次生解析失败，没有应用崩溃栈。API26该大日志尚未逐片完整审计，不夸大读取范围。

原API26归档12034895391，17670字节，SHA256 0f2f018adead0861bf736089d0f489c237ec76b9942def69dd4ecfc23f2552b0。原API34归档12034347759，19219字节，SHA256 764f2c63feec8d3d7f338f93e053b73b3fbc40ac4089e91c2989aa046be61971。主机12033921467、452909字节、SHA256 8c195751a5bc1f8a9eeac5eb780b08bfc0779cf5c47f5fe82c20523e4fa9f226；报告12034736220、5129字节、SHA256 ff01af498311ed66f0a864526d9eb96ccb31adcfc3423296810a6b319275f7b6。后二者未下载。

[API26构建原收据](https://github.com/supercubegame/todo-pocket-android/runs/116892020407)和[API34构建原收据](https://github.com/supercubegame/todo-pocket-android/runs/116892085288)均完整读到PASS，绑定10b原run。两端实际Android编译成功，但不是运行验收；均为一次性签名，不可作为稳定覆盖升级APK。

10b工作流28332字节/blob e8c08c036b3a074c43d288aa269d01c4d72b311f。DeviceTest109218字节/blob93890332b2f6e3a7f4b582897e55a954a612e83c/SHA256317a64ff38b9b337198b0cff8433346b97db9cebf2e34b131cc1959ad0fc21aa；verifier350004字节/blob6f81b048e1ff8a7b759809f29afd42b76fa3af94/SHA25609ce976924c7cb06ecb2286d0baa1c91c79406e105fb05e71b55ac0271c8308a。

## 已接受基线与后续顺序

最新完整已验收隔离基线仍fa12481ce8013304aa47d9d848025496ab1242d3：[CI38865507655](https://github.com/supercubegame/todo-pocket-android/actions/runs/38865507655)。原21主机、双API完整seed/reopen、确认事务消费同意前退出、双库独立回放及汇总已复核通过。不能用其绿灯接受10b或新诊断。

[上一份不可变交接8f279530](https://github.com/supercubegame/todo-pocket-android/blob/8f279530eea0b2c5b1aa3187f41f0dd9894f0a3d/HANDOFF.md)保存fa全部身份与验收、10b真实双场景设计、13故障/2整段断言省略/1调用省略、原始授权和旧链入口；其中10b pending由本文失败状态替代。新测试拟在真实确认线程第二次备份摘要处验证已处schema4事务，分别继续提交及注入故障回滚；本地Android/SQLite为替身，实际设备未接受。不能猜测getReadableDatabase、Error逃逸或夹具重建就是根因。

先读9e938诊断的原始崩溃栈，确定首失败属于产品、测试观察器还是环境；做原路径RED、最小修复GREEN和有意义反例，恢复10b验收基线加最小修复，实际提交/独立远端/同提交原21及双API。随后转向已批准产品集成、AGENTS/CLAUDE同文不超200行、原子非强制产品推送、同最终产品提交双API及稳定签名旧APK覆盖升级，最后交付APK。不任意扩展无关竞态；不把诊断绿灯当产品验收。

产品最后核验3a5a17e1fdc570c73804007cd9a4d2ef36c0966b；手机4d8742预览。近期产品推送0，无新APK。ADB255/ANR根因未证实，其余功能、真实照片/EXIF/输入法/大字体、性能/存储失败、商业签名分发未全验，无可靠整体百分比。文档不能代替代码交付。

沿用[十一文件授权与原21命令](https://github.com/supercubegame/todo-pocket-android/blob/9a6c72f8c67e2ae3520398833dc1ace7bcfcddf4/HANDOFF.md)：既有凭据，明确同意、已校验备份先于迁移、普通启动不自动迁移、失败关闭、不清用户数据、不卸载、不操作手机、不启动外部应用、不合并发布。单分支一个写入者，跨账号不假定继承沙箱或短期artifact，对话结束不表示助手继续开发。

本地辅助文件位于/home/user/work/startup-ui：crash-observer.py、test-crash-observer.py、build-crash-workflow.py、crash-workflow.json、crash-candidate.yml；原postddl文件均保留。跨账号优先不可变GitHub工作流及原始证据，不依赖这些本地路径。
