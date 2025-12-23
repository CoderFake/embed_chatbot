# Visitor Grader - Lead Scoring System

AI-powered lead scoring system that analyzes visitor chat conversations to determine sales potential.

## Architecture

```
Backend → RabbitMQ → Visitor Grader → LLM Scoring → Webhook → Backend → Email Notification
```

### Flow:
1. **Backend** publishes grading task when session closes
2. **Visitor Grader** consumes task from RabbitMQ
3. **LLM** analyzes conversation and assigns score (0-100)
4. **Webhook** sends result back to backend
5. **Backend** saves score and sends email to bot owner

## Features

- ✅ **Multi-LLM Support**: OpenAI, Gemini, Ollama
- ✅ **Clean Architecture**: Router → Service → Repository pattern
- ✅ **Lead Scoring**: HOT (70+), WARM (40-69), COLD (0-39)
- ✅ **Intent Detection**: Purchase signals, engagement level
- ✅ **Actionable Insights**: Key interests, recommended actions
- ✅ **Webhook Integration**: HMAC-signed payloads with retry logic
- ✅ **Read-only**: No direct database access, gets data from backend

## Scoring Criteria

### Purchase Intent (0-50 points)
- Asked about pricing/plans: +15
- Requested demo/trial: +15  
- Enterprise features: +10
- Implementation timeline: +10
- Mentioned budget: +10

### Engagement Level (0-25 points)
- High (5+ messages): +25
- Medium (3-4 messages): +15
- Low (1-2 messages): +5

### Qualification (0-25 points)
- Company info: +10
- Integration questions: +8
- Specific use cases: +7
- Technical understanding: +5

## Installation

```bash
cd visitor-grader
pip install -r requirements.txt
```

## Configuration

Copy `.env.example` to `.env` and configure:

```bash
# Choose LLM provider
LLM_PROVIDER=openai  # or gemini, ollama

# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

# Backend webhook
BACKEND_WEBHOOK_URL=http://backend:8000/api/v1/webhooks/visitor-grading
BACKEND_WEBHOOK_SECRET=your-secret-key
```

## Run

### Local
```bash
python -m app
```

### Docker
```bash
docker build -t visitor-grader .
docker run --env-file .env visitor-grader
```

### Docker Compose
```bash
docker-compose up visitor-grader
```

## Project Structure

```
visitor-grader/
├── app/
│   ├── __init__.py
│   ├── __main__.py           # Entry point
│   ├── main.py               # Application loop
│   ├── config/
│   │   └── settings.py       # Configuration
│   ├── core/
│   │   ├── llm_client.py     # LLM integrations
│   │   ├── prompt_loader.py  # Prompt management
│   │   └── webhook_client.py # Backend communication
│   ├── services/
│   │   ├── scoring.py        # Business logic
│   │   └── queue_consumer.py # RabbitMQ consumer
│   ├── schemas/
│   │   └── grading.py        # Pydantic models
│   └── utils/
│       └── logger.py         # Logging
├── static/
│   └── prompts/
│       └── lead_scoring.yaml # Scoring prompt
├── Dockerfile
├── requirements.txt
└── .env.example
```

## Backend Integration

### 1. Webhook Endpoint

Backend must implement: `POST /api/v1/webhooks/visitor-grading`

```python
@router.post("/webhooks/visitor-grading", include_in_schema=False)
async def handle_visitor_grading(
    request: Request,
    payload: VisitorGradingWebhook,
    db: AsyncSession = Depends(get_db)
):
    # Verify HMAC signature
    signature = request.headers.get("X-Webhook-Signature")
    verify_webhook_signature(await request.body(), signature)
    
    # Update visitor record
    visitor_service = VisitorService(db)
    await visitor_service.update_lead_score(
        visitor_id=payload.visitor_id,
        lead_score=payload.lead_score,
        lead_category=payload.lead_category,
        scoring_data={
            "intent_signals": payload.intent_signals,
            "engagement_level": payload.engagement_level,
            "key_interests": payload.key_interests,
            "recommended_actions": payload.recommended_actions,
            "reasoning": payload.reasoning,
            "graded_at": payload.graded_at,
            "model_used": payload.model_used
        }
    )
    
    # Send email notification if HOT lead
    if payload.lead_category == "hot":
        await send_hot_lead_notification(
            bot_id=payload.bot_id,
            visitor_id=payload.visitor_id,
            score=payload.lead_score,
            insights=payload
        )
    
    return {"status": "success"}
```

### 2. Schema

```python
class VisitorGradingWebhook(BaseModel):
    task_id: str
    visitor_id: str
    bot_id: str
    session_id: str
    lead_score: int
    lead_category: str
    intent_signals: List[str]
    engagement_level: str
    key_interests: List[str]
    recommended_actions: List[str]
    reasoning: str
    graded_at: datetime
    model_used: str
    conversation_count: int
```

### 3. Email Notification

```python
async def send_hot_lead_notification(
    bot_id: str,
    visitor_id: str,
    score: int,
    insights: VisitorGradingWebhook
):
    # Get bot owner email
    bot = await bot_service.get_by_id(bot_id)
    owner_email = bot.user.email
    
    # Send email
    await send_email(
        to=owner_email,
        subject=f"🔥 Hot Lead Detected - Score: {score}/100",
        template="hot_lead_notification",
        data={
            "score": score,
            "category": insights.lead_category,
            "intent_signals": insights.intent_signals,
            "key_interests": insights.key_interests,
            "recommended_actions": insights.recommended_actions,
            "reasoning": insights.reasoning,
            "visitor_profile_url": f"{FRONTEND_URL}/dashboard/visitors/{visitor_id}"
        }
    )
```

## Monitoring

Logs are in JSON format for easy parsing:

```json
{
  "timestamp": "2024-01-01T10:00:00Z",
  "level": "INFO",
  "logger": "app.services.scoring",
  "message": "Visitor scored successfully",
  "task_id": "task_123",
  "visitor_id": "visitor_456",
  "score": 85,
  "category": "hot"
}
```

## Performance

- Concurrent tasks: Configurable via `MAX_CONCURRENT_TASKS`
- LLM timeout: 30s default
- Webhook retries: 3 attempts with exponential backoff
- Memory: ~100MB per worker

## Security

- ✅ HMAC webhook signatures
- ✅ No database credentials needed
- ✅ Read-only access to data
- ✅ Isolated service

## Testing

```python
# Test scoring
task = GradingTaskPayload(
    task_id="test_123",
    visitor_id="visitor_123",
    bot_id="bot_123",
    session_id="session_123",
    conversation_history=[
        {"role": "user", "content": "What's your pricing?"},
        {"role": "assistant", "content": "We have 3 plans..."}
    ],
    visitor_profile={"total_sessions": 2}
)

result = await scoring_service.score_visitor(task)
print(f"Score: {result.score}, Category: {result.category}")
```
