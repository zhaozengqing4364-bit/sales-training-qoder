# Quickstart Guide: Enterprise AI Intelligent Practice System

**Last Updated**: 2025-01-10
**For**: Developers starting implementation

---

## Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Node.js 18+ (for frontend)
- GPU with CUDA support (for qwen3-asr-flash) OR CPU (slower)
- systemd or supervisor (for production process management)

---

## 1. Backend Setup (5 minutes)

### 1.1 Clone and Setup

```bash
# Clone repository
cd /path/to/repository
git checkout 001-ai-practice-system

# Create virtual environment
cd backend
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt
```

### 1.2 Environment Variables

Create `.env` file in `backend/`:

```bash
# Database
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/ai_practice
REDIS_URL=redis://localhost:6379/0

# AI Services
OPENAI_API_KEY=sk-...your-key
OPENAI_BASE_URL=https://api.openai.com/v1  # or your proxy

# Vector Database
CHROMADB_PERSIST_DIR=./data/chromadb

# Enterprise WeChat
WECHAT_CORP_ID=your_corp_id
WECHAT_SECRET=your_secret

# Storage
AUDIO_STORAGE_PATH=./data/audio
PPT_STORAGE_PATH=./data/ppts

# JWT
JWT_SECRET=your-super-secret-key-change-in-production
JWT_ALGORITHM=HS256

# Monitoring
LOG_LEVEL=INFO
ENABLE_TRACING=true
```

### 1.3 Initialize Database

```bash
# Run migrations
alembic upgrade head

# Or create tables directly
python -m src.db.init_db
```

### 1.4 Start Backend Server

```bash
# Development
uvicorn src.main:app --reload --port 8000

# Production
uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 4
```

**Verify**: Visit `http://localhost:8000/docs` for API documentation.

---

## 2. ASR & TTS Setup (10 minutes)

### 2.1 Install qwen3-asr-flash

```bash
# Install FunASR
pip install funasr

# Download qwen3-asr-flash model (first time only)
python -c "
from funasr import AutoModel
model = AutoStreammodel(
    model='qwen3-asr-flash',
    device='cuda'  # or 'cpu'
)
"
```

**Model location**: `~/.cache/funasr/`

### 2.2 Test ASR

```python
# test_asr.py
import asyncio
from funasr import AutoModel

asr = AutoModel(model="qwen3-asr-flash", device="cuda")

async def stream_asr(audio_file):
    async for chunk in asr.generate(input=audio_file, stream=True):
        print(chunk["text"])

asyncio.run(stream_asr("test.wav"))
```

### 2.3 Test Edge-TTS

```bash
pip install edge-tts
python -m edge_tts --text "你好，这是一个测试" --voice zh-CN-XiaoxiaoNeural --out test.mp3
```

---

## 3. Frontend Setup (5 minutes)

### 3.1 Install Dependencies

```bash
cd frontend
npm install
```

### 3.2 Environment Variables

Create `.env.local`:

```bash
VITE_API_URL=http://localhost:8000/v1
VITE_WS_URL=ws://localhost:8000/ws
```

### 3.3 Start Dev Server

```bash
npm run dev
```

**Verify**: Visit `http://localhost:5173`

---

## 4. Process Management (Production)

### 4.1 Using systemd

Create `/etc/systemd/system/ai-practice-backend.service`:

```ini
[Unit]
Description=AI Practice Backend
After=network.target postgresql.service

[Service]
Type=notify
User=ai-practice
WorkingDirectory=/opt/ai-practice/backend
Environment="PATH=/opt/ai-practice/backend/venv/bin"
ExecStart=/opt/ai-practice/backend/venv/bin/uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable ai-practice-backend
sudo systemctl start ai-practice-backend
sudo systemctl status ai-practice-backend
```

### 4.2 Using supervisor

Create `/etc/supervisor/conf.d/ai-practice-backend.conf`:

```ini
[program:ai-practice-backend]
command=/opt/ai-practice/backend/venv/bin/uvicorn src.main:app --host 0.0.0.0 --port 8000
directory=/opt/ai-practice/backend
user=ai-practice
autostart=true
autorestart=true
stderr_logfile=/var/log/supervisor/ai-practice-backend.err.log
stdout_logfile=/var/log/supervisor/ai-practice-backend.out.log
```

Enable and start:
```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start ai-practice-backend
```

---

## 5. First Practice Session

### 5.1 Create Test Data

```bash
# Using the API
curl -X POST http://localhost:8000/v1/presentations \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@test.pptx" \
  -F "title=Test Presentation"
```

### 5.2 Start Session

```bash
# Create session
curl -X POST http://localhost:8000/v1/practice/sessions \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "scenario_type": "presentation",
    "presentation_id": "uuid-from-step-1"
  }'
```

Response includes `session_id`.

### 5.3 Connect WebSocket

```javascript
const ws = new WebSocket(`ws://localhost:8000/ws/presentation?session_id=${session_id}&token=YOUR_TOKEN`);

ws.onopen = () => {
  console.log('Connected!');
  // Start sending audio chunks...
};
```

---

## 6. Run Tests

### 6.1 Backend Tests

```bash
cd backend

# Unit tests
pytest tests/unit/

# Integration tests
pytest tests/integration/

# Performance tests (50 concurrent sessions)
pytest tests/performance/
```

### 6.2 Frontend Tests

```bash
cd frontend

# Unit tests
npm run test

# E2E tests
npm run test:e2e
```

---

## 7. Development Workflow

### Daily Development

1. **Start PostgreSQL**: `sudo systemctl start postgresql`
2. **Run backend**: `cd backend && source venv/bin/activate && uvicorn src.main:app --reload`
3. **Run frontend**: `cd frontend && npm run dev`
4. **Run tests**: `pytest backend/tests/`
5. **Check metrics**: http://localhost:3000 (Grafana)

### Adding a New Feature

1. **Create branch**: `git checkout -b feature/your-feature`
2. **Implement**: Write code in `backend/src/` or `frontend/src/`
3. **Test**: Write tests in `backend/tests/` or `frontend/tests/`
4. **Verify**: Run performance tests if latency-critical
5. **Document**: Update relevant spec/docs
6. **PR**: Create pull request for review

### Code Review Checklist

- [ ] No error popups in frontend
- [ ] All errors have fallbacks
- [ ] Latency <300ms for interactions
- [ ] Structured logging with trace_id
- [ ] Tests pass (unit + integration)
- [ ] No hardcoded secrets
- [ ] Async/await used for all I/O

---

## 8. Monitoring & Debugging

### 8.1 View Logs

```bash
# Backend logs (if running with systemd)
sudo journalctl -u ai-practice-backend -f

# Backend logs (if running with supervisor)
sudo tail -f /var/log/supervisor/ai-practice-backend.out.log

# Backend logs (development mode)
cd backend && source venv/bin/activate
tail -f logs/app.log

# Filter errors
sudo journalctl -u ai-practice-backend | grep ERROR
```

### 8.2 Check Metrics

**Grafana Dashboard**: http://localhost:3000
- Login: `admin` / `admin` (change on first login)
- Import dashboard: `specs/001-ai-practice-system/grafana-dashboard.json`

**Key Metrics to Watch**:
- End-to-end latency (p95 should be <300ms)
- WebSocket connections (should be <50)
- Error rate (should be <1%)
- LLM token usage (cost tracking)

### 8.3 Trace a Request

```python
# All requests have trace_id in logs
logger.info("Processing request", extra={"trace_id": "abc123"})

# Search logs
grep "trace_id=abc123" backend/logs/app.log
```

---

## 9. Common Issues

### Issue: ASR latency >200ms

**Solution**:
1. Check GPU is being used: `nvidia-smi`
2. Verify model is loaded: Check logs for "Model loaded"
3. Reduce audio chunk size: Try 100ms instead of 200ms

### Issue: WebSocket disconnects frequently

**Solution**:
1. Check nginx/proxy timeout settings (if behind proxy)
2. Enable WebSocket keepalive
3. Verify client reconnection logic

### Issue: LLM API timeout

**Solution**:
1. Check `OPENAI_BASE_URL` is correct
2. Verify API key has credits
3. Implement fallback (predefined responses)

### Issue: Frontend shows error popup

**Solution**:
1. This is a BUG - violates constitution!
2. Check error handler in `frontend/src/utils/error-handler.js`
3. Ensure all errors are caught and converted to status updates

---

## 10. Production Deployment

### 10.1 Prepare Environment

```bash
# On production server
sudo mkdir -p /opt/ai-practice
sudo useradd -r -s /bin/bash ai-practice
sudo chown -R ai-practice:ai-practice /opt/ai-practice

# Copy code to server
cd /opt/ai-practice
git clone <your-repo> backend

# Setup virtual environment
cd backend
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Create admin user
python -m src.scripts.create_admin
```

### 10.2 Deploy

```bash
# Setup systemd service (see Section 4.1)
sudo cp deploy/ai-practice-backend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable ai-practice-backend

# Start service
sudo systemctl start ai-practice-backend

# Check health
curl http://your-domain.com/health
```

### 10.3 Monitor

```bash
# Check logs
sudo journalctl -u ai-practice-backend -f

# Check metrics
curl http://your-domain.com/metrics
```

---

## 11. Next Steps

1. **Read the full specs**:
   - `specs/001-ai-practice-system/spec.md` - Feature specification
   - `specs/001-ai-practice-system/plan.md` - Implementation plan
   - `specs/001-ai-practice-system/research.md` - Technical research

2. **Run `/speckit.tasks`** to generate actionable tasks

3. **Join the team channel** for questions

---

## Quick Reference

| Command | Purpose |
|---------|---------|
| `python -m venv venv` | Create virtual environment |
| `pytest backend/tests/` | Run backend tests |
| `npm run test` | Run frontend tests |
| `uvicorn src.main:app --reload` | Start backend dev server |
| `npm run dev` | Start frontend dev server |
| `alembic upgrade head` | Run database migrations |
| `sudo systemctl start ai-practice-backend` | Start production service |
| `sudo journalctl -u ai-practice-backend -f` | View backend logs |

---

## Support

- **Documentation**: `specs/001-ai-practice-system/`
- **Issues**: GitHub Issues
- **Questions**: Team Slack channel
