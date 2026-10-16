# 口袋待办：当前接续入口

2026-10-16 22:06继续轮。42f2产品交付失败，原21项主机全部通过，提交前未跟踪文件保护拒绝；产品引用更新0，dispatch0。独立读取产品ref确认仍3a5a。已提交只读逐命令诊断4281d7fa，最新读取CI38913592925主机执行中。目录隔离修复仅本地候选，尚未提交，不得宣称已修复、已交付产品或新APK。

## 下一步优先读取当前诊断，不盲目重跑

[诊断4281d7fadb9a49b08084ba488123c6b012f76ef0](https://github.com/supercubegame/todo-pocket-android/commit/4281d7fadb9a49b08084ba488123c6b012f76ef0)，[CI38913592925](https://github.com/supercubegame/todo-pocket-android/actions/runs/38913592925)，run64，attempt1，suite105458096729，job117015288097，提交2026-10-16T14:10:11Z。恢复原driver和本地保护测试步骤均success，Original21 commands步骤最后读取in_progress。工作流6591字节，blob c53c2d547add1979d4f954b48efa8dba968ec16e，SHA256 34e3c3eaeccc77c3228242d70e6f9702bd50fea5ca86274db0926e416f773145；写入响应和独立不可变目录一致。

诊断只改现有隔离分支.github/workflows/shortcut-storage.yml。用摘要固定恢复42f2原完整driver/原传输测试，保留原21命令、顺序、次数、300秒预算、stdout/stderr及原最终未跟踪文件拒绝。在每条命令后记录git ls-files未跟踪路径及文件大小/摘要，最后再次记录；不删、不忽略、不移走原输出。即便未再复现也在任何产品写请求前明确DIAGNOSTIC_ONLY_NO_PRODUCT_WRITE退出，并且token只有contents:read/actions:read/checks:write。失败检查是预期的诊断结果，不把红灯改绿。新观察不是原42f2现场，必须区分。

本地真实临时Git已验证观察空目录、确切新增文件身份、保留原拒绝及不删除文件；实际工作流恢复程序已执行并比对输出AST与本地观察补丁，shell和Python语法通过。原传输测试保留。准备过程中嵌入Python缩进问题在本地发现修正，未提交有语法错误版本。

## 42f2原始失败已完整读取

[原CI38897460634](https://github.com/supercubegame/todo-pocket-android/actions/runs/38897460634)，commit42f2ae2fc8bfd6de86a92aed21784da195aee31c。[回执1/2](https://github.com/supercubegame/todo-pocket-android/runs/116964423073)和[2/2](https://github.com/supercubegame/todo-pocket-android/runs/116964428380)均完整读取。原21项全部attempts1/budget300/return0/timed_out=false，第21项254.33621607499998秒，stdout25258字节/SHA256 75e5382e8a80c35513de3ef87d538f21e00d879f235899460b3d76bd5adba08d，stderr空。

实际首失败：deliver-accepted.py第224行，git ls-files --others --exclude-standard并非空，AssertionError: no untracked product paths。失败前原已跟踪八文件范围检查通过。回执product_ref_updates=0、dispatches=[]、failed_stage=STARTED，尚未创建/提交产品commit。原回执没有列出未跟踪路径，不可把猜测称为原现场根因。归档[12045121587](https://github.com/supercubegame/todo-pocket-android/actions/runs/38897460634/artifacts/12045121587)保留原主机输出及已验收候选归档，本轮未下载该ZIP。

实际tools/verify.py固定3a5a已读取，blob c9388d4f110050e045c96cda71d0542010b42b94：core()在工作目录创建build/core并编译CoreTest等class，v12在build中执行其余临时夹具。同提交.gitignore读取不存在。这支持生成物污染提交工作目录的假设，但仍须读4281逐项实际观察确定完整文件清单及出现时点。

## 目录隔离候选，仅本地，尚未提交

最小方案：保留产品提交目录原来的未跟踪文件必须为空保护，另外用git worktree add --detach建立独立验证目录，应用完全相同八文件，在那里运行全部原21命令。输出和验证目录随诊断归档保留，不删除或忽略。验证结束检查所有受跟踪变化范围、候选逐字节内容和文件模式均符合；提交目录仍要求无未跟踪路径。原单次force=false引用更新、完整远端树/父提交/全部blob读回和两个workflow_dispatch流程保持。

本地真实Git+实际Java编译已重现原同目录生成class导致RED；隔离后验证目录含class但提交目录干净GREEN；候选内容、其他受跟踪文件、执行位三种故障均被拒绝；原RED生成物保留。完整补丁driver配原传输套件的成功和4个原故障路径也通过。GitHub和21条业务命令在传输套件仍为明确替身，不是新的真实21主机或设备验收。

本地/home/user/work/startup-ui包含isolate-delivery-validation.py、test-validation-worktree.py、build-worktree-delivery.py、worktree-delivery.yml、worktree-isolation-local.log及原deliver-accepted.py/test-deliver-accepted.py/accepted-delivery.yml。候选工作流7041字节，blob d90744a609a76f4df0de5f56357d1d9f356dcafb，SHA256 551d88305d58921635757ec3672cbe56418b526abfbb35aac8c951ec79a56789。工作流从42f2不可变载荷恢复原driver，并嵌入隔离补丁与完整本地测试；恢复后逐文件身份已验证。这仍是LOCAL_CANDIDATE，不是已提交产品。跨账号不能假定本地路径存在，必要时按上述边界重建，原driver在42f2工作流中可校验恢复。

诊断完成后先读取所有分段回执，核验生成文件来自哪些原命令；若符合生成物问题再提交隔离修复。不要在未知其他源文件污染时直接放宽保护，也不要重跑同一旧交付。修复CI仍必须从固定7920已验收归档恢复六源文件及配对文档，重跑原21，然后实际单提交与独立远端核对，读取新产品同SHA的设备和升级CI。

## 已验收基线、授权、剩余边界

[上一不可变交接12a9b777](https://github.com/supercubegame/todo-pocket-android/blob/12a9b7779dca1cd2477c8aee1d00a54d1698a686/HANDOFF.md)完整保留7920原21/双API/双库回放、每个候选与归档身份、八文件交付设计。其42f2 pending已由本页原失败取代。最新完整隔离验收仍7920bbe315a61cdfd7c8af78cc54f30cee254da8/[CI38884051157](https://github.com/supercubegame/todo-pocket-android/actions/runs/38884051157)，不等于产品/覆盖升级验收。

产品ref本轮独立确认3a5a17e1fdc570c73804007cd9a4d2ef36c0966b；手机仍4d8742。AGENTS/CLAUDE交付候选12647字节、blob f8823316934f4ef3ad84607a14b19362972af5fd、SHA256 6c8219ad15f0f74d409bb20aed7bb13cbdc581a3c99e752875dc4a505863e316，二者相同。

[十一文件授权与原21命令](https://github.com/supercubegame/todo-pocket-android/blob/9a6c72f8c67e2ae3520398833dc1ace7bcfcddf4/HANDOFF.md)继续有效；没有待批准安全事项，不重复询问已批准范围。既有凭据、明确同意、验证备份先于迁移、普通启动不自动迁移、失败关闭，不清用户数据、不卸载、不操作手机、不启动外部应用、不合并发布。

剩余主线：实际产品提交、同提交双API、稳定签名覆盖升级及显式激活组合、APK。原android.yml的历史升级源仍f42，不是用户当前4d APK到新APK加显式激活的全部证明。旧ADB255/ANR根因仍独立待查；全v1.2/真机UX/性能/商业分发未完成，不编整体百分比。对话结束不表示助手继续开发，已经提交的Actions会自行执行。
