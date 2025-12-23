# Chatbot Embed Platform - Architecture

Kiến trúc tổng quan của hệ thống Chatbot Embed Platform với microservices, RAG pipeline, và visitor lead scoring.

---

## 🏗️ Tổng quan kiến trúc

### System Architecture Diagram

### High-Level Overview

```mermaid
flowchart LR
    Client[👤 Client<br/>Browser/Widget] <--> Backend[🚀 Backend API<br/>FastAPI]
    Backend <--> Workers[⚙️ Workers<br/>Chat/File/Grader]
    
    Backend <--> Storage[(💾 Storage<br/>PostgreSQL<br/>Redis<br/>MinIO)]
    Workers --> Storage
    Workers --> AI[🤖 AI Services<br/>Milvus Vector DB<br/>LLM Providers]
    
    style Client fill:#e3f2fd
    style Backend fill:#4a90e2,color:#fff
    style Workers fill:#7cb342,color:#fff
    style Storage fill:#336791,color:#fff
    style AI fill:#ab47bc,color:#fff
```

### Detailed Architecture

```mermaid
graph LR
    subgraph Client["Client Layer"]
        Widget[Chat Widget]
        Admin[Admin Dashboard]
    end
    
    subgraph Backend["Backend API"]
        API[FastAPI Server]
    end
    
    subgraph Workers["Processing Workers"]
        Chat[Chat Worker<br/>RAG Pipeline]
        File[File Server<br/>Doc Processing]
        Grader[Visitor Grader<br/>Lead Scoring]
    end
    
    subgraph Infra["Infrastructure"]
        DB[(PostgreSQL)]
        Cache[(Redis)]
        Queue[RabbitMQ]
        S3[(MinIO)]
    end
    
    subgraph AI["AI Services"]
        Vector[(Milvus<br/>Vector DB)]
        LLM[LLM APIs<br/>OpenAI/Gemini]
        Crawler[Crawl4AI]
    end
    
    Widget <--> API
    Admin --> API
    
    API <--> DB
    API <--> Cache
    API --> Queue
    API <--> S3
    
    Chat --> Queue
    File --> Queue
    Grader --> Queue
    
    Chat -.webhook.-> API
    File -.webhook.-> API
    Grader -.webhook.-> API
    
    Chat <--> Vector
    Chat <--> LLM
    File <--> Vector
    File <--> Crawler
    Grader <--> Vector
    Grader <--> LLM
    
    Workers <--> DB
    Workers <--> Cache
    File <--> S3
    
    style API fill:#4a90e2,color:#fff
    style Chat fill:#7cb342,color:#fff
    style File fill:#fb8c00,color:#fff
    style Grader fill:#ab47bc,color:#fff
    style Vector fill:#00c7b7,color:#fff
```

---

## 🔧 Core Components

### 1. Backend API (FastAPI)

**Chức năng chính:**
- RESTful API endpoints
- Authentication & authorization (JWT)
- Bot configuration management
- User & organization management
- Widget token generation
- Webhook handling
- Real-time streaming via SSE

**Tech Stack:**
- FastAPI (async)
- SQLAlchemy ORM
- Pydantic validation
- Alembic migrations

**Endpoints:**
- `/api/v1/auth` - Authentication
- `/api/v1/bots` - Bot management
- `/api/v1/documents` - Document upload
- `/api/v1/chat` - Chat gateway
- `/api/v1/widget` - Widget API
- `/api/v1/admin` - Admin operations
- `/api/v1/webhooks` - Service webhooks

---

### 2. Chat Worker (RAG Pipeline)

**Chức năng chính:**
- Process chat messages via RabbitMQ
- LangGraph-based conversational AI
- RAG (Retrieval Augmented Generation)
- Two-stage adaptive retrieval
- Long-term memory management
- Token streaming via Redis Pub/Sub

**Architecture:**

```mermaid
graph LR
    subgraph "Chat Worker"
        Queue[RabbitMQ Queue]
        Graph[LangGraph Engine]
        
        subgraph "Nodes"
            Reflection[Reflection Node]
            Chitchat[Chitchat Node]
            Retrieve[Retrieve Node]
            Generate[Generate Node]
            Memory[Memory Node]
        end
        
        Embedding[BGE-M3 Embedder]
        Reranker[Cross-Encoder Reranker]
    end
    
    Queue --> Graph
    Graph --> Reflection
    Reflection -->|Chitchat| Chitchat
    Reflection -->|Question| Retrieve
    Retrieve --> Embedding
    Embedding --> Milvus
    Milvus --> Reranker
    Reranker --> Generate
    Generate --> Memory
    Chitchat --> Memory
    Generate --> LLM
    
    style Graph fill:#7cb342
    style Retrieve fill:#fb8c00
    style Generate fill:#42a5f5
```

---

### 3. File Server (Document Processing)

**Chức năng chính:**
- Document chunking & embedding
- Web crawling với Crawl4AI
- Upload to MinIO
- Vector storage in Milvus
- Progress tracking via Redis
- Webhook notifications

**Processing Pipeline:**

```mermaid
flowchart TD
    Start[File Upload/Crawl Request] --> Queue[RabbitMQ Queue]
    Queue --> Worker[File Server Worker]
    
    Worker --> Type{Type?}
    
    Type -->|File| Download[Download from MinIO]
    Type -->|URL| Crawl[Crawl4AI Scraper]
    
    Download --> Extract[Text Extraction]
    Crawl --> Extract
    
    Extract --> Chunk[Text Chunking<br/>512 tokens, 128 overlap]
    Chunk --> Embed[BGE-M3 Embedding<br/>512 dimensions]
    
    Embed --> Batch[Batch Processing<br/>1000 chunks/batch]
    Batch --> Milvus[(Milvus Vector Store)]
    
    Milvus --> Metadata[(PostgreSQL Metadata)]
    Metadata --> Webhook[Webhook to Backend]
    Webhook --> Complete[Mark Complete]
    
    Worker --> Progress[Update Progress<br/>via Redis]
    Progress --> SSE[SSE to Frontend]
    
    style Worker fill:#fb8c00
    style Embed fill:#00c7b7
    style Milvus fill:#00c7b7
```

---

### 4. Visitor Grader (Lead Scoring)

**Chức năng chính:**
- Analyze visitor chat history
- RAG-based lead qualification
- Score: Hot (70+), Warm (40-69), Cold (0-39)
- Email notifications to sales team
- Async processing via RabbitMQ

**Scoring Flow:**

```mermaid
flowchart TD
    Trigger[Visitor provides contact info] --> Backend[Backend creates grading task]
    Backend --> Queue[RabbitMQ Queue]
    
    Queue --> Grader[Visitor Grader]
    Grader --> Retrieve[Retrieve relevant<br/>product/service docs]
    
    Retrieve --> Milvus[(Milvus)]
    Milvus --> Rerank[Rerank top chunks]
    
    Rerank --> Analyze[LLM Analysis<br/>Intent, Budget, Timeline]
    
    Analyze --> Score{Score}
    
    Score -->|70+| Hot[🔥 Hot Lead]
    Score -->|40-69| Warm[🌡️ Warm Lead]
    Score -->|0-39| Cold[❄️ Cold Lead]
    
    Hot --> Email[Email Sales Team]
    Warm --> Email
    Cold --> Log[Log to DB]
    
    Email --> Webhook[Webhook to Backend]
    Log --> Webhook
    Webhook --> Update[(Update Visitor)]
    
    style Grader fill:#ab47bc
    style Hot fill:#ff5722
    style Warm fill:#ff9800
    style Cold fill:#03a9f4
```

---

## 💾 Data Layer

### Database Schema

```mermaid
erDiagram
    USERS ||--o{ BOTS : creates
    USERS ||--o{ INVITES : sends
    USERS {
        uuid id PK
        string email UK
        string name
        string password_hash
        enum role
        boolean is_active
        timestamp created_at
    }
    
    BOTS ||--o{ DOCUMENTS : contains
    BOTS ||--o{ CHAT_SESSIONS : has
    BOTS ||--o{ VISITORS : interacts_with
    BOTS {
        uuid id PK
        uuid owner_id FK
        string name
        string description
        string system_prompt
        json config
        timestamp created_at
    }
    
    DOCUMENTS ||--o{ CHUNKS : split_into
    DOCUMENTS {
        uuid id PK
        uuid bot_id FK
        string filename
        enum type
        string s3_key
        int chunk_count
        enum status
        timestamp created_at
    }
    
    CHAT_SESSIONS ||--o{ CHAT_MESSAGES : contains
    CHAT_SESSIONS {
        uuid id PK
        uuid bot_id FK
        uuid visitor_id FK
        string session_id UK
        timestamp created_at
    }
    
    CHAT_MESSAGES {
        uuid id PK
        uuid session_id FK
        enum role
        text content
        json metadata
        boolean is_contact
        timestamp created_at
    }
    
    VISITORS {
        uuid id PK
        uuid bot_id FK
        string name
        string email
        string phone
        enum lead_grade
        json grading_result
        timestamp created_at
    }
    
    PROVIDERS ||--o{ PROVIDER_KEYS : has
    PROVIDERS {
        uuid id PK
        string name
        enum type
        json config
        boolean is_active
    }
    
    PROVIDER_KEYS ||--o{ MODELS : supports
    PROVIDER_KEYS {
        uuid id PK
        uuid provider_id FK
        string encrypted_key
        int priority
        boolean is_active
    }
```

### Milvus Collections

```mermaid
graph TD
    subgraph "Milvus Vector Store"
        Collection[Collection: chatbot_documents]
        
        subgraph "Fields"
            ID[id: VARCHAR PK]
            BotID[bot_id: VARCHAR]
            DocID[document_id: VARCHAR]
            ChunkID[chunk_id: VARCHAR]
            Content[content: VARCHAR]
            Vector[embedding: FLOAT_VECTOR<br/>512 dims]
            Meta[metadata: JSON]
        end
        
        Collection --> ID
        Collection --> BotID
        Collection --> DocID
        Collection --> ChunkID
        Collection --> Content
        Collection --> Vector
        Collection --> Meta
    end
    
    Index[IVF_FLAT Index<br/>nlist=1024<br/>metric=IP]
    Vector --> Index
    
    style Collection fill:#00c7b7
    style Vector fill:#ff9800
    style Index fill:#4caf50
```

---

## 🔄 Key Workflows

### Chat Conversation Flow

Xem chi tiết: [chat_conversation_flow.md](../backend/docs/chat_conversation_flow.md)

**Tóm tắt:**
1. Widget gửi message → Backend API
2. Backend tạo task → RabbitMQ queue
3. Chat Worker xử lý qua LangGraph:
   - **Reflection**: Phân tích intent, ngôn ngữ
   - **Retrieve**: 2-stage adaptive retrieval + reranking
   - **Generate**: LLM với context từ RAG
   - **Memory**: Update long-term memory
4. Stream tokens qua Redis Pub/Sub → Widget via SSE
5. Save to PostgreSQL
6. Nếu có contact info → trigger Visitor Grader

---

### Document Processing Flow

```mermaid
sequenceDiagram
    participant User
    participant Backend
    participant MinIO
    participant RabbitMQ
    participant FileServer
    participant Milvus
    participant WebSocket
    
    User->>Backend: Upload file
    Backend->>MinIO: Store file
    MinIO-->>Backend: S3 key
    Backend->>RabbitMQ: Publish task
    Backend->>User: Return task_id
    
    RabbitMQ->>FileServer: Consume task
    FileServer->>MinIO: Download file
    
    loop Chunks
        FileServer->>FileServer: Extract & chunk text
        FileServer->>FileServer: Generate embeddings
    end
    
    FileServer->>Milvus: Batch insert vectors
    FileServer->>Backend: Webhook: progress update
    Backend->>WebSocket: Push to frontend
    
    FileServer->>Backend: Webhook: completed
    Backend->>User: Notification
```

---

### Lead Scoring Flow

Xem chi tiết: [visitor_assessment_flow.md](../backend/docs/visitor_assessment_flow.md)

**Trigger:**
- User provides contact info trong chat
- Backend tạo visitor record
- Enqueue grading task to RabbitMQ

**Process:**
1. Visitor Grader retrieves chat history
2. RAG retrieval từ bot's documents
3. LLM analyzes:
   - Purchase intent
   - Budget signals
   - Timeline urgency
   - Fit score
4. Calculate final score → assign grade
5. Email sales team với insights
6. Webhook update to Backend

---

## 🔐 Security Architecture

### Authentication Flow

```mermaid
sequenceDiagram
    participant Client
    participant Backend
    participant Redis
    participant DB
    
    Client->>Backend: POST /auth/login<br/>(email, password)
    Backend->>DB: Verify credentials
    DB-->>Backend: User data
    Backend->>Backend: Generate JWT tokens<br/>(access + refresh)
    Backend->>Redis: Store refresh token
    Backend-->>Client: Return tokens + user info
    
    Note over Client,Backend: Subsequent requests
    
    Client->>Backend: API request<br/>(Authorization: Bearer {access_token})
    Backend->>Backend: Verify JWT signature
    Backend->>Redis: Check if blacklisted
    Backend-->>Client: Protected resource
    
    Note over Client,Backend: Token refresh
    
    Client->>Backend: POST /auth/refresh<br/>(refresh_token)
    Backend->>Redis: Verify refresh token
    Backend->>Backend: Generate new access token
    Backend-->>Client: New access token
```

### Widget Token Flow

```mermaid
flowchart LR
    Admin[Admin Dashboard] -->|Configure bot| Backend[Backend API]
    Backend -->|Generate widget token<br/>JWT: bot_id + domain| Token[Widget Token]
    
    Token -->|Embed in website| Website[Client Website]
    Website -->|Load widget.js<br/>with token| Widget[Chat Widget]
    
    Widget -->|Verify token<br/>Check allowed origins| Backend
    Backend -->|Valid| Session[Create session]
    Backend -->|Invalid| Reject[Reject request]
    
    Session -->|Chat messages| ChatAPI[Chat API]
    
    style Token fill:#ffc107
    style Widget fill:#4caf50
    style Reject fill:#f44336
```

---

## 📊 Scalability & Performance

### Caching Strategy

```mermaid
graph TB
    Request[API Request]
    
    Request --> Cache{Redis Cache?}
    Cache -->|Hit| Return[Return cached data]
    Cache -->|Miss| DB[(Database)]
    
    DB --> Save[Save to cache<br/>with TTL]
    Save --> Return
    
    subgraph "Cache Keys"
        BotConfig["bot:config:{bot_id}<br/>TTL: 3600s"]
        UserData["user:{user_id}<br/>TTL: 3600s"]
        Documents["bot:documents:{bot_id}<br/>TTL: 1800s"]
        Analytics["analytics:{bot_id}:{period}<br/>TTL: 300s"]
    end
    
    style Cache fill:#dc382d
    style Return fill:#4caf50
```

### Rate Limiting

```mermaid
flowchart TD
    Request[Incoming Request]
    
    Request --> Check{Rate Limit Check}
    
    Check -->|Within limit| Process[Process Request]
    Check -->|Exceeded| Block[Return 429<br/>Too Many Requests]
    
    Process --> Increment[Increment counter<br/>in Redis]
    Increment --> Response[Send Response]
    
    subgraph "Limits"
        API["API: 60 req/min per user"]
        Widget["Widget: 20 req/min per IP"]
        Global["Global: 100 req/min per IP"]
    end
    
    style Check fill:#ff9800
    style Block fill:#f44336
    style Process fill:#4caf50
```

---

## 🚀 Deployment Architecture

### Docker Compose Services

```mermaid
graph TB
    subgraph "Infrastructure"
        Postgres[PostgreSQL:15432]
        Redis[Redis:16379]
        RabbitMQ[RabbitMQ:5672<br/>Management:15672]
        MinIO[MinIO:9000<br/>Console:9001]
        Etcd[Etcd:2379]
        Milvus[Milvus:19532]
        Crawl4AI[Crawl4AI:11235]
    end
    
    subgraph "Application Services"
        Backend[Backend API:18000]
        ChatWorker[Chat Worker]
        FileServer[File Server]
        VisitorGrader[Visitor Grader]
    end
    
    Backend --> Postgres
    Backend --> Redis
    Backend --> RabbitMQ
    Backend --> MinIO
    
    ChatWorker --> Postgres
    ChatWorker --> Redis
    ChatWorker --> RabbitMQ
    ChatWorker --> Milvus
    
    FileServer --> MinIO
    FileServer --> Milvus
    FileServer --> RabbitMQ
    FileServer --> Crawl4AI
    
    VisitorGrader --> Postgres
    VisitorGrader --> Redis
    VisitorGrader --> RabbitMQ
    VisitorGrader --> Milvus
    
    Milvus --> Etcd
    Milvus --> MinIO
    
    style Backend fill:#4a90e2
    style ChatWorker fill:#7cb342
    style FileServer fill:#fb8c00
    style VisitorGrader fill:#ab47bc
```

### Environment Modes

| Mode | Workers | Reload | Docs | Logs | Use Case |
|------|---------|--------|------|------|----------|
| **dev** | 1 (Uvicorn) | ✅ | 🔓 Open | Debug | Local development |
| **stg** | 2 (Gunicorn) | ✅ | 🔒 Auth | Debug | Staging/Testing |
| **prod** | 4 (Gunicorn) | ❌ | 🔒 Auth | Info | Production |

---

## 🔍 Monitoring & Observability

### Key Metrics

**Performance:**
- API response time (p50, p95, p99)
- Chat latency breakdown (reflection, retrieval, generation)
- Document processing throughput
- Vector search latency

**Business:**
- Active bots count
- Messages per day/bot
- Document chunks indexed
- Visitor grading completion rate
- Hot/Warm/Cold lead distribution

**System:**
- CPU & memory usage
- Database connections
- Redis cache hit rate
- RabbitMQ queue depth
- Milvus vector count

### Health Checks

```mermaid
graph LR
    subgraph "Health Endpoints"
        Backend[Backend: /health]
        ChatWorker[Chat Worker: RabbitMQ consumer]
        FileServer[File Server: RabbitMQ consumer]
        VisitorGrader[Visitor Grader: RabbitMQ consumer]
    end
    
    Backend --> Postgres
    Backend --> Redis
    Backend --> MinIO
    Backend --> RabbitMQ
    
    ChatWorker --> Milvus
    FileServer --> Crawl4AI
    
    style Backend fill:#4caf50
    style ChatWorker fill:#4caf50
    style FileServer fill:#4caf50
    style VisitorGrader fill:#4caf50
```

---

## 📁 Directory Structure

```
embed_chatbot/
├── backend/                    # FastAPI backend
│   ├── app/
│   │   ├── api/v1/            # API endpoints
│   │   ├── models/            # SQLAlchemy models
│   │   ├── schemas/           # Pydantic schemas
│   │   ├── services/          # Business logic
│   │   ├── core/              # Config & settings
│   │   ├── cache/             # Redis cache
│   │   └── utils/             # Helpers
│   ├── alembic/               # DB migrations
│   └── docs/                  # Documentation
│
├── chat-worker/               # RAG pipeline
│   ├── app/
│   │   ├── graph/             # LangGraph nodes
│   │   ├── services/          # Retrieval, LLM
│   │   └── models/            # Data models
│
├── file-server/               # Document processor
│   ├── app/
│   │   ├── services/          # Chunking, embedding
│   │   └── workers/           # RabbitMQ workers
│
├── visitor-grader/            # Lead scorer
│   ├── app/
│   │   ├── services/          # Grading logic
│   │   └── workers/           # RabbitMQ workers
│
├── frontend/                  # Admin dashboard (Next.js)
│   └── src/
│       ├── components/
│       ├── pages/
│       └── services/
│
└── docker-compose.yml         # Service orchestration
```

---

## 🔗 Related Documentation

- [Chat Conversation Flow](../backend/docs/chat_conversation_flow.md) - RAG pipeline chi tiết
- [Bot Creation Flow](../backend/docs/bot_creation_flow.md) - Quy trình tạo bot
- [Visitor Assessment Flow](../backend/docs/visitor_assessment_flow.md) - Lead scoring
- [README.md](../README.md) - Quick start guide

---

## 🛠️ Technology Stack Summary

| Layer | Technologies |
|-------|-------------|
| **Backend** | FastAPI, SQLAlchemy, Pydantic, Alembic |
| **AI/ML** | LangGraph, BGE-M3, Cross-Encoder Reranker |
| **Database** | PostgreSQL, Milvus (vector DB) |
| **Cache** | Redis (cache + pub/sub) |
| **Queue** | RabbitMQ |
| **Storage** | MinIO (S3-compatible) |
| **Crawler** | Crawl4AI |
| **Frontend** | Next.js, React, TailwindCSS |
| **Deployment** | Docker, Docker Compose |
| **LLM Providers** | OpenAI, Google Gemini, Anthropic Claude |

---

**Last Updated:** 2025-12-23
