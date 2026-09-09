# LegalSkillEvolve 主实验执行说明（128案顺序积累）

现行协议为8块×16案、每案K=4、统一合作型`P_WD`。没有固定内部验收集，没有逐候选额外对话，也不把K=4拆成候选控制/治疗单元。

| 环节 | 数据 | 作用 |
|---|---|---|
| 顺序训练 | 自建128案，8块×16案，统一合作型P_WD | K=4真实探索、组内优势、候选来源和技能积累 |
| Prequential观察 | 每块预声明8案的正常当前库轨迹与匹配空库影子 | 观察块首整体技能库的事实获取效率与安全 |
| 库级维护 | 第2、4、6、8块后的累计工作库 | 去重、冲突、冗余、暴露/使用与提示容量治理 |
| 主外测 | 官方中文30案×4人格 | 最终冻结库与空库的同案配对比较 |

## 每块顺序

1. 冻结块首工作技能库\(L_{b-1}\)、实现、模型revision、提示、数据与随机配置。第一块从空库开始；同一块运行期间不得边生成边改变在线技能包。
2. 一次生成完整16×K4轨迹和memo。每案四条轨迹看到相同opening、合作型人格和适用的`general + domain`文档，各自独立采样会话前计划与逐轮动作。程序不指定目标、不触发技能、不替换问题，也不要求问满固定轮数。
3. 评分前检查轨迹协议与可归因性。泄漏、非法状态、不可归因fallback和不完整组按预声明规则失败关闭或整组隔离；事实产率低、重复提问或健康的早停属于评分结果，不得用硬门把弱策略从学习链抹掉。
4. 离线评审和确定性指标完成后，对本批同库K=4计算组内优势，选择在F、G或信息不损失提问效率上优于低分轨迹的完整对照，并形成通用或领域来源簇。
5. 从所有合格簇中最多选择3个未尝试fingerprint。通用与领域簇都存在时至少各选1个；余下席位优先新的行为机制和法域。向Luna逐簇提交，允许每簇返回一个文档候选或`NOOP`。
6. 每个候选依次通过静态合法性、来源因果重放、法律与运行安全、语义去重和工作库联合提示容量硬门。失败项保留明确审计理由；全部通过者在本块事务末尾直接写入\(L_b\)，下一块自然使用。
7. 计算绑定\(L_{b-1}\)的块级prequential观察：正常K=4已代表当前库，只对预声明8案增加匹配空库影子。该影子不进入本批TF-GRPO、教师证据或技能准入。
8. 第2、4、6、8块完成后运行库级维护并保存不可变报告；其他块只保存新增库版本与检查点。第八块仍可生成技能，维护完成后冻结最终库，再进入官方外测。

技能从来源块之后的第一块起作为固定会话文档真实暴露。后一块的自然使用和prequential曲线提供累计库级证据，但不会把某个技能单独分配为治疗，也不会产生`provisional`、`ACCEPT/DEFER/REJECT`。若需要单技能因果分析，只能作为独立消融，不能悄悄恢复成主训练门槛。

## 启动与恢复

```bash
bash scripts/start_main_model_services.sh
.venv/bin/python scripts/run_main_experiment.py --run-id <run-id> preflight
# 仅当preflight报告对应的当前资格组合失效时，才重新运行：
# .venv/bin/python scripts/qualify_client_simulator.py --run-id <run-id>
# .venv/bin/python scripts/qualify_local_judge.py
.venv/bin/python scripts/run_main_experiment.py --run-id <run-id> train \
  --fresh --confirm I_CONFIRM_MAIN_TRAINING
```

客户模拟器可使用`configs/qualification/client_simulator_evidence.yaml`中显式批准的组件级资格证据，
前提是报告、binding、提示、schema、实现、冻结revision、资格样例与端点身份全部通过当前哈希复核；
任一项变化就必须为当前run重新资格。本地裁判同样绑定当前提示、schema、评分实现、资格样例和冻结
revision。这样可安全复用未变化组件，而不是每换run ID就重复跑资格；旧哈希、历史成功结论或手工
复制文件仍一律不能放行。`train`入口会自动运行教师和裁判结构化探针。

安全中止后只能在实现、配置、模型、数据、提示、批次计划和空初始库哈希全部仍一致时恢复：

```bash
.venv/bin/python scripts/run_main_experiment.py --run-id <run-id> train \
  --resume --confirm I_CONFIRM_MAIN_TRAINING
```

块级事务会复用并重新核验已经原子落盘的轨迹、评分、教师响应、准入、曲线和维护报告；时间戳不能让
确定性内容相同的维护报告在恢复时冲突。若教师manifest尚未写完，preflight只对“proposal文件、
证据fingerprint、批次身份、教师模型、精确响应缓存和响应哈希全部一致”的提案抵扣剩余Luna最坏
调用数，残缺或复制缓存不抵扣。教师生成同ID不同文档时只拒收冲突提案且不覆盖旧文件，不把可预期
命名碰撞升级成整run失败。

任何协议切换必须使用新run ID。旧42+18、逐候选前瞻、`provisional`生命周期、调查计划全集、64条首轮、20条完整对话及其语义审计入口都属于退役设计；历史输出与历史run不能执行、恢复或作为效果证据。
