# 关键发现

## 现有架构事实

- 学习专题不是独立业务表，而是 `sales_trainer_asset_revisions` 上的 `newcomer_learning_topics_v1` payload；商务礼仪目前是唯一 topic，key 为 `business_etiquette`。
- 学习专题服务已经提供草稿、发布、回滚、future-only、operation log 和非阻塞校验，适合作为客户常见问答的治理主轴。
- 商务礼仪前台当前强绑定文章章节；客户常见问答不应复用长文章阅读模型，应新增卡片化 learner surface，同时仍由同一学习专题 revision 控制是否前台展示。
- 录音演练已经抽象为 `audio_evaluation_scenarios`，PPT 讲解、公司产品 Demo、金字塔演讲均是“录音上传 + AI 评分”能力的不同载体；客户问答口播应新增为同级场景，不应建成文章或题库附属页。
- 题库、考卷、短答 AI 评分、音频评分、操作记录已有体系，应尽量绑定来源卡片而不是另起数据库模型。

## 材料治理发现

- 100 问覆盖初次拜访、竞品 PK、交付部署三大场景，但实际可训练维度应按公司价值、产品能力、部署架构、行业案例、竞品、POC/交付、高风险技术、现场表达重组。
- 多处重复/近似重复会导致新人记忆混乱，后台导入时必须展示重复提示，由管理员确认合并、保留或归档。
- 材料中存在大量高风险表达，不能直接变成标准答案；必须拆成“标准答法”“案例依据”“禁说/需确认”。

## 工具与执行发现

- 当前会话没有暴露可调用的多 agent/subagent 工具；已通过 `tool_search` 搜索未找到。后续按最多 3 个分析轨道在主 agent 内完成，并在实现记录中说明。
- 仓库有 `.codegraph/`，但没有 CodeGraph MCP 工具；已改用 shell 版 `codegraph explore`，符合 CodeGraph First。
- `docs/uiux.md`、`docs/domain-glossary.md`、`docs/ai-governance.md` 当前不存在；需要更新实际存在的 `docs/api-contract/sales-trainer.md`，必要时新增缺失文档或 ADR。

## 实现后发现

- `TrainingJourney.modules` 旧测试仍假设 `business_skills` 作为非必修 quiz/AI 模块存在；新口径要求学习专题单独投影，因此测试已改为断言源模块不再进入主路径，学习得分进入 `learning_topics` 和 `learning_topic_summaries`。
- 客户问答解析器最初会先构造空重复组再过滤，触发 Pydantic `min_length=2` 校验；已改为先过滤再构造，并补回归测试。
- 后端 mypy 本次相关文件已清理；剩余 `src/common/ai/config_manager.py:279` 为既有无关类型债务。
- Playwright Chromium 缺少 `libnspr4.so`，且当前用户无 sudo，专项浏览器审计无法在本环境完成；路由清单已补齐，待系统依赖安装后可直接运行。
- 用户验收发现学习专题总览仍只显示已存在的商务礼仪规范。根因是总览页只渲染 `config.payload.topics`，未把“可配置但尚未导入/生成草稿”的 `customer_faq` 作为 starter 展示。已改为“starter 模板 + 已配置 topic”合并视图，并补回归测试。
