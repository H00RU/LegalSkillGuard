# 固定实验与方法验收核对

Goal active、未完成。下列核对复用原方案，不新增验收门槛，不调用模型。

| 原要求 | 当前证据状态 |
|---|---|
| fixed_model_thinking_OFF_no_parameter_training | verified_configuration |
| formal_bound_code_data_profile | verified |
| 128_TRAIN_8_batches_48_updates_42_DEV_points | incomplete |
| B8_fixed_seven_system_five_dataset_TEST | incomplete |
| registered_foreign_skill_mask_contrast | incomplete |
| Lift_independent_cross_parent_mechanism | incomplete |
| CoRev_independent_cross_parent_mechanism | incomplete |
| actual_meaningful_gain_over_strong_controls | incomplete |
| no_teacher_during_frozen_evaluation | verified_so_far |

## 实际学习状态

| 臂 | 初答母来源 | 已结算更新 | 技能 | 依赖端口 | 修订模式 |
|---|---:|---:|---:|---:|---:|
| NoSkill | 128 | 0 | 0 | 0 | 0 |
| FreeEvolution | 128 | 7 | 4 | 0 | 0 |
| LiftOnly | 128 | 7 | 2 | 0 | 0 |
| CoRevOnly | 128 | 7 | 2 | 0 | 0 |
| Full | 128 | 7 | 4 | 0 | 0 |
| Lift+GenericJoint | 128 | 7 | 3 | 0 | 0 |
| AllPorts+CoRev | 128 | 7 | 2 | 0 | 0 |

## 真实教师输入核对

逐项核对43个已结算教师请求的原始输入、账本请求哈希及批初库；其中21次包含非空固定前提候选块，0次包含技能依赖端口，0次包含已学修订模式。候选块只表示有位置可提议，不代表该案一定需要或能够受益于Lift。分臂计数见JSON。

通过类型与执行、普通程序获取/修补的收益、专门Lift/CoRev的独立作用分开报告。回退不算核心机制成功。若完整固定实验仍无机制事件，不把跑完队列或DEV涨分替代双贡献验收，也不追加来源或修改TEST追分。

完整数值、四项注册差值、账本状态和证据哈希见[JSON核对](fixed_study_completion_audit.json)；曲线及费用见[现有执行报告](README.md)。
