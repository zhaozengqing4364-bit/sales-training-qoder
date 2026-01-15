# Requirements Supplement: Enterprise AI Intelligent Practice System

**Purpose**: 补充和澄清现有需求文档中的缺口和模糊点
**Date**: 2026-01-10
**Status**: Draft
**Based on**: comprehensive-reviewed.md 检查清单审查结果

---

## 一、高优先级补充 (影响核心功能)

### 1.1 三维评分计算公式和权重分配

**来源**: CHK008 - 三维评分（逻辑、准确度、完整度）的计算公式和权重分配是否定义？

#### 补充需求

**FR-048**: 三维评分计算公式

**评分维度定义**:
1. **逻辑分数 (Logic Score)**: 演讲内容的逻辑连贯性和结构合理性
   - 计算方法: 基于 AI 语义分析，评估论点之间的逻辑关系
   - 公式: `Logic = Base_Score × (1 - Logic_Faults × 0.1)`
   - 其中 Logic_Faults 为逻辑缺陷数量（前后矛盾、论据不足等）
   - 范围: 0-100 分

2. **准确度分数 (Accuracy Score)**: 事实陈述的准确性和专业知识正确性
   - 计算方法: 基于知识库向量检索，验证陈述内容与 PPT 内容的一致性
   - 公式: `Accuracy = (Verified_Statements / Total_Statements) × 100`
   - 其中 Verified_Statements 为与知识库匹配的陈述数量
   - 范围: 0-100 分

3. **完整度分数 (Completeness Score)**: 必讲点覆盖程度
   - 计算方法: 基于必讲点检测，计算已覆盖必讲点比例
   - 公式: `Completeness = (Covered_Points / Total_Required_Points) × 100`
   - 其中 Covered_Points 为用户提及的必讲点数量
   - 范围: 0-100 分

**综合评分公式**:
```
Overall_Score = Logic × 0.3 + Accuracy × 0.4 + Completeness × 0.3
```

**权重分配理由**:
- 准确度占 40%: 专业知识正确性最重要
- 逻辑和完整度各占 30%: 演讲结构和内容完整性同等重要

**分级标准**:
- 90-100 分: 优秀 (Excellent)
- 75-89 分: 良好 (Good)
- 60-74 分: 需改进 (Needs Improvement)
- <60 分: 不合格 (Poor)

---

### 1.2 模糊回答检测标准

**来源**: CHK012 - "模糊回答"的检测标准是否可操作化定义？

#### 补充需求

**FR-049**: 销售对练模糊回答检测标准

**检测维度**:

1. **缺乏具体数据** (Lack of Specific Data):
   - 触发条件: 回答中无数字、百分比、具体指标
   - 示例: "产品很好" → 模糊; "提升 30% 效率" → 具体
   - 检测方法: 正则匹配数字、百分比、量词

2. **过度概括** (Over-Generalization):
   - 触发条件: 使用"总是"、"从来"、"所有"等绝对化词汇
   - 示例: "所有客户都喜欢" → 模糊; "80% 的客户反馈" → 具体
   - 检测方法: 关键词匹配 + 上下文分析

3. **回避问题** (Evasion):
   - 触发条件: 回答与问题主题不相关
   - 示例: 问"价格"答"质量" → 回避
   - 检测方法: LLM 语义相似度分析

4. **模糊修饰语** (Vague Modifiers):
   - 触发条件: 使用"可能"、"大概"、"差不多"等不确定词汇
   - 示例: "大概下周" → 模糊; "下周一前" → 具体
   - 检测方法: 模糊词汇表匹配

**模糊回答判定流程**:
```python
def is_vague_response(user_input: str, question: str) -> tuple[bool, str]:
    """
    Returns: (is_vague, reason)
    """
    # 1. 检测具体数据
    if not has_specific_data(user_input):
        return True, "缺乏具体数据"

    # 2. 检测绝对化词汇
    if has_absolute_terms(user_input):
        return True, "过度概括"

    # 3. 检测回避问题
    if not is_relevant(user_input, question):
        return True, "回避问题"

    # 4. 检测模糊修饰语
    if has_vague_modifiers(user_input):
        return True, "表达不确定"

    return False, None
```

**AI 打断话术库**:
- "这个回答太笼统了。能给我 3 个具体的例子吗？"
- "你用了'可能'这个词。能给我一个确定的答案吗？"
- "我没听到具体的数据。能用数字说明一下吗？"
- "这个回答和问题不太相关。我们回到正题？"

---

### 1.3 对话上下文窗口大小

**来源**: CHK013 - 对话上下文窗口大小（对话历史轮数）是否指定？

#### 补充需求

**FR-050**: 销售对练对话上下文管理

**上下文窗口配置**:
- **默认窗口大小**: 10 轮对话（5 轮用户 + 5 轮 AI）
- **最大窗口大小**: 20 轮对话（内存限制）
- **最小窗口大小**: 5 轮对话（保持连贯性）

**对话轮定义**:
```
1 轮 = 用户输入 + AI 响应
```

**窗口滚动策略**:
- **FIFO (先进先出)**: 超过窗口大小后，丢弃最早的对话轮
- **关键信息保留**: 如果早期对话包含关键信息（如客户需求），保留摘要
- **上下文压缩**: 每 5 轮生成一次对话摘要，保留关键信息

**实现示例**:
```python
class ConversationContext:
    def __init__(self, window_size: int = 10):
        self.window_size = window_size
        self.history = []  # List[dict]

    def add_turn(self, user_input: str, ai_response: str, metadata: dict):
        """添加一轮对话"""
        turn = {
            "user": user_input,
            "ai": ai_response,
            "timestamp": datetime.now(),
            **metadata
        }
        self.history.append(turn)

        # 超过窗口大小则丢弃最早的
        if len(self.history) > self.window_size:
            self.history.pop(0)

    def get_context_for_llm(self) -> str:
        """获取格式化的上下文"""
        return "\n".join([
            f"用户: {turn['user']}\nAI: {turn['ai']}"
            for turn in self.history
        ])
```

**性能考虑**:
- 10 轮对话 ≈ 2000 tokens (中文)
- LLM 上下文窗口限制: 4K tokens (GPT-3.5) / 8K tokens (GPT-4)
- 预留空间: 50% 用于 AI 响应生成

---

## 二、中优先级补充 (影响用户体验)

### 2.1 页面跟踪触发机制

**来源**: CHK005 - 当前页面跟踪机制的触发条件是否明确？

#### 补充需求

**FR-051**: PPT 演练页面跟踪触发机制

**触发方式** (按优先级):

1. **用户主动翻页** (主要方式):
   - 触发条件: 用户点击"下一页"按钮或滑动
   - 前端事件: `page_change` 消息发送到服务器
   - 确认机制: 服务器返回当前页面的必讲点列表

2. **语音指令** (辅助方式):
   - 触发条件: 用户说"下一页"、"翻页"等指令
   - ASR 识别: 检测关键词 "下一页"、"翻到第 X 页"
   - 确认机制: AI 确认"好的，我们翻到第 X 页"

3. **自动检测** (备选方式):
   - 触发条件: 用户演讲内容与下一页内容高度相关
   - 检测方法: 向量检索用户输入与各页面内容的相似度
   - 确认机制: AI 提示"您是要讲到第 X 页了吗？"

**状态同步**:
- 服务器维护 `current_page` 状态
- 前端显示当前页码和总页数
- 页面变更时更新必讲点检查列表

---

### 2.2 必讲点完整度判断

**来源**: CHK006 - 必讲点"漏掉"的判断标准是否可量化定义？

#### 补充需求

**FR-052**: 必讲点覆盖度判断标准

**判断维度**:

1. **完全覆盖** (Fully Covered):
   - 标准: 用户明确提及必讲点的核心关键词
   - 示例: 必讲点"专有技术" → 用户说"我们的专有技术..."
   - 权重: 100%

2. **部分覆盖** (Partially Covered):
   - 标准: 用户提及相关内容但未明确关键词
   - 示例: 必讲点"专有技术" → 用户说"我们的独特技术..."
   - 权重: 50%

3. **未覆盖** (Not Covered):
   - 标准: 用户未提及相关内容
   - 权重: 0%

**检测方法**:
```python
def check_point_coverage(user_speech: str, required_point: str) -> float:
    """
    Returns: coverage_ratio (0.0 to 1.0)
    """
    # 1. 关键词匹配 (完全覆盖)
    keywords = extract_keywords(required_point)
    if any(keyword in user_speech for keyword in keywords):
        return 1.0

    # 2. 语义相似度 (部分覆盖)
    similarity = calculate_semantic_similarity(user_speech, required_point)
    if similarity > 0.7:  # 阈值可调
        return 0.5

    # 3. 未覆盖
    return 0.0
```

**页面完成判定**:
- 用户明确表示"讲完了"、"下一页"
- 用户停顿超过 10 秒
- 用户开始讲下一页的内容

---

### 2.3 重连会话恢复策略

**来源**: CHK035 - 重连成功后的会话恢复策略是否定义？

#### 补充需求

**FR-053**: WebSocket 断线重连会话恢复机制

**会话状态保存**:
- 服务器维护会话状态，有效期 5 分钟
- 状态包括: current_page, interruption_count, scores, history

**恢复策略**:

1. **无损恢复** (< 30 秒断开):
   - 条件: 断开时长 < 30 秒
   - 策略: 恢复到断开前的精确状态
   - 用户体验: 无感知，继续对话

2. **部分恢复** (30 秒 - 5 分钟):
   - 条件: 断开时长 30 秒 - 5 分钟
   - 策略: 恢复页面和进度，丢失断开期间的音频
   - 用户体验: AI 提示"我们刚才讲到第 X 页"

3. **超时重置** (> 5 分钟):
   - 条件: 断开时长 > 5 分钟
   - 策略: 会话结束，保存当前进度
   - 用户体验: 提示"会话已结束，进度已保存"

**恢复流程**:
```
Client                              Server
  |                                    |
  |----- RECONNECT -------------------->|
  |                                    | 1. 查询会话状态
  |<---- SESSION_STATE ----------------|
  |     {status: "resumable",          |
  |      last_page: 5,                 |
  |      buffer: [...]}               |
  |                                    | 2. 客户端恢复状态
  |----- CLIENT_READY ---------------->|
  |                                    | 3. 继续对话
  |<---- AI_GREETING ------------------|
  |     "我们继续，刚才讲到第5页..."    |
```

---

### 2.4 成本监控机制

**来源**: CHK031 - 成本追踪的监控频率和告警阈值是否定义？

#### 补充需求

**FR-054**: 单次演练成本实时追踪与告警

**成本计算模型**:

| 组件 | 单价 | 计量单位 | 单次成本 |
|------|------|----------|----------|
| LLM API | ¥0.05/1K tokens | tokens | ~¥0.25/会话 |
| ASR (qwen3) | ¥0 | - | ¥0 |
| TTS (Edge-TTS) | ¥0 | - | ¥0 |
| 存储 | ¥0.01/GB/月 | GB | ¥0.001/会话 |
| **总计** | | | **~¥0.251/会话** |

**监控频率**:
- **实时追踪**: 每个 LLM 调用后累加成本
- **会话级汇总**: 会话结束时生成成本报告
- **日级统计**: 每日汇总总成本

**告警阈值**:
- **80% 阈值** (¥0.80): 记录警告日志，通知管理员
- **90% 阈值** (¥0.90): 降低 AI 响应复杂度，减少 token 使用
- **100% 阈值** (¥1.00): 强制结束会话，避免超支

**降级策略** (接近预算时):
- 简化 LLM Prompt (减少系统提示词)
- 减少 AI 响应长度
- 使用更便宜的 LLM 模型 (如 GPT-3.5-turbo)

**实现示例**:
```python
class CostTracker:
    def __init__(self, budget_limit: float = 1.0):
        self.budget_limit = budget_limit
        self.session_cost = 0.0
        self.warn_thresholds = [0.8, 0.9]

    def record_llm_call(self, tokens: int):
        cost = tokens * 0.00005  # ¥0.05/1K tokens
        self.session_cost += cost

        # 检查阈值
        ratio = self.session_cost / self.budget_limit
        if ratio >= 1.0:
            raise BudgetExceeded("会话成本已达上限")
        elif ratio >= 0.9:
            logger.warning(f"成本达到 90%: ¥{self.session_cost:.2f}")
        elif ratio >= 0.8:
            logger.info(f"成本达到 80%: ¥{self.session_cost:.2f}")
```

---

### 2.5 错误率指标定义

**来源**: CHK072 - "错误率"指标的计算公式和告警阈值是否定义？

#### 补充需求

**FR-055**: 系统错误率监控与告警

**错误率计算公式**:
```
Error_Rate = (Failed_Requests / Total_Requests) × 100%
```

**失败请求定义**:
- HTTP 状态码 >= 500
- WebSocket 连接失败
- ASR/TTS 超时或失败
- LLM API 调用失败

**统计维度**:
- **时间窗口**: 滚动 5 分钟窗口
- **按场景分类**: PPT 演练 / 销售对练
- **按错误类型**: ASR / TTS / LLM / 网络 / 系统

**告警阈值**:
- **警告级**: 错误率 > 1% 持续 5 分钟
- **严重级**: 错误率 > 5% 持续 2 分钟
- **紧急级**: 错误率 > 10% 持续 1 分钟

**告警动作**:
- 警告级: 发送通知到管理员
- 严重级: 发送短信 + 自动降级服务
- 紧急级: 短信 + 电话 + 考虑暂停服务

---

### 2.6 成本追踪维度

**来源**: CHK074 - API 使用量的成本追踪维度是否定义？

#### 补充需求

**FR-056**: 多维度成本追踪与分析

**追踪维度**:

1. **按用户** (Per-User):
   - 目的: 识别高成本用户
   - 指标: 每用户平均成本/会话
   - 告警: 单用户月度成本 > ¥50

2. **按场景** (Per-Scenario):
   - 目的: 对比不同场景成本
   - 指标: PPT 演练 vs 销售对练平均成本
   - 用途: 优化高成本场景

3. **按时间** (Per-Time):
   - 目的: 识别成本趋势
   - 指标: 每小时/每日/每月总成本
   - 用途: 预算规划

4. **按组件** (Per-Component):
   - 目的: 识别成本瓶颈
   - 指标: LLM / ASR / TTS / 存储成本占比
   - 用途: 优化高成本组件

**数据存储**:
```sql
CREATE TABLE cost_tracking (
    tracking_id UUID PRIMARY KEY,
    session_id UUID REFERENCES practice_sessions,
    user_id UUID REFERENCES users,
    scenario_type VARCHAR(20),
    component VARCHAR(50),  -- 'llm', 'asr', 'tts', 'storage'
    quantity FLOAT,         -- tokens, seconds, GB
    unit_cost FLOAT,        -- 单价
    total_cost FLOAT,
    tracked_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_cost_user ON cost_tracking(user_id, tracked_at);
CREATE INDEX idx_cost_scenario ON cost_tracking(scenario_type, tracked_at);
```

**报表查询示例**:
```sql
-- 每用户月度成本
SELECT
    user_id,
    SUM(total_cost) as monthly_cost,
    COUNT(DISTINCT session_id) as session_count
FROM cost_tracking
WHERE tracked_at >= date_trunc('month', current_date)
GROUP BY user_id
HAVING SUM(total_cost) > 50;
```

---

### 2.7 依赖注入实现方式

**来源**: CHK057 - 依赖注入的具体实现方式是否指定？

#### 补充需求

**FR-057**: 使用 FastAPI Depends 进行依赖注入

**实现标准**:

**后端依赖注入**:
```python
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

# 1. 数据库会话依赖
async def get_db() -> AsyncSession:
    async with async_session_maker() as session:
        yield session

# 2. 服务层依赖
def get_asr_service() -> ASRService:
    return ASRService()

def get_tts_service() -> TTSService:
    return TTSService()

# 3. 在路由中使用
@app.post("/practice/sessions")
async def create_session(
    db: AsyncSession = Depends(get_db),
    asr: ASRService = Depends(get_asr_service),
    current_user: User = Depends(get_current_user)
):
    ...
```

**模块边界强制**:
- `presentation_coach/` 模块只能注入 `common/` 服务
- `sales_bot/` 模块只能注入 `common/` 服务
- 禁止跨模块直接导入，编译时检查

---

### 2.8 页面加载 SLA 范围

**来源**: CHK023 - 初始页面加载 <2 秒是否包含 PPT 图片加载时间？

#### 补充需求

**FR-058**: 页面加载性能 SLA 定义

**SLA 分解**:

**初始页面加载 < 2 秒**:
- **包含**: HTML/CSS/JavaScript 加载、首屏渲染、WebSocket 连接建立
- **不包含**: PPT 图片懒加载、知识库索引预加载

**PPT 图片加载** (异步):
- **触发**: 用户翻到对应页面时
- **SLA**: 首图加载 < 500ms
- **降级**: 显示占位符，图片加载完成后淡入

**知识库索引** (后台):
- **触发**: PPT 上传完成后
- **SLA**: 20 页 PPT 索引 < 3 分钟
- **不阻塞**: 用户可以在索引进行时开始演练

**性能测量**:
```javascript
// 初始页面加载
performance.mark('page-load-start');
// ... 加载资源 ...
performance.mark('page-load-end');
performance.measure('page-load', 'page-load-start', 'page-load-end');

// PPT 图片加载
performance.mark('image-load-start');
// ... 加载图片 ...
performance.mark('image-load-end');
performance.measure('image-load', 'image-load-start', 'image-load-end');
```

---

### 2.9 安全扫描失败处理

**来源**: CHK065 - 安全扫描的失败处理策略是否定义？

#### 补充需求

**FR-059**: 依赖安全扫描失败处理流程

**失败分级**:

1. **高危漏洞** (Critical/High):
   - 处理: 阻塞部署，必须修复
   - 例外: 安全团队签署豁免书
   - 流程: 创建 JIRA 工单 → 安全审查 → 修复 → 复扫

2. **中危漏洞** (Medium):
   - 处理: 警告但不阻塞
   - 要求: 7 天内修复
   - 流程: 发送通知 → 开发修复 → 复扫

3. **低危漏洞** (Low):
   - 处理: 记录日志
   - 要求: 下个版本修复
   - 流程: 积累到技术债务

**扫描工具配置**:
```yaml
# .github/workflows/security-scan.yml
security-scan:
  runs-on: ubuntu-latest
  steps:
    - name: Run safety check
      run: safety check --json

    - name: Check for high severity
      run: |
        if [ $(safety check --json | jq '.vulnerabilities | map(select(.severity >= 0.7)) | length') -gt 0 ]; then
          echo "High severity vulnerabilities found!"
          exit 1
        fi
```

---

### 2.10 用户数据删除方式

**来源**: CHK051 - 用户删除演练记录后的数据清除策略是否定义？

#### 补充需求

**FR-060**: 用户数据删除与保留策略

**删除类型**:

1. **软删除** (用户操作):
   - 触发: 用户点击"删除"按钮
   - 操作: 设置 `deleted_at` 时间戳，数据仍保留
   - 前端: 用户看不到已删除记录
   - 后台: 管理员可在 30 天内恢复

2. **硬删除** (定时任务):
   - 触发: `deleted_at` 超过 30 天
   - 操作: 物理删除数据库记录和音频文件
   - 例外: 转录文本永久保留（用于分析）

3. **管理员删除** (管理操作):
   - 触发: 管理员批量清理
   - 操作: 硬删除，不可恢复
   - 要求: 记录操作日志

**数据清理流程**:
```python
async def soft_delete_session(session_id: UUID):
    """用户软删除"""
    await db.execute(
        "UPDATE practice_sessions SET deleted_at = NOW() WHERE session_id = $1",
        session_id
    )

async def hard_delete_old_sessions():
    """定时任务：硬删除 30 天前软删除的记录"""
    await db.execute("""
        DELETE FROM practice_sessions
        WHERE deleted_at < NOW() - INTERVAL '30 days'
    """)
    # 同步删除音频文件
    cleanup_audio_files(session_ids)
```

---

## 三、低优先级补充 (优化建议)

### 3.1 跳过页面策略

**来源**: CHK108 - 用户主动跳过 PPT 页面的必讲点评估策略是否定义？

#### 补充需求

**FR-061**: PPT 页面跳过机制

**跳过方式**:
1. 用户点击"跳过"按钮
2. 用户语音指令"跳过这一页"

**处理策略**:
- 必讲点评估: 跳过的页面不计入完整度评分
- 页面进度: 标记为"已跳过"状态
- AI 反馈: "好的，我们跳到下一页"

**数据记录**:
```python
class PageVisit:
    status: Enum  # 'visited', 'skipped', 'pending'
    skipped_at: Optional[Timestamp]
    skip_reason: Optional[str]  # 'user_request', 'timeout'
```

---

### 3.2 成本与质量优先级

**来源**: CHK119 - 成本控制与高质量需求之间的优先级定义？

#### 补充需求

**FR-062**: 成本与质量的优先级平衡

**优先级矩阵**:

| 场景 | 成本优先级 | 质量优先级 | 决策 |
|------|-----------|-----------|------|
| 单次会话 | 高 | 高 | 使用免费/低成本方案，但不降低核心体验 |
| 50 并发 | 高 | 中 | 保证基本功能，可降低非关键体验 |
| 系统稳定 | 最高 | 高 | 稳定第一，必要时降低质量保稳定 |

**降级决策树**:
```
IF 预算充足 (< ¥0.8/会话):
    使用最佳质量方案
ELSE IF 预算紧张 (¥0.8 - ¥1.0):
    使用标准方案
ELSE (预算超限 > ¥1.0):
    降级到最低成本方案
```

**质量保证底线**:
- ASR 延迟: 不超过 300ms (即使降级)
- TTS 质量: 不低于浏览器原生 TTS
- AI 智能: 不低于 GPT-3.5 水平

---

### 3.3 企业防火墙考虑

**来源**: CHK126 - "WebSocket 自动重连"的企业网络环境假设是否考虑？

#### 补充需求

**FR-063**: 企业网络环境适配

**企业网络特性**:
1. **防火墙限制**:
   - WebSocket 端口可能被阻止
   - 解决方案: 支持 WSS (WebSocket over TLS) + 443 端口

2. **代理服务器**:
   - 可能需要 HTTP 代理
   - 解决方案: 支持代理自动发现 (WPAD)

3. **网络隔离**:
   - 外网 API 可能被阻止
   - 解决方案: 支持内网部署

**配置选项**:
```python
# .env
WEBSOCKET_PORT=443  # 使用标准端口
WEBSOCKET_SSL=True  # 启用 WSS
HTTP_PROXY=http://proxy.corp.com:8080  # 代理配置
```

**检测与适配**:
```python
async def detect_network_environment():
    """检测企业网络环境"""
    try:
        # 尝试直连
        await test_direct_connection()
        return "direct"
    except (ConnectionRefused, Timeout):
        try:
            # 尝试代理
            await test_proxy_connection()
            return "proxy"
        except:
            # 使用降级方案
            return "degraded"
```

---

## 四、其他补充需求

### 4.1 评分报告生成细节

**来源**: CHK009 - 评分报告生成 10 秒 SLA 的边缘情况处理

#### 补充需求

**SC-009A**: 评分报告生成性能要求

**正常情况** (< 100 个打断事件):
- SLA: 10 秒内完成
- 包含: 三维评分、改进建议、音频 URL

**大数据量** (100-500 个打断事件):
- SLA: 30 秒内完成
- 策略: 异步生成，前端显示"评分中..."

**超大数据量** (> 500 个打断事件):
- SLA: 60 秒内完成
- 策略: 后台生成，完成后推送通知

**生成失败降级**:
- 如果评分生成超时: 显示"评分中，请稍后查看"
- 保留原始音频和转录，允许手动重试

---

### 4.2 向量数据库恢复策略

**来源**: CHK114 - 向量数据库恢复后的索引重建策略是否明确？

#### 补充需求

**FR-064**: ChromaDB 灾难恢复与重建

**备份策略**:
- 频率: 每日增量备份
- 保留: 30 天备份历史
- 位置: 对象存储 (S3/MinIO)

**恢复流程**:
1. 检测 ChromaDB 损坏
2. 从备份恢复向量数据
3. 从 PostgreSQL 恢复元数据
4. 重建索引（可能需要数小时）

**降级策略**:
- 恢复期间: 关键词搜索降级
- 用户体验: "搜索功能暂时简化"

---

### 4.3 测试数据准备策略

**来源**: CHK097 - E2E 测试的测试数据准备策略是否指定？

#### 补充需求

**FR-065**: 测试数据管理

**PPT 测试样本**:
- 5 页 PPT (基础测试)
- 20 页 PPT (中等测试)
- 50 页 PPT (性能测试)
- 包含: 文字、图表、混合内容

**用户账号**:
- 测试用户 1: 管理员权限
- 测试用户 2-10: 普通员工
- 测试用户 11-50: 性能测试

**数据管理**:
- 位置: `tests/fixtures/`
- 版本控制: Git LFS (大文件)
- 更新策略: 每季度更新

---

### 4.4 分布式追踪开销控制

**来源**: CHK076 - 分布式追踪的性能开销控制策略是否指定？

#### 补充需求

**FR-066**: 分布式追踪性能控制

**采样策略**:
- 正常模式: 10% 采样
- 高负载模式: 1% 采样
- 调试模式: 100% 采样

**异步上报**:
- 追踪数据批量上报 (每 10 秒或 100 条)
- 不阻塞主流程
- 上传失败时丢弃数据

**性能预算**:
- 追踪开销 < 5% 总响应时间
- 每个追踪点 < 1ms

---

## 五、需求文档更新映射

以下补充需求应添加到 spec.md 的对应章节：

| 补充需求 ID | 添加到 spec.md 章节 | 需求类型 |
|------------|---------------------|----------|
| FR-048 | §Success Criteria → Measurable Outcomes | 非功能需求 |
| FR-049 | §Requirements → Functional Requirements → Sales Sparring Bot | 功能需求 |
| FR-050 | §Requirements → Functional Requirements → Sales Sparring Bot | 功能需求 |
| FR-051 | §Requirements → Functional Requirements → PPT Presentation Coaching | 功能需求 |
| FR-052 | §Requirements → Functional Requirements → PPT Presentation Coaching | 功能需求 |
| FR-053 | §Requirements → Error Handling & Resilience | 功能需求 |
| FR-054 | §Requirements → Performance & Scalability | 非功能需求 |
| FR-055 | §Success Criteria → Quality & Reliability | 非功能需求 |
| FR-056 | §Requirements → Performance & Scalability | 非功能需求 |
| FR-057 | §Requirements → Architecture Constraints | 架构需求 |
| FR-058 | §Success Criteria → Real-time Performance | 非功能需求 |
| FR-059 | §Requirements → External Dependency Management | 非功能需求 |
| FR-060 | §Requirements → Data & Privacy | 非功能需求 |
| FR-061 | §Requirements → Functional Requirements → PPT Presentation Coaching | 功能需求 |
| FR-062 | §Constitution → Principle V | 原则 |
| FR-063 | §Requirements → Architecture Constraints | 架构需求 |
| FR-064 | §Requirements → Knowledge Base & Content Management | 功能需求 |
| FR-065 | §Success Criteria → Measurable Outcomes | 非功能需求 |
| FR-066 | §Requirements → Observability | 非功能需求 |

---

## 六、后续行动

### 立即执行 (本次迭代)
1. ✅ 将 FR-048 到 FR-066 添加到 spec.md
2. ✅ 更新 Key Entities 部分（如需）
3. ✅ 重新运行检查清单验证
4. ✅ 继续执行 `/speckit.implement`

### 持续优化 (下个迭代)
1. 收集实施过程中的新问题
2. 定期审查需求完整性
3. 根据用户反馈调整需求

---

**创建时间**: 2026-01-10
**下一步**: 将本文件内容整合到 spec.md
