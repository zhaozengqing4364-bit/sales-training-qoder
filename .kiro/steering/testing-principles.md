---
inclusion: fileMatch
fileMatchPattern: "**/tests/**/*.py"
---

# 测试原则 (元能力版)

> 只保留核心原则，代码模板见 `.kiro/templates/backend/test_example.py`

---

## 1. 测试金字塔

```
              ┌─────────┐
              │  E2E    │  ← 少量，关键用户流程
             ─┴─────────┴─
            ┌─────────────┐
            │   集成测试   │  ← 中等，模块协作
           ─┴─────────────┴─
          ┌─────────────────┐
          │    单元测试      │  ← 大量，单个函数/类
         ─┴─────────────────┴─
```

**覆盖率目标:** 单元测试 80%+，核心业务流程 100%

---

## 2. 命名规范

### 文件命名
```
test_asr.py              # 测试 ASR 模块
test_presentation_flow.py  # 测试演示文稿流程
```

### 方法命名: should_行为_when_条件
```python
def test_should_return_success_when_valid_input(self):
def test_should_interrupt_when_forbidden_word_detected(self):
def test_should_fallback_when_llm_timeout(self):
```

---

## 3. AAA 模式

```python
def test_should_transcribe_audio_successfully(self):
    # Arrange - 准备
    service = ASRService(mock_provider)
    audio_data = b"fake_audio_data"
    
    # Act - 执行
    result = await service.transcribe(audio_data)
    
    # Assert - 断言
    assert result.is_success
    assert result.value == "expected text"
```

---

## 4. 断言规范

### 明确断言
```python
# ✅ 正确
assert result.is_success is True
assert len(items) == 3

# ❌ 错误
assert result  # 不清楚期望什么
```

### 带消息的断言
```python
# ✅ 正确
assert latency_ms < 100, f"延迟 {latency_ms:.2f}ms 超过 100ms 目标"

# ❌ 错误
assert latency_ms < 100  # 失败时不知道实际值
```

---

## 5. 性能目标

| 指标 | 目标 |
|------|------|
| ASR 流式识别 | <200ms |
| 打断检测 | <100ms |
| LLM 响应 | <300ms |
| TTS 首包 | <500ms |

---

## 6. 必须覆盖的场景

```
正常流程:
├── 创建会话 → 发送消息 → 收到响应 → 结束会话
└── 各能力模块正常执行

边界条件:
├── 空输入
├── 超长输入
├── 特殊字符
└── 并发请求

错误处理:
├── LLM 超时
├── ASR 失败
├── 数据库错误
└── WebSocket 断开

降级场景:
├── 返回 fallback 响应
└── 切换备用服务
```

---

## 7. 运行命令

```bash
# 运行所有测试
cd backend && python -m pytest

# 运行单元测试
python -m pytest tests/unit/ -v

# 带覆盖率
python -m pytest --cov=src --cov-report=html

# 运行特定测试
python -m pytest tests/unit/test_result.py::TestResultType::test_result_ok -v
```
