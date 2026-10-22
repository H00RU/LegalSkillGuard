# ACE v3：原始引用列表与法律答案分离

2026-10-22。封存TEST仍未读取。此修订依据实际TRAIN B2及固定上游代码，
不是整项研究的事前注册，也不是已获得公平方法优势的声明。

## 根因与停止

旧ACE run01的B2中204/212 EC返回有效JSON和法律答案，但引用了重复的已知
技能ID。本地Online与decoder额外将其判为整题解析失败，虽然发送的schema未
要求ID唯一，固定上游Generator也直接保留JSON中的列表。这一限制还改变训练
反馈，不能只重新算两个分数便继续把旧库当作一致协议的正式学习器。

原等待unit中的ACE主进程于16:02:55在制品安全边界停止；原8B服务未停止。
955成员的两个actual-terminal档已逐字核验，原始分数不覆盖，全部177次8B生成/
56次教师成本保留。旧run01不进入正式三次ACE重复，不因其分数较低而充当胜出证据。
离线仅移除元数据拒收的诊断不等于新运行、重答或最终结果。

上游固定代码：
[Generator](https://github.com/ace-agent/ace/blob/82709de050e1db6e6ef2f07bcb0393560b94992a/ace/core/generator.py)。
使用其原始JSON列表语义，不导入regex、JSON修复或重答fallback。

## 唯一运行语义修订

- learner为`ace_native_online_v3`，必须声明
  `ace_bullet_provenance_policy=preserve_raw_ids_distinct_reflection_tags`。
- Generator的请求消息、JSON schema、公开上下文、模型与采样预算不变。
  原样保留`bullet_ids`和`final_answer`；重复已知ID不是法律答案错误。
- 只有反思的“有哪些不同条目被引用”采用保序集合，每个条目标签一次。
  反思输入的原始observation仍保留重复列表；原生last-tag批计数与ADD逻辑不变。
- 法律答案解码、原EC/EV评分与容差、错误答案、非法JSON及非法答案字段均不修复。
  不补写法条、不改金额、不因不理想的分数重答。

## 全规模新学习

新seed45配置为`openexempt_ace_public_assets128_20261022_run02.json`；
seed145/245使用同日同版本配置，未排队或运行不算已完成。
每次均从原生空标题开始，不导入旧库、旧教师或旧回答。保持同128 TRAIN来源、
8批×16来源、每来源独立EC/EV、单实例冻结Qwen3-8B、每次8192输出、thinking开、
最多3轮TRAIN反思及8192库容量。每批所有首答完成后才释放当前标签，无验证集。
教师与共享账本不重置，启动前重新冻结源码/配置；不新增付费服务或模型。

主Run03及盲法条库使用的四个共享直接actor/scorer文件不改。对主方法学习算法、
原始成绩和真实B1控制没有修订，不因ACE专属适配器修复要求重跑已完成的主Run。
最终评测必须使用与新ACE学习相同的v3 adapter；旧ACE不能混入一致协议重复。
其他最近邻、独立重复、必要消融及TEST前完整冻结的要求保持不变。
