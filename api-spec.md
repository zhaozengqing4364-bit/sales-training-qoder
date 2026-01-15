# AI Practice Platform - 前端数据与接口对接规格说明书 (API & Data Spec)

## 1. 概述
本文档详细列出了前端各页面所需的所有数据节点、接口调用时机及展示逻辑。

**核心原则**：
*   所有复杂计算（如比率、趋势、排名）均由**后端**完成，前端只负责展示。
*   实时交互（语音、评分）走 WebSocket。
*   页面加载数据走 RESTful API。

---

## 📂 一、全局与公共模块 (Global)

### 1.1 用户基础信息 (User Profile)
*   **调用时机**：应用初始化 (`Layout` 加载时)。
*   **接口**：`GET /api/v1/users/me`
*   **前端展示位置**：
    *   侧边栏底部 (头像、姓名)。
    *   首页欢迎语 ("早安, {name}")。
*   **响应数据结构 (Response)**：
    ```json
    {
      "id": "u_12345",
      "display_name": "Alexander",
      "avatar_url": "https://example.com/avatar.jpg",
      "role": "Sales Manager",
      "department": "销售部",
      "settings": {
        "theme": "light",
        "notification_enabled": true
      }
    }
    ```

### 1.2 退出登录 (Logout)
*   **交互**：点击侧边栏用户弹窗 -> "Log Out" 按钮。
*   **接口**：`POST /api/v1/auth/logout`
*   **前端逻辑**：
    1.  调用接口。
    2.  清除 LocalStorage/Cookies 中的 Token。
    3.  强制重定向至 `/login`。

---

## 📂 二、首页仪表盘 (Dashboard) - `/`

### 2.1 仪表盘统计数据 (Dashboard Stats)
*   **调用时机**：首页组件挂载时 (`useEffect`)。
*   **接口**：`GET /api/v1/dashboard/stats`
*   **前端展示位置**：
    *   右上角 "本周练习" 卡片。
    *   中间 "上次得分" 卡片。
*   **响应数据结构**：
    ```json
    {
      "weekly_activity": {
        "total_duration_minutes": 210, // 3.5 小时 = 210 分钟 (前端需格式化为 3.5h)
        "session_count": 8,
        "trend_percentage": 12,        // +12% (后端逻辑：(本周-上周)/上周 * 100)
        "trend_direction": "up"        // "up" | "down" | "flat" (用于显示绿色箭头或红色箭头)
      },
      "last_session": {
        "score": 85,
        "percentile": 78,              // "击败了 78% 的用户"
        "trend": "stable"
      }
    }
    ```

### 2.2 智能推荐 (Recommendation)
*   **调用时机**：首页加载时。
*   **接口**：`GET /api/v1/recommendations/latest`
*   **前端展示位置**：首页左侧大卡片 "系统推荐"。
*   **响应数据结构**：
    ```json
    {
      "title": "加强异议处理能力",
      "reason": "基于您最近的销售对练数据，我们在“价格谈判”环节发现了提升空间。",
      "action_label": "去训练大厅",
      "target_path": "/training/sales" // 点击按钮跳转的路径
    }
    ```

### 2.3 最近练习记录列表 (Recent Activity)
*   **调用时机**：首页加载时。
*   **接口**：`GET /api/v1/sessions?limit=2&sort=desc`
*   **响应数据结构**：(见 7.1 历史记录列表)

---

## 📂 三、训练大厅 (Training Hub) - `/training`

### 3.1 获取训练大类 (Training Categories)
*   **调用时机**：页面加载时。
*   **接口**：`GET /api/v1/training-categories`
*   **前端展示位置**：训练大厅的三个大卡片 (销售、演讲、客服)。
*   **响应数据结构**：
    ```json
    [
      {
        "id": "sales",
        "title": "销售能力训练",
        "description": "通过与不同性格的 AI 客户进行实战演练...",
        "icon_key": "mic",           // 前端根据 key 映射图标组件
        "color_theme": "blue",
        "agent_count": 4,            // "4 个场景"
        "tags": ["谈判技巧", "异议处理"],
        "status": "active"           // "active" | "coming_soon" (决定卡片是否可点)
      },
      // ... 其他分类
    ]
    ```

---

## 📂 四、专项训练列表 (Category Detail) - `/training/sales`

### 4.1 获取具体 Agent 列表 (Agents List)
*   **调用时机**：页面加载时。
*   **接口**：`GET /api/v1/agents?category_id=sales`
*   **前端展示位置**：Agent 卡片网格 (怀疑型、价格型等)。
*   **响应数据结构**：
    ```json
    [
      {
        "id": "sales-skeptical",
        "title": "怀疑型客户 - 王总",
        "role": "某制造企业采购总监",
        "description": "性格谨慎多疑，对销售话术免疫...",
        "difficulty": "Hard",        // 决定 Badge 颜色
        "skills": ["证据提供", "逻辑构建"],
        "avatar_url": "...",
        "is_new": false
      },
      // ... 其他 Agent
    ]
    ```

### 4.2 创建/开始练习 (Start Session) - 🟢 核心交互
*   **交互**：点击具体的 Agent 卡片。
*   **接口**：`POST /api/v1/sessions`
*   **请求参数 (Payload)**：
    ```json
    {
      "agent_id": "sales-skeptical",
      "mode": "voice" // 默认为语音模式
    }
    ```
*   **响应数据**：
    ```json
    {
      "session_id": "ses_98765abc", // 拿到 ID
      "status": "created"
    }
    ```
*   **前端逻辑**：
    1.  显示加载状态 (Loading spinner)。
    2.  获取到 `session_id`。
    3.  **路由跳转**：`router.push('/practice/ses_98765abc')`。

---

## 📂 五、实时练习页面 (Practice Session) - `/practice/[id]`

此页面为**重交互**页面，分为初始化和实时通信两部分。

### 5.1 初始化会话信息 (Init Session)
*   **调用时机**：页面组件挂载 (`useEffect`)。
*   **接口**：`GET /api/v1/sessions/{session_id}`
*   **展示数据**：
    *   `agent_name`: "怀疑型客户" (标题)
    *   `duration`: 00:00 (计时器初始值)
    *   `history_messages`: [] (如果是从断点恢复，需加载历史消息)

### 5.2 建立 WebSocket 连接 (Realtime Stream) - 🟢 核心
*   **连接地址**：`wss://api.domain.com/ws/practice/{session_id}?token=...`
*   **前端处理逻辑**：

    *   **📤 发送 (Client Send)**:
        *   **音频流 (`audio_data`)**: 当用户按下空格/录音按钮时，通过 `MediaRecorder` API 获取音频块，转为 Blob/Base64 发送。
        *   **开始说话 (`vad_start`)**: 告诉后端用户开始说话了 (用于打断 AI)。
        *   **停止说话 (`vad_end`)**: 告诉后端用户说完了。

    *   **📥 接收 (Server Push)**:
        *   **`transcript` (字幕)**:
            *   数据：`{ "role": "user" | "ai", "text": "...", "is_final": boolean }`
            *   逻辑：实时更新聊天气泡。`is_final=false` 时显示打字机效果/灰字，`true` 时确定文本。
        *   **`audio_playback` (语音)**:
            *   数据：二进制音频流。
            *   逻辑：前端播放器队列播放 AI 的回复。
        *   **`analysis_alert` (实时提示 - 右侧面板)**:
            *   数据：`{ "type": "fuzzy", "content": "检测到模糊词'大概'，建议使用具体数字" }`
            *   逻辑：在右侧 "实时提示" 区域追加一条警告卡片。
        *   **`score_update` (实时评分 - 右侧面板)**:
            *   数据：`{ "dimensions": { "专业度": 82, "沟通": 70 } }`
            *   逻辑：更新右侧进度条的 `width` 百分比。

### 5.3 结束练习 (End Session)
*   **交互**：点击右上角 "结束练习" 按钮。
*   **接口**：`POST /api/v1/sessions/{session_id}/end`
*   **前端逻辑**：
    1.  停止录音，断开 WebSocket。
    2.  显示 "生成报告中..." Loading 遮罩。
    3.  跳转至报告页：`/practice/{session_id}/report`。

---

## 📂 六、练习报告页 (Report) - `/practice/[id]/report`

### 6.1 获取详细报告 (Get Report)
*   **调用时机**：页面加载时。
*   **接口**：`GET /api/v1/sessions/{session_id}/report`
*   **响应数据结构 (用于渲染)**：
    ```json
    {
      "summary": {
        "total_score": 78,           // 顶部大圆环分数
        "level": "Good",             // "良好"
        "score_diff": 5              // "+5分" (比率/差值由后端计算)
      },
      "radar_chart": [               // 雷达图数据
        { "subject": "专业度", "score": 85, "fullMark": 100 },
        { "subject": "沟通技巧", "score": 72, "fullMark": 100 },
        { "subject": "销售流程", "score": 80, "fullMark": 100 },
        { "subject": "异议处理", "score": 75, "fullMark": 100 },
        { "subject": "成交能力", "score": 78, "fullMark": 100 }
      ],
      "feedback": {
        "good": [                    // "做得好" 列表
          "开场白自然流畅...",
          "善于使用案例..."
        ],
        "bad": [                     // "需改进" 列表
          "使用了3次模糊词...",
          "价格谈判过早让步"
        ],
        "suggestion": [              // "建议" 列表
          "准备更多数据支撑..."
        ]
      },
      "transcript_url": "/api/..."   // 完整对话记录下载链接(可选)
    }
    ```

### 6.2 再练一次 (Retry)
*   **交互**：点击底部 "再练一次"。
*   **逻辑**：调用 **4.2 创建练习接口** (使用当前报告对应的 `agent_id`)，重新开始流程。

---

## 📂 七、历史记录 (History) - `/history`

### 7.1 获取历史列表 (Get History)
*   **调用时机**：页面加载。
*   **接口**：`GET /api/v1/sessions`
*   **查询参数**：
    *   `page`: 1 (分页)
    *   `page_size`: 10
*   **响应数据结构**：
    ```json
    {
      "total": 42,
      "items": [
        {
          "id": "ses_1",
          "title": "销售对练 - 怀疑型客户",
          "agent_type": "sales",     // 决定图标 (Mic vs Presentation)
          "start_time": "2024-01-15T14:30:00Z", // 前端需格式化时间
          "duration_seconds": 512,   // 前端格式化为 "8分32秒"
          "score": 78                // 决定分数颜色 (Green/Yellow/Red)
        },
        // ...
      ]
    }
    ```

---

## 📝 前端开发 Checklist

1.  **Mock 数据**：在后端接口未就绪前，请在 `src/lib/api-mock.ts` 中按照上述 JSON 结构创建 Mock 函数，确保 UI 开发不阻塞。
2.  **错误处理**：所有接口调用需包裹在 `try-catch` 中，统一处理 401 (未登录)、403 (无权限)、500 (服务器错误)。
3.  **Loading 状态**：
    *   列表页：骨架屏 (Skeleton)。
    *   按钮操作：Loading Spinner (防止重复提交)。
4.  **WebSocket 心跳**：在练习页面，需实现 WS 断线重连机制 (Reconnection)。
