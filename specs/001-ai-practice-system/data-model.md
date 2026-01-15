# Data Model: Enterprise AI Intelligent Practice System

**Date**: 2025-01-10
**Status**: Complete

## Entity Relationship Diagram

```
┌─────────────┐         ┌──────────────┐         ┌────────────────┐
│    User     │───────<│PracticeSession│>────────│  Scenario     │
│  (用户)     │  1:N   │ (演练会话)   │  N:1    │  (演练场景)   │
└─────────────┘         └──────┬───────┘         └────────────────┘
                               │
                               │ N:1
                               ▼
                        ┌──────────────┐
                        │ Presentation │
                        │  (演示文稿)  │
                        └──────┬───────┘
                               │
                  ┌────────────┼────────────┐
                  │ 1:N       │ 1:N         │ 1:N
                  ▼           ▼             ▼
           ┌──────────┐ ┌─────────┐ ┌──────────────┐
           │   Page   │ │   Required│ │ ForbiddenWord│
           │  (页面)  │ │ TalkingPoint│ (禁忌词)   │
           └──────────┘ └─────────┘ └──────────────┘
                               │
                               │ 1:N
                               ▼
                        ┌──────────────┐
                        │InterruptionEvent│
                        │  (打断事件)  │
                        └──────────────┘

┌─────────────┐
│Leaderboard  │
│  (排行榜)   │
└──────┬──────┘
       │ N:1
       ▼
┌─────────────┐
│    User     │
└─────────────┘
```

---

## Entity Definitions

### 1. User (用户)

**Purpose**: Represents an employee who uses the practice system

**Attributes**:

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| user_id | UUID | PRIMARY KEY | Unique identifier |
| wechat_user_id | VARCHAR(128) | UNIQUE, NOT NULL | Enterprise WeChat user ID |
| name | VARCHAR(100) | NOT NULL | User's display name |
| department | VARCHAR(100) | | Department name |
| email | VARCHAR(255) | UNIQUE | Email address |
| created_at | TIMESTAMP | DEFAULT NOW() | Account creation time |
| last_login | TIMESTAMP | | Last login time |
| is_active | BOOLEAN | DEFAULT TRUE | Account status |

**Relationships**:
- Has many PracticeSession
- Appears in LeaderboardEntry

**Indexes**:
- `idx_wechat_user_id` on `wechat_user_id` (for SSO lookup)

**Validation**:
- `wechat_user_id` required for authentication
- Email format validation

---

### 2. Scenario (演练场景)

**Purpose**: Represents a practice scenario type

**Attributes**:

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| scenario_id | UUID | PRIMARY KEY | Unique identifier |
| scenario_type | ENUM | NOT NULL | 'presentation' or 'sales' |
| name | VARCHAR(100) | NOT NULL | Display name |
| description | TEXT | | Scenario description |
| persona_prompt | TEXT | | AI persona prompt (for sales bot) |
| is_active | BOOLEAN | DEFAULT TRUE | Scenario availability |
| created_at | TIMESTAMP | DEFAULT NOW() | Creation time |

**Relationships**:
- Has many PracticeSession

**Validation**:
- `scenario_type` must be 'presentation' or 'sales'
- `persona_prompt` required for 'sales' type

---

### 3. Presentation (演示文稿)

**Purpose**: Represents a PPT file uploaded for practice

**Attributes**:

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| presentation_id | UUID | PRIMARY KEY | Unique identifier |
| title | VARCHAR(200) | NOT NULL | Presentation title |
| file_url | VARCHAR(500) | NOT NULL | Storage location |
| file_size_bytes | INTEGER | | File size for monitoring |
| upload_date | TIMESTAMP | DEFAULT NOW() | Upload time |
| version_number | INTEGER | DEFAULT 1 | Version tracking |
| status | ENUM | DEFAULT 'processing' | 'processing', 'ready', 'failed' |
| uploaded_by_admin_id | UUID | FK → User | Admin who uploaded |
| total_pages | INTEGER | | Number of pages |
| ocr_progress | FLOAT | DEFAULT 0 | 0.0 to 1.0 |

**Relationships**:
- Belongs to User (admin)
- Has many Page
- Has many RequiredTalkingPoint
- Has many ForbiddenWord
- Has many PracticeSession

**Indexes**:
- `idx_status` on `status` (for processing queries)

**Validation**:
- `file_url` must be accessible
- `version_number` auto-increments on re-upload

**State Transitions**:
```
processing → ready (OCR completed successfully)
processing → failed (OCR error, manual intervention needed)
ready → processing (new version uploaded)
```

---

### 4. Page (页面)

**Purpose**: Represents a single page within a presentation

**Attributes**:

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| page_id | UUID | PRIMARY KEY | Unique identifier |
| presentation_id | UUID | FK → Presentation | Parent presentation |
| page_number | INTEGER | NOT NULL | 1-based page index |
| ocr_extracted_text | TEXT | | Text from OCR |
| image_url | VARCHAR(500) | | Page image thumbnail |
| extraction_confidence | FLOAT | | OCR confidence score |
| needs_manual_review | BOOLEAN | DEFAULT FALSE | Flag for admin review |

**Relationships**:
- Belongs to Presentation
- Has many RequiredTalkingPoint
- Has many ForbiddenWord (page-specific)

**Unique Constraint**:
- `(presentation_id, page_number)` must be unique

**Validation**:
- `page_number` >= 1
- `extraction_confidence` between 0.0 and 1.0

---

### 5. RequiredTalkingPoint (必讲点)

**Purpose**: Represents a key point that must be mentioned during a specific page

**Attributes**:

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| point_id | UUID | PRIMARY KEY | Unique identifier |
| page_id | UUID | FK → Page | Associated page |
| description | TEXT | NOT NULL | Required point description |
| created_by | ENUM | NOT NULL | 'admin' or 'ai' |
| is_ai_generated | BOOLEAN | DEFAULT FALSE | AI or manual |
| confirmed_by_admin | BOOLEAN | DEFAULT TRUE | Admin confirmation |
| created_at | TIMESTAMP | DEFAULT NOW() | Creation time |

**Relationships**:
- Belongs to Page

**Indexes**:
- `idx_page_id` on `page_id` (for queries during practice)

**Validation**:
- If `is_ai_generated = TRUE`, requires `confirmed_by_admin = TRUE` (or review pending)

---

### 6. ForbiddenWord (禁忌词)

**Purpose**: Represents a word or phrase that should not be used

**Attributes**:

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| word_id | UUID | PRIMARY KEY | Unique identifier |
| presentation_id | UUID | FK → Presentation (nullable) | Global for presentation |
| page_id | UUID | FK → Page (nullable) | Page-specific |
| phrase | VARCHAR(500) | NOT NULL | Forbidden phrase |
| suggested_alternative | TEXT | | Replacement suggestion |
| is_regex | BOOLEAN | DEFAULT FALSE | Phrase is regex pattern |

**Relationships**:
- Belongs to Presentation OR Page (mutually exclusive)

**Unique Constraint**:
- Either `presentation_id` OR `page_id` must be set (not both, not neither)

**Validation**:
- `phrase` required
- If `is_regex = TRUE`, validate regex pattern

---

### 7. PracticeSession (演练会话)

**Purpose**: Represents a single practice session

**Attributes**:

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| session_id | UUID | PRIMARY KEY | Unique identifier |
| user_id | UUID | FK → User | User who practiced |
| scenario_id | UUID | FK → Scenario | Scenario type |
| presentation_id | UUID | FK → Presentation (nullable) | For presentation coaching |
| start_time | TIMESTAMP | DEFAULT NOW() | Session start |
| end_time | TIMESTAMP | | Session end |
| status | ENUM | DEFAULT 'preparing' | 'preparing', 'in_progress', 'paused', 'completed', 'scoring' |
| current_page | INTEGER | | Current page number (for PPT) |
| logic_score | FLOAT | | 0.0 to 100.0 |
| accuracy_score | FLOAT | | 0.0 to 100.0 |
| completeness_score | FLOAT | | 0.0 to 100.0 |
| audio_url | VARCHAR(500) | | Recording location |
| transcript_url | VARCHAR(500) | | Transcript location |
| total_duration_seconds | INTEGER | | Session length |
| llm_tokens_used | INTEGER | DEFAULT 0 | Cost tracking |
| interruption_count | INTEGER | DEFAULT 0 | Number of interruptions |

**Relationships**:
- Belongs to User
- Belongs to Scenario
- Belongs to Presentation (optional, for presentation coaching)
- Has many InterruptionEvent

**Indexes**:
- `idx_user_id` on `user_id` (for user history)
- `idx_status` on `status` (for active sessions)
- `idx_start_time` on `start_time` (for analytics)

**Validation**:
- If `scenario_type = 'presentation'`, `presentation_id` required
- Scores between 0.0 and 100.0

**State Transitions**:
```
preparing → in_progress (user starts)
in_progress → paused (user pauses)
paused → in_progress (user resumes)
in_progress → scoring (user ends)
scoring → completed (report generated)
```

---

### 8. InterruptionEvent (打断事件)

**Purpose**: Represents an instance where the AI interrupted the user

**Attributes**:

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| event_id | UUID | PRIMARY KEY | Unique identifier |
| session_id | UUID | FK → PracticeSession | Parent session |
| timestamp | TIMESTAMP | DEFAULT NOW() | When interruption occurred |
| interruption_type | ENUM | NOT NULL | 'forbidden_word', 'missing_point', 'vague_response' |
| trigger_content | TEXT | | What triggered interruption |
| ai_response | TEXT | NOT NULL | What AI said |
| user_response_after | TEXT | | How user responded |
| detection_latency_ms | INTEGER | | Time to detect |
| was_effective | BOOLEAN | | Did user improve? |

**Relationships**:
- Belongs to PracticeSession

**Indexes**:
- `idx_session_id` on `session_id` (for session replay)

**Validation**:
- `detection_latency_ms` recorded for performance monitoring

---

### 9. LeaderboardEntry (排行榜条目)

**Purpose**: Represents a user's ranking position

**Attributes**:

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| entry_id | UUID | PRIMARY KEY | Unique identifier |
| user_id | UUID | FK → User | User reference |
| scenario_type | ENUM | NOT NULL | 'presentation' or 'sales' |
| presentation_id | UUID | FK → Presentation (nullable) | For specific PPT |
| average_score | FLOAT | NOT NULL | Weighted average |
| total_sessions | INTEGER | DEFAULT 1 | Session count |
| rank | INTEGER | | Calculated rank |
| last_updated | TIMESTAMP | DEFAULT NOW() | Update time |

**Relationships**:
- Belongs to User

**Unique Constraint**:
- `(user_id, scenario_type, presentation_id)` must be unique

**Indexes**:
- `idx_scenario_type` on `scenario_type` (for leaderboard queries)
- `idx_rank` on `rank` (for pagination)

**Validation**:
- `average_score` between 0.0 and 100.0
- `rank` recalculated on each session completion

---

## SOLID Principles Validation

### Single Responsibility Principle
- Each entity represents ONE concept (User, Session, Presentation, etc.)
- No entity mixes concerns (e.g., PracticeSession is separate from InterruptionEvent)

### Open/Closed Principle
- Adding new scenario types:只需在 `Scenario.scenario_type` ENUM 添加新值
- Adding new interruption types:只需在 `InterruptionEvent.interruption_type` ENUM 添加新值
- No existing code needs modification

### Liskov Substitution Principle
- Not applicable (no inheritance hierarchy in data model)

### Interface Segregation Principle
- Entities only have attributes they need
- Optional fields marked nullable (e.g., `presentation_id` in PracticeSession for sales bot scenario)

### Dependency Inversion Principle
- Foreign keys depend on abstract identifiers (UUID), not concrete implementations
- No hard-coded technology dependencies in schema

---

## PostgreSQL Schema (DDL)

```sql
-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Users
CREATE TABLE users (
    user_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    wechat_user_id VARCHAR(128) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    department VARCHAR(100),
    email VARCHAR(255) UNIQUE,
    created_at TIMESTAMP DEFAULT NOW(),
    last_login TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_users_wechat ON users(wechat_user_id);

-- Scenarios
CREATE TABLE scenarios (
    scenario_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    scenario_type VARCHAR(20) NOT NULL CHECK (scenario_type IN ('presentation', 'sales')),
    name VARCHAR(100) NOT NULL,
    description TEXT,
    persona_prompt TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Presentations
CREATE TABLE presentations (
    presentation_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(200) NOT NULL,
    file_url VARCHAR(500) NOT NULL,
    file_size_bytes INTEGER,
    upload_date TIMESTAMP DEFAULT NOW(),
    version_number INTEGER DEFAULT 1,
    status VARCHAR(20) DEFAULT 'processing' CHECK (status IN ('processing', 'ready', 'failed')),
    uploaded_by_admin_id UUID REFERENCES users(user_id),
    total_pages INTEGER,
    ocr_progress FLOAT DEFAULT 0
);

CREATE INDEX idx_presentations_status ON presentations(status);

-- Pages
CREATE TABLE pages (
    page_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    presentation_id UUID NOT NULL REFERENCES presentations(presentation_id),
    page_number INTEGER NOT NULL,
    ocr_extracted_text TEXT,
    image_url VARCHAR(500),
    extraction_confidence FLOAT,
    needs_manual_review BOOLEAN DEFAULT FALSE,
    UNIQUE(presentation_id, page_number)
);

CREATE INDEX idx_pages_presentation ON pages(presentation_id);

-- Required Talking Points
CREATE TABLE required_talking_points (
    point_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    page_id UUID NOT NULL REFERENCES pages(page_id),
    description TEXT NOT NULL,
    created_by VARCHAR(10) NOT NULL CHECK (created_by IN ('admin', 'ai')),
    is_ai_generated BOOLEAN DEFAULT FALSE,
    confirmed_by_admin BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_talking_points_page ON required_talking_points(page_id);

-- Forbidden Words
CREATE TABLE forbidden_words (
    word_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    presentation_id UUID REFERENCES presentations(presentation_id),
    page_id UUID REFERENCES pages(page_id),
    phrase VARCHAR(500) NOT NULL,
    suggested_alternative TEXT,
    is_regex BOOLEAN DEFAULT FALSE,
    CHECK (
        (presentation_id IS NOT NULL AND page_id IS NULL) OR
        (presentation_id IS NULL AND page_id IS NOT NULL)
    )
);

-- Practice Sessions
CREATE TABLE practice_sessions (
    session_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(user_id),
    scenario_id UUID NOT NULL REFERENCES scenarios(scenario_id),
    presentation_id UUID REFERENCES presentations(presentation_id),
    start_time TIMESTAMP DEFAULT NOW(),
    end_time TIMESTAMP,
    status VARCHAR(20) DEFAULT 'preparing' CHECK (status IN ('preparing', 'in_progress', 'paused', 'completed', 'scoring')),
    current_page INTEGER,
    logic_score FLOAT CHECK (logic_score BETWEEN 0 AND 100),
    accuracy_score FLOAT CHECK (accuracy_score BETWEEN 0 AND 100),
    completeness_score FLOAT CHECK (completeness_score BETWEEN 0 AND 100),
    audio_url VARCHAR(500),
    transcript_url VARCHAR(500),
    total_duration_seconds INTEGER,
    llm_tokens_used INTEGER DEFAULT 0,
    interruption_count INTEGER DEFAULT 0
);

CREATE INDEX idx_sessions_user ON practice_sessions(user_id);
CREATE INDEX idx_sessions_status ON practice_sessions(status);
CREATE INDEX idx_sessions_start ON practice_sessions(start_time);

-- Interruption Events
CREATE TABLE interruption_events (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES practice_sessions(session_id),
    timestamp TIMESTAMP DEFAULT NOW(),
    interruption_type VARCHAR(30) NOT NULL CHECK (interruption_type IN ('forbidden_word', 'missing_point', 'vague_response')),
    trigger_content TEXT,
    ai_response TEXT NOT NULL,
    user_response_after TEXT,
    detection_latency_ms INTEGER,
    was_effective BOOLEAN
);

CREATE INDEX idx_interruptions_session ON interruption_events(session_id);

-- Leaderboard
CREATE TABLE leaderboard_entries (
    entry_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(user_id),
    scenario_type VARCHAR(20) NOT NULL CHECK (scenario_type IN ('presentation', 'sales')),
    presentation_id UUID REFERENCES presentations(presentation_id),
    average_score FLOAT NOT NULL CHECK (average_score BETWEEN 0 AND 100),
    total_sessions INTEGER DEFAULT 1,
    rank INTEGER,
    last_updated TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, scenario_type, COALESCE(presentation_id, '00000000-0000-0000-0000-000000000000'::UUID))
);

CREATE INDEX idx_leaderboard_scenario ON leaderboard_entries(scenario_type);
CREATE INDEX idx_leaderboard_rank ON leaderboard_entries(rank);
```

---

## ChromaDB Collection Structure

### Collection: ppt_knowledge

```python
{
    "collection_name": "ppt_knowledge",
    "metadata": {
        "hnsw:space": "cosine",
        "hnsw:construction_ef": 200,
        "hnsw:M": 16
    }
}
```

### Document Schema

```python
{
    "document": "Extracted text from PPT page",
    "metadata": {
        "presentation_id": "uuid",
        "page_number": 3,
        "page_id": "uuid",
        "ocr_confidence": 0.95
    },
    "id": "page_uuid",
    "embedding": [0.1, 0.2, ...]  # Auto-generated
}
```

### Query Example

```python
results = collection.query(
    query_texts=["user question about current page"],
    where={
        "presentation_id": "ppt_001",
        "page_number": 3
    },
    n_results=3
)
```

---

## Data Validation Summary

| Entity | Critical Validations | State Transitions |
|--------|---------------------|-------------------|
| User | wechat_user_id required, email format | is_active toggle |
| Scenario | type enum, persona for sales | is_active toggle |
| Presentation | file accessible, version tracking | processing → ready/failed |
| Page | page_number >= 1, unique per PPT | needs_manual_review flag |
| RequiredTalkingPoint | AI needs confirmation | N/A |
| ForbiddenWord | mutually exclusive FK | N/A |
| PracticeSession | scores 0-100, presentation optional | preparing → in_progress → scoring → completed |
| InterruptionEvent | latency tracking | N/A |
| LeaderboardEntry | rank recalculated | N/A |
