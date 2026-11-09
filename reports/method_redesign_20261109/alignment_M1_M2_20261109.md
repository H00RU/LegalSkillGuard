# 已完成／可复用／缺失


## 最新用户设计衔接：M1/M2，不重开Goal

2026-11-09 已从GitHub main只读取得 `reports/semantic_disambiguation_design_20261109` 的16份文档/原型，固定main提交5368150eceece401ee475370cc6b8170ca6584bf；研究分支仍c6277a7。用户的最终主报告优先于其中被否决的中间M2/分组纠错方案。原稿已存 `reports/method_redesign_20261109/external_design_snapshot/`，retrieval_manifest记录哈希。没有修改main。

当前两项方法明确为：M1混淆对驱动的消歧技能编译；M2结构化误读通道学习。既有模块/上限修复/查新/旧A/B反证直接复用，不重跑。source-role v1后来新增1E/2T（§151学生、§151教师、§63教师），均已结算；没有继续该重型接口剩余批次。§151教师仅将condition中的true按Boolean字面量无歧义渲染为True即可通过原检查，保存processed衍生文件，原结果不改。学生域/义务为NL且有取整/角色错误，不能靠适配补语义。

新的缺失工作是共同轻量source-span前端、真实混淆对、跨来源技能归纳/执行、冻结误读通道的盲预测及同信息强对照。先预注册原TRAIN小池分组和单因素变体；不把已诊断DEV当新确认集。首次小试即含直接role抽取、正确政策缓存、同错误—修复材料检索、同特征错误模型；所有原始问题/响应按各臂实际可见范围计费，共享回放不伪造缓存外回答。M2没有可识别锚点时保留unresolved。

实时累计1342E/47T，pending0。Goal active，OFF，不启动完整训练/矩阵/TEST/论文。
