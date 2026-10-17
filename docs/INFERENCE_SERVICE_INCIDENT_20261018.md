# 2026-10-18 原8B推理服务退出：事实、限制与恢复边界

这是一份运行事故记录，不是方法效果或根因已解决的声明。时间同时保留UTC与北京时间。

## 已观察到的事件

- 2026-10-18 04:23:25 CST（2026-10-17 20:23:25 UTC），在同一个
  `artifacts/gpu_generation.lock` 下，核实原服务PID2261314及其启动身份后，
  发起两个合成输入的能力检查。没有使用合同、Gold、正式TEST或教师调用。
- embeddings请求没有产生向量：HTTP200的body返回model不支持Embeddings API的400错误。
- 随后一次chat请求设`max_tokens=1`、`logprobs=true`、`top_logprobs=20`、关闭thinking，
  约0.149秒后HTTP500：`EngineCore encountered an issue`。没有生成token或概率。
- 此后原主进程2261314及GPU引擎2261698都已消失；`/health`和`/metrics`连接拒绝。
  04:26:54 CST再次检查时，两PID均不存在，`nvidia-smi`没有compute-app。
- 本次没有发送重试，没有执行kill、服务重启、权重下载、切换模型或删除操作。
  但能力请求由本助手发起，紧接着发生服务退出；不能把事故淡化为仅“不支持接口”。

两个实际请求、响应、时间和耗时见
`artifacts/research/frozen_8b_semantic_feature_capability_20261018/`。

## 根因尚未查明

- 对04:10–04:30原主PID的journal查询无条目；对04:15–04:30 kernel journal查询亦无条目。
- 当前`dmesg`尾部没有本次OOM/GPU错误。历史NVRM版本不匹配告警截至10月16日，
  不能拿它作为本次退出的已证原因。`coredumpctl`未安装。
- 已找回的旧`orphaned_original_vllm_server_log_recovered.log`仅截至10月15日01:04:59，
  其中的旧NCCL Broken pipe不是10月18日本次堆栈。
- 按用户及删除文件检查未发现原模型权重或服务日志仍被存活进程持有。
  尚未获得本次EngineCore具体异常堆栈，不能断言是OOM、logprobs参数或某个CUDA缺陷。

## 恢复边界

- 此前已记录原权重及旧venv在磁盘缺失，服务靠原存活进程运行；本次不发生新的源码删除。
- 原路径、当前项目对应模型路径、常用HF缓存及home/vdb深度5的Qwen目录检查中，
  没有找到同一Qwen3-8B完整副本。发现Qwen3-VL-8B目录不等于同一模型，不作替换。
- 原主进程和引擎均退出后，不能再通过它们的FD或GPU常驻内存恢复原运行实例。
  这不等于已经穷尽所有存储取证手段，也不承诺可以复原原始权重SHA。
- 当前不能继续native律师生成。CPU工件、代码、数据和教师记录仍在；
  不据服务故障重开已证负收益的长训练，也不谎称后台训练仍进行。
- 若无用户提供的同权重副本，恢复将需要重新获取同一Qwen3-8B并重建推理环境，
  记录实际revision/hash、依赖与配置，以新运行身份验证。未经确认不下载、重启或换模型。
  原权重SHA未找回，即使模型名称相同，也不能声称与原实例位级一致。

## 已完成实验与保全

- 最近教师更新CPU检验04:16:55已完成，非仍在运行：同18来源普通工具
  TP171/FP32/FN116/F1=69.7959%，最新发布3程序/37特征为176/57/111/F1=67.6923%。
  实际1教师、0新native；全部合法UPDATE3发布，不回滚或择优。
- 其后只读排序审计也负于普通：mAP85.6246%对83.7352%。
  不以固定阈值作唯一借口，不把组件分数充当律师或正式测试成绩。
- 最新实际终态归档在两个不同文件系统均重新核验SHA256：
  `e947349e6cd518a5a27ff1f5586860895d010cc1261899d2e700d5cacd6a1f76`。
  完整Git `eb69017`两盘bundle的SHA均为
  `580bedb22a35614c61fc896e4e92187e27f7301d4aa6fc6a6cd3a15d04d196a6`。
- 两盘位置为`/media/sangfor/vdb/legal-skill-backups`与
  `/home/yndx/hhy/legal-skill-rootdisk-backups`。这是同机两文件系统，
  不是异地、权重或整机快照。事故后新审计/事故证据将单独归档，不冒充早先终态内容。

Goal仍active且未完成。恢复同一模型所需的新操作应明确请求确认，
不因本事故把方法失败解释成“无标签不能技能学习”。
