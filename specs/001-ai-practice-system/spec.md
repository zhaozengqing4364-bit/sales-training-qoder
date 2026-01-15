# Feature Specification: Enterprise AI Intelligent Practice System

**Feature Branch**: `001-ai-practice-system`
**Created**: 2025-01-10
**Status**: Draft
**Input**: Enterprise AI Intelligent Practice System - PPT Presentation Coach and Sales Training Bot

---

## Clarifications

### Session 2025-01-10

- Q: Should ForbiddenWord support both global (presentation-level) and page-specific scope, or only one level? → A: Support two-level scope with global presentation-level prohibitions (e.g., "I don't know") and page-specific restrictions, distinguished by a `scope` field in the ForbiddenWord entity.
- Q: How should the system handle new practice sessions when the 50-concurrent limit is reached? → A: Hard rate limiting - reject new sessions immediately with a friendly "System busy, please try again later" message. Simple implementation with clear user expectation.
- Q: What is the strategy for managing external service API version compatibility (ASR, TTS, LLM, ChromaDB, WeChat)? → A: Explicit version locking in configuration files. Pin specific versions for reproducibility. Regular security scans and planned upgrade windows.
- Q: What architecture pattern should be used for the overall system design? → A: Modular monolith - single FastAPI application with Python packages and module boundaries isolating PPT coaching and sales bot scenarios. Simplifies deployment, reduces operational complexity, maintains future microservices flexibility.
- Q: What is the long-term data retention and deletion strategy for practice recordings and transcripts? → A: Tiered retention - audio permanently deleted after 3 years, text transcripts retained indefinitely. Support user export/deletion requests for GDPR compliance.
- Q: How should cost control (<¥1/session) be balanced against quality requirements? → A: Priority matrix: (1) Single session - high priority for both, use free/low-cost solutions without degrading core experience; (2) 50 concurrent - high cost, medium quality, maintain basic functionality; (3) System stability - highest priority, degrade quality to maintain stability. Quality baseline: ASR latency <300ms even when degraded, TTS quality no worse than browser native, AI intelligence no worse than GPT-3.5.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - PPT Presentation Real-time Coach (Priority: P1)

**Description**: An employee uploads a PPT presentation and practices their delivery with an AI coach that listens in real-time, provides immediate feedback through voice interruptions, and generates a comprehensive performance report after completion.

**Why this priority**: This is the core differentiator of the system - real-time voice interaction with bidirectional interruption capability. It directly addresses the pain point of high training costs and delayed feedback in traditional corporate training.

**Independent Test**: Can be tested by uploading a sample PPT, configuring required talking points, and conducting a 5-minute practice session. The AI should interrupt when required points are missed, and a score report should be generated at the end.

**Acceptance Scenarios**:

1. **Given** an administrator has uploaded a PPT and configured required talking points for page 3, **When** an employee practices and reaches page 3 without mentioning "proprietary technology", **Then** the AI immediately interrupts with voice feedback: "Wait, you haven't mentioned our proprietary technology yet."

2. **Given** an employee is practicing presentation, **When** they use a forbidden word (e.g., "I don't know"), **Then** the AI immediately interrupts: "Please avoid saying 'I don't know'. Try saying 'Let me verify that information' instead."

3. **Given** an employee completes a 20-minute presentation practice, **When** they finish speaking, **Then** the system generates a score report within 10 seconds showing: logic score (85%), accuracy score (90%), completeness score (75%), and specific text-based improvement suggestions.

4. **Given** an employee is in the middle of a sentence, **When** the AI starts speaking to interrupt, **Then** the employee can interrupt back by speaking, and the AI immediately stops and starts listening again.

5. **Given** the network connection temporarily drops during practice, **When** the interruption lasts less than 3 seconds, **Then** the system automatically reconnects without showing any error popup, and the conversation continues seamlessly.

---

### User Story 2 - Sales Sparring Bot with Pressure Scenarios (Priority: P1)

**Description**: An employee engages in a high-pressure sales conversation where an AI plays a difficult customer persona (e.g., impatient CEO, skeptical buyer) and challenges the employee's responses with tough questions and objections.

**Why this priority**: This is the second core scenario that demonstrates the system's unique bidirectional interruption capability. It provides realistic sales training that employees cannot get from traditional role-playing.

**Independent Test**: Can be tested by selecting a "difficult customer" scenario and engaging in a 5-10 minute conversation. The AI should actively challenge weak responses, interrupt when answers are vague, and provide a performance summary at the end.

**Acceptance Scenarios**:

1. **Given** an employee selects "impatient CEO" as the customer persona, **When** the conversation begins, **Then** the AI acts with impatient characteristics (short responses, frequent interruptions, demanding direct answers).

2. **Given** the employee gives a vague answer like "our product is very good", **When** the AI detects this lack of specificity, **Then** the AI interrupts within 2 seconds: "That's too vague. Give me 3 specific metrics."

3. **Given** the AI is speaking and the employee needs to respond, **When** the employee starts speaking while the AI is still talking, **Then** the AI immediately stops speaking and switches to listening mode.

4. **Given** a conversation has been ongoing for 5 minutes, **When** the employee requests to end the session, **Then** the AI provides a summary of the conversation highlighting: strong points, weak arguments, and specific improvement suggestions.

5. **Given** the LLM API times out during the conversation, **When** the timeout occurs, **Then** the system plays a fallback response ("Let me think about that... can you tell me more?") and retries the API call in the background without showing any error to the user.

---

### User Story 3 - Knowledge Base Management (Priority: P2)

**Description**: Administrators can upload training materials (PPTs, white papers, product specifications), configure required talking points and forbidden words for each presentation page, and manage the knowledge base that powers the AI coach.

**Why this priority**: While critical for system operation, this can be initially seeded with sample data and enhanced later. The core value delivery happens during practice sessions (Stories 1 & 2).

**Independent Test**: Can be tested by an administrator logging into the management backend, uploading a 10-page PPT, setting 3 required talking points for page 5, and verifying that these points are correctly retrieved during a practice session.

**Acceptance Scenarios**:

1. **Given** an administrator uploads a 20-page PPT, **When** the upload completes, **Then** the system automatically performs OCR processing to extract text from each page and creates a searchable knowledge base indexed by page number.

2. **Given** the system has extracted text from page 7 of a PPT, **When** an administrator reviews the extraction, **Then** they can see the extracted text and can add/edit required talking points and forbidden words for that page.

3. **Given** an administrator has configured required points for pages 1-10 of a presentation, **When** an employee is practicing and currently on page 5, **Then** the AI only evaluates against the required points for page 5 (not pages 1-4 or 6-10).

4. **Given** an administrator uploads a new version of an existing PPT, **When** the upload is processed, **Then** the system automatically archives the old version and updates the knowledge base with the new content.

5. **Given** the vector database fails during a knowledge search, **When** the failure occurs, **Then** the system falls back to keyword-based search and continues the practice session without interruption.

---

### User Story 4 - Practice Analytics & Leaderboard (Priority: P3)

**Description**: Employees can view their practice history, track improvement over time, and see how they rank against peers on a leaderboard. Administrators can view aggregate statistics to identify training gaps.

**Why this priority**: This is an enhancement that drives engagement and provides management visibility but is not essential for the core coaching functionality to work.

**Independent Test**: Can be tested by completing 3 practice sessions over 2 days and verifying that: (1) history shows all 3 sessions, (2) scores show improvement trends, and (3) the leaderboard reflects the latest rankings.

**Acceptance Scenarios**:

1. **Given** an employee has completed 10 presentation practices over 2 weeks, **When** they view their practice history, **Then** they see a line chart showing their score progression and can click on any session to see the detailed feedback.

2. **Given** multiple employees have practiced the same presentation, **When** an employee views the leaderboard, **Then** they see rankings based on average scores, with their own position highlighted.

3. **Given** an administrator views the analytics dashboard, **When** they look at the aggregate statistics, **Then** they see metrics like: average practice completion rate, most common missing required points, and overall score distribution.

4. **Given** it's the end of the month, **When** the scheduled cleanup job runs, **Then** audio recordings older than 1 year are automatically archived to cold storage, while text transcripts remain available.

---

### Edge Cases

**Network & Connectivity**:
- What happens when the user's network connection drops completely during practice? **System buffers audio locally for up to 30 seconds and attempts reconnection. If reconnection fails, display a friendly "Connection lost - please reconnect" message without any error popup.**

- What happens when the backend ASR service becomes temporarily unavailable? **System switches to browser's built-in speech recognition as a fallback and logs the degradation for monitoring.**

- What happens when a WebSocket connection abruptly closes (server restart, network hiccup)? **Client automatically attempts to reconnect with exponential backoff (1s, 2s, 4s, 8s max). During reconnection, show a subtle "reconnecting..." indicator, not an error.**

**Voice Recognition & Synthesis**:
- What happens when the user speaks with heavy accent or mumbles and ASR returns low-confidence results? **System asks for clarification naturally: "I didn't quite catch that. Could you say it again?" rather than showing a technical error.**

- What happens when TTS generation fails (Edge-TTS service down)? **System falls back to browser's native text-to-speech or displays the text on screen with a "speaking" animation.**

- What happens when the user speaks for over 2 minutes without pause? **System gently interrupts: "You've been talking for a while. Shall we move to the next topic?" to prevent monologue.**

**AI & Knowledge Base**:
- What happens when the LLM API is rate-limited or returns a timeout? **System uses a predefined fallback response based on the context (e.g., "That's interesting. Tell me more about...") and retries in the background.**

- What happens when the vector database search returns zero results for a page? **System uses keyword matching as fallback and proceeds with evaluation based on general knowledge rather than page-specific content.**

- What happens when PPT OCR fails for certain pages (images without text, complex layouts)? **System marks those pages as "manual review required" and allows administrators to add required points manually.**

**User Experience**:
- What happens when the user accidentally clicks "end practice" while mid-sentence? **System shows a confirmation dialog: "Are you sure you want to end? Your progress will be saved."**

- What happens when multiple users try to access the same presentation simultaneously? **System handles concurrent access gracefully. Each user's session is independent.**

- What happens when the user switches apps or locks their screen during practice? **System pauses the session and shows a "practice paused - tap to resume" overlay when they return.**

**Content & Configuration**:
- What happens when a presentation has zero required points configured for a page? **System provides general feedback based on presentation skills (pace, clarity) rather than content-specific feedback.**

- What happens when forbidden words list is empty? **System skips vocabulary monitoring and focuses on content completeness.**

- What happens when an administrator tries to delete a presentation that has existing practice records? **System warns: "This presentation has 15 practice records. Delete anyway?" and preserves the historical records.**

**Performance & Scale**:
- What happens when 50 users simultaneously start practice sessions? **System must handle 50 concurrent WebSocket connections without degradation in response time (<300ms latency target maintained).**

- What happens when a single presentation has 100+ pages? **System must efficiently handle large PPTs with pagination and lazy loading of page content.**

---

## Requirements *(mandatory)*

### Functional Requirements

**Core Voice Interaction**:
- **FR-001**: System MUST support full-duplex WebSocket audio communication allowing simultaneous recording and playback.
- **FR-002**: System MUST convert user's voice to text in real-time using streaming ASR with latency <200ms.
- **FR-003**: System MUST generate human-like speech from text using TTS with natural intonation and emotion.
- **FR-004**: System MUST support bidirectional interruption where either the user or AI can interrupt the other at any time.
- **FR-005**: System MUST detect and handle user interruption (when user speaks while AI is talking) within 100ms.

**PPT Presentation Coaching**:
- **FR-006**: System MUST allow users to upload PPT files (PPTX format up to 50MB).
- **FR-007**: System MUST automatically extract text from PPT pages using OCR and create a searchable knowledge base.
- **FR-008**: System MUST allow administrators to configure required talking points per page (e.g., "Must mention: proprietary technology").
- **FR-009**: System MUST allow administrators to configure forbidden words that trigger immediate interruption.
- **FR-010**: System MUST track which page the user is currently presenting and evaluate only that page's requirements.
  - **Page Tracking Trigger Methods**: (1) User manual navigation (primary) - click/swipe to next page; (2) Voice command (secondary) - "next page", "go to page X"; (3) Auto-detection (fallback) - based on semantic similarity to next page content.
- **FR-011**: System MUST interrupt immediately when a forbidden word is detected.
- **FR-012**: System MUST interrupt when the user finishes a page without mentioning required talking points.
  - **Coverage Detection Standards**: (1) Fully Covered - user mentions core keywords (100% weight); (2) Partially Covered - user mentions related content without keywords (50% weight); (3) Not Covered - user doesn't mention related content (0% weight).
  - **Page Completion Criteria**: User explicitly says "done"/"next page", user pauses >10 seconds, or user starts talking about next page content.
- **FR-013**: System MUST generate a multi-dimensional score report (logic, accuracy, completeness) within 10 seconds of session completion.
  - **Scoring Formula**: `Overall = Logic×0.3 + Accuracy×0.4 + Completeness×0.3`
  - **Logic Score (0-100)**: `Base_Score × (1 - Logic_Faults×0.1)` - evaluates coherence and structure
  - **Accuracy Score (0-100)**: `(Verified_Statements / Total_Statements) × 100` - validates against knowledge base
  - **Completeness Score (0-100)**: `(Covered_Points / Total_Required_Points) × 100` - tracks required point coverage
  - **Grade Levels**: Excellent (90-100), Good (75-89), Needs Improvement (60-74), Poor (<60)
  - **Performance SLA**: Normal sessions (<100 interruptions) = 10s; Large sessions (100-500) = 30s; Extra large sessions (>500) = 60s
- **FR-014**: System MUST save both audio recording and text transcript of each practice session for one year.
- **FR-061**: System MUST support skipping PPT pages during practice.
  - **Skip Methods**: User clicks "Skip" button or uses voice command "skip this page"
  - **Impact**: Skipped pages excluded from completeness scoring, marked as "skipped" status
  - **AI Response**: "OK, let's move to the next page"

**Sales Sparring Bot**:
- **FR-015**: System MUST provide multiple customer personas (e.g., impatient CEO, skeptical buyer, price-focused procurement).
- **FR-016**: System MUST initiate conversation with an opening question based on the selected persona.
- **FR-017**: System MUST detect vague, evasive, or weak responses and interrupt with specific challenges.
  - **Vague Response Detection Criteria**: (1) Lack of specific data (no numbers, percentages, metrics); (2) Over-generalization (absolute terms like "always", "never"); (3) Evasion (response irrelevant to question); (4) Vague modifiers ("maybe", "probably", "about").
  - **AI Interruption Scripts**: "That's too vague. Give me 3 specific examples.", "You used 'maybe'. Can you give me a definite answer?", "I didn't hear specific data. Can you use numbers to explain?"
- **FR-018**: System MUST adapt questioning strategy based on user's previous responses (contextual conversation).
  - **Conversation Context Window**: Default 10 turns (5 user + 5 AI responses), maximum 20 turns, minimum 5 turns.
  - **Window Management**: FIFO (first-in-first-out) with key information retention, context compression every 5 turns.
- **FR-019**: System MUST provide a conversation summary at the end highlighting strengths and areas for improvement.

**Knowledge Base & Content Management**:
- **FR-020**: System MUST support metadata filtering in vector database to retrieve content by presentation ID and page number.
- **FR-021**: System MUST allow AI-assisted extraction of required talking points from PPT content (with human confirmation).
- **FR-022**: System MUST support versioning of presentations with automatic archiving of old versions.
- **FR-023**: System MUST allow administrators to manually edit OCR-extracted text and talking points.

**Error Handling & Resilience**:
- **FR-024**: System MUST NEVER show error popups to users during practice sessions.
- **FR-025**: System MUST implement automatic reconnection for WebSocket disconnections with exponential backoff.
  - **Session Recovery Strategy**: (1) Lossless recovery (<30s disconnect) - restore to exact state; (2) Partial recovery (30s-5min) - restore page/progress, prompt "We were on page X"; (3) Timeout reset (>5min) - end session and save progress.
- **FR-026**: System MUST provide fallback responses when LLM API times out or fails.
- **FR-027**: System MUST switch to backup TTS (browser native) when primary TTS fails.
- **FR-028**: System MUST fall back to keyword-based search when vector database search fails.
  - **Recovery Strategy**: Daily incremental backups, 30-day retention, restore from backup + PostgreSQL metadata, index rebuild may take hours
- **FR-029**: System MUST buffer audio locally for up to 30 seconds during brief network interruptions.

**User Management & Analytics**:
- **FR-030**: System MUST integrate with enterprise WeChat workbench for single sign-on authentication.
- **FR-031**: System MUST allow users to view their practice history with score trends.
- **FR-032**: System MUST display a leaderboard showing rankings based on average scores.
- **FR-033**: System MUST provide administrators with aggregate analytics dashboard (completion rates, common gaps, score distribution).

**Performance & Scalability**:
- **FR-034**: System MUST support up to 50 concurrent practice sessions without performance degradation.
- **FR-034A**: When the 50-concurrent limit is reached, system MUST reject new sessions immediately with a friendly "System busy, please try again later" message (hard rate limiting, no queuing).
- **FR-035**: System MUST achieve end-to-end response latency (user stops speaking → AI responds) <300ms for 95% of interactions.
- **FR-036**: System MUST complete initial page load in under 2 seconds.
  - **SLA Breakdown**: Includes HTML/CSS/JS loading, first paint, WebSocket connection; Excludes PPT image lazy-loading (async, <500ms per image) and knowledge base indexing (background, <3min for 20-page PPT).
- **FR-054**: System MUST track real-time cost per practice session with budget alerts.
  - **Cost Model**: LLM ~¥0.25/session, ASR ¥0, TTS ¥0, Storage ~¥0.001/session
  - **Monitoring**: Real-time per-call tracking, session-level summary, daily aggregation
  - **Alert Thresholds**: 80% (¥0.80) - warn log; 90% (¥0.90) - reduce complexity; 100% (¥1.00) - force end session
  - **Dimensions**: Per-user, per-scenario, per-time, per-component
- **FR-055**: System MUST monitor error rates with defined calculation and alert thresholds.
  - **Formula**: `Error_Rate = (Failed_Requests / Total_Requests) × 100%`
  - **Failed Request**: HTTP status >=500, WebSocket failure, ASR/TTS timeout, LLM failure
  - **Alert Thresholds**: Warning (1% for 5min), Severe (5% for 2min), Critical (10% for 1min)
  - **Response Actions**: Warning → notify admin; Severe → SMS + degrade service; Critical → SMS + call + consider service pause

**Data & Privacy**:
- **FR-037**: System MUST encrypt all data in transit using TLS.
- **FR-038**: System MUST ensure practice records are only accessible to the user who created them and administrators.
- **FR-039**: System MUST allow users to delete their own practice records.
  - **Deletion Strategy**: (1) Soft delete - user clicks "delete", sets `deleted_at` timestamp, data retained for 30-day recovery; (2) Hard delete - scheduled task after 30 days, physical delete of DB records and audio, text transcripts kept for analytics; (3) Admin delete - bulk cleanup, irreversible, operation logged.
- **FR-040**: System MUST implement tiered data retention: (1) archive audio to cold storage after 1 year, (2) permanently delete audio after 3 years, (3) retain text transcripts indefinitely.
- **FR-040A**: System MUST support user data export requests (provide downloadable JSON/CSV of all personal data) for GDPR compliance.
- **FR-040B**: System MUST provide administrators with tools to bulk-delete historical audio data older than 3 years upon user request.

**External Dependency Management**:
- **FR-041**: System MUST pin explicit versions for all external service dependencies (qwen3-asr-flash, Edge-TTS, LangChain, ChromaDB, enterprise WeChat SDK) in configuration files.
- **FR-042**: System MUST implement automated security scanning of external dependencies on a weekly basis.
  - **Failure Handling**: (1) Critical/High severity - block deployment, require security team exemption; (2) Medium severity - warn but don't block, fix within 7 days; (3) Low severity - log only, fix in next version
- **FR-043**: System MUST follow a planned upgrade process for external dependencies: (1) test in staging, (2) schedule during low-traffic windows, (3) monitor for 24 hours post-upgrade.

**Architecture Constraints**:
- **FR-044**: System MUST implement a modular monolith architecture using a single FastAPI application.
- **FR-045**: PPT coaching (`presentation_coach/`) and sales bot (`sales_bot/`) modules MUST be isolated through Python package boundaries with no direct cross-module imports.
- **FR-046**: Shared functionality MUST be placed in `common/` package and accessed through dependency injection.
  - **Implementation**: Use FastAPI `Depends()` for all service injections, compile-time checks for module boundary violations
- **FR-047**: System MUST support future extraction of modules into microservices without extensive refactoring (clear interfaces, minimal coupling).
- **FR-063**: System MUST adapt to enterprise network environments (firewalls, proxies).
  - **Enterprise Network Support**: WSS (WebSocket over TLS) on port 443, HTTP proxy auto-discovery (WPAD), internal deployment option for air-gapped environments
- **FR-066**: System MUST control distributed tracing performance overhead.
  - **Sampling Strategy**: Normal mode 10%, high-load 1%, debug mode 100%
  - **Async Reporting**: Batch upload every 10s or 100 records, non-blocking
  - **Performance Budget**: <5% overhead, <1ms per trace point

---

### Key Entities

**User (用户)**:
- Represents an employee who uses the practice system
- Attributes: user_id, name, department, email (from enterprise WeChat), created_at
- Relationships: has many PracticeSessions, appears on Leaderboard

**Presentation (演示文稿)**:
- Represents a PPT file uploaded for practice
- Attributes: presentation_id, title, file_url, upload_date, version_number, status (processing/ready/failed), uploaded_by_admin_id
- Relationships: has many Pages, has many RequiredTalkingPoints, has many ForbiddenWords, has many PracticeSessions

**Page (页面)**:
- Represents a single page within a presentation
- Attributes: page_id, presentation_id, page_number, ocr_extracted_text, image_url
- Relationships: belongs to Presentation, has many RequiredTalkingPoints

**RequiredTalkingPoint (必讲点)**:
- Represents a key point that must be mentioned during a specific page
- Attributes: point_id, page_id, description, created_by (admin or AI), is_ai_generated, confirmed_by_admin
- Relationships: belongs to Page

**ForbiddenWord (禁忌词)**:
- Represents a word or phrase that should not be used during presentation
- Attributes: word_id, scope (global/page), presentation_id (required for global), page_id (required for page-specific), phrase, suggested_alternative
- Relationships: belongs to Presentation (global scope) or Page (page-specific scope)
- Design note: Two-level scope supports global presentation-level prohibitions (e.g., "I don't know", "maybe") and page-specific restrictions (e.g., "cheap" forbidden on product pages but allowed on technical pages)

**Scenario (演练场景)**:
- Represents a practice scenario type (PPT coaching or sales bot)
- Attributes: scenario_id, scenario_type (presentation/sales), name, description, persona_prompt (for sales bot)
- Relationships: has many PracticeSessions

**PracticeSession (演练会话)**:
- Represents a single practice session
- Attributes: session_id, user_id, presentation_id (for presentation coaching) or scenario_id (for sales bot), start_time, end_time, status (preparing/in_progress/paused/completed/scoring), logic_score, accuracy_score, completeness_score, audio_url, transcript_url
- Relationships: belongs to User, belongs to Presentation or Scenario, has many InterruptionEvents

**InterruptionEvent (打断事件)**:
- Represents an instance where the AI interrupted the user
- Attributes: event_id, session_id, timestamp, interruption_type (forbidden_word/missing_point/vague_response), trigger_content, ai_response, user_response_after_interruption
- Relationships: belongs to PracticeSession

**LeaderboardEntry (排行榜条目)**:
- Represents a user's ranking position
- Attributes: entry_id, user_id, scenario_type, average_score, total_sessions, rank, last_updated
- Relationships: belongs to User

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

**Real-time Performance**:
- **SC-001**: End-to-end response latency (from when user stops speaking to when AI response begins) is <300ms for 95% of interactions.
- **SC-002**: Interruption detection (AI detecting need to interrupt) occurs within 100ms of trigger event (forbidden word spoken, page completed without required points).
- **SC-003**: System supports 50 concurrent practice sessions without any degradation in latency or performance.

**User Experience**:
- **SC-004**: Users can complete a full 20-minute presentation practice session without experiencing any visible error popups or disruptive technical issues.
- **SC-005**: Practice session completion rate is >85% (users who start a session successfully finish it).
- **SC-006**: User satisfaction score (measured via post-session survey) is >4.0/5.0 for interaction naturalness.

**Business Value**:
- **SC-007**: Operational cost per practice session is <¥1 (including all ASR, TTS, and LLM API costs).
- **SC-008**: Time from PPT upload to ready-for-practice is <5 minutes for a 20-page presentation.
- **SC-009**: Score report generation completes within 10 seconds of session end.

**Quality & Reliability**:
- **SC-010**: System uptime is >99% during business hours (9 AM - 6 PM, Monday-Friday).
- **SC-011**: Audio transcription accuracy (word error rate) is <15% for clear speech.
- **SC-012**: Vector database search returns relevant results for >90% of page-specific queries.
- **SC-016**: Error rate monitoring must track failed requests (HTTP >=500, WebSocket failure, ASR/TTS timeout, LLM failure) with rolling 5-minute windows, categorized by scenario and error type, with alert thresholds at 1%/5%/10%.

**Adoption & Engagement**:
- **SC-013**: Within 3 months of launch, >50% of target users have completed at least one practice session.
- **SC-014**: Users who practice at least 3 times show measurable score improvement (>10% increase in average scores).
- **SC-015**: Average session duration is >15 minutes, indicating meaningful engagement (not just quick testing).
