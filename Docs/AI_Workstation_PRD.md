# Campus AI Work Station

## Product Requirements Document (PRD)

### Version 1.0 --- Scope Freeze

> **Project status:** Architecture / implementation planning\
> **Primary goal:** Build a private, zero-inference-cost, remotely
> accessible campus AI coding service powered by a local RTX 5060 Ti 16
> GB workstation.\
> **Deployment target:** Windows 11 + WSL2 + Docker\
> **Initial authorized users:** up to 50\
> **Typical simultaneous users:** \~12 or fewer\
> **Maximum active inference jobs:** 3\
> **Primary workload:** Agentic software development

------------------------------------------------------------------------

# Page 01 --- Executive Summary

## 1.1 Product

**Campus AI Work Station** is a self-hosted AI inference platform
operated from a lab workstation. The workstation provides local LLM
inference to a controlled group of students and developers without
relying on commercial inference APIs such as Claude, OpenAI, or Gemini
for the actual model execution.

The system is intentionally designed as an **AI infrastructure
service**, not merely a chatbot.

A user should be able to configure an IDE or coding agent against the
service and perform workflows such as:

> "Build X, run the tests, fix the errors, and keep going until the
> implementation is complete."

The coding agent remains on the user's development machine. The
workstation provides the expensive model inference.

## 1.2 Core architecture

``` text
User Laptop
├── VS Code / IDE
├── Cline / Roo / Continue / Aider / OpenHands / etc.
├── Repository
├── Terminal
├── Compiler
└── Tests
        │
        │ OpenAI-compatible API
        ▼
Secure Internet / Tunnel
        │
        ▼
AI Gateway
├── Authentication
├── API keys
├── Queue
├── Priority scheduler
├── Usage telemetry
└── Mode policy
        │
        ▼
Inference Runtime
└── vLLM
        │
        ▼
RTX 5060 Ti 16 GB
```

vLLM is appropriate as the initial inference layer because it exposes
OpenAI-compatible HTTP APIs, including chat completions and the
Responses API, and can be deployed through Docker.

## 1.3 Design principles

1.  **API first.**
2.  **Agent first, chatbot second.**
3.  **Private by default.**
4.  **No direct exposure of the inference runtime.**
5.  **No artificial daily token quota.**
6.  **Three active inference jobs maximum initially.**
7.  **Queue rather than reject ordinary contention.**
8.  **Configurable priorities from the beginning.**
9.  **Models are replaceable.**
10. **Transport is replaceable.**
11. **Student repositories remain on student machines.**
12. **Everything practical is Dockerized.**
13. **Do not over-engineer for hypothetical scale.**
14. **Use real measurements to tune GPU behavior.**

------------------------------------------------------------------------

# Page 02 --- Problem Statement and Motivation

## 2.1 Problem

Students increasingly use AI coding agents, but commercial inference
services impose recurring costs, usage limits, rate limits, privacy
concerns, or dependence on third-party infrastructure.

A lab workstation with a capable NVIDIA GPU can instead become a shared
inference resource.

The problem is not simply:

> "How do we run an LLM?"

The actual problem is:

> "How do we turn one workstation into a controlled, remotely
> accessible, multi-user inference service that coding agents can use
> reliably without compromising the workstation's own development
> workload?"

## 2.2 Intended outcome

The final system should allow:

-   selected students to obtain accounts;
-   IDEs and coding agents to connect through a standard API;
-   multiple models to be available;
-   requests to stream responses;
-   up to three inference jobs to execute concurrently;
-   additional requests to wait in a queue;
-   users to consume the service without a token subscription;
-   administrators to control access and priorities;
-   the workstation owner to switch operating modes;
-   Game Dev Mode to preserve GPU resources for Unity/Unreal/game
    workloads;
-   usage data to power analytics and a leaderboard.

## 2.3 Non-goals for V1

The following are explicitly not required initially:

-   Kubernetes;
-   distributed inference;
-   multiple GPUs;
-   public model training;
-   student repository hosting;
-   remote code execution on the AI server;
-   a full ChatGPT clone;
-   automatic university-wide account provisioning;
-   commercial billing;
-   per-user monthly token subscriptions;
-   complex RAG infrastructure;
-   autonomous server-side coding agents.

These may become future extensions, but they are not allowed to inflate
V1.

------------------------------------------------------------------------

# Page 03 --- Hardware and Host Environment

## 3.1 Confirmed hardware

  -----------------------------------------------------------------------
  Component                           Specification
  ----------------------------------- -----------------------------------
  GPU                                 NVIDIA GeForce RTX 5060 Ti

  VRAM                                16,311 MiB reported

  CPU                                 AMD Ryzen 7 8745HX

  CPU                                 8 cores / 16 logical processors

  RAM                                 64 GB DDR5, 2 × 32 GB

  Storage                             Not currently a constraint

  Host OS                             Windows 11

  Network                             University Wi-Fi

  Availability                        Intended 24/7 operation, subject to
                                      power/network availability
  -----------------------------------------------------------------------

The exact GPU output was verified with `nvidia-smi`. The project
specification should use **RTX 5060 Ti 16 GB** rather than the
previously used informal "5060 Ti Super" label.

## 3.2 Host architecture

The selected deployment architecture is:

``` text
Windows 11
    │
    └── WSL2
          │
          └── Linux distribution
                │
                └── Docker
                      │
                      ├── Gateway
                      ├── Scheduler
                      ├── Inference
                      ├── Database
                      └── Monitoring
```

NVIDIA documents GPU acceleration for CUDA workloads under WSL2, and the
NVIDIA Container Toolkit provides the runtime components required for
GPU-accelerated containers.

## 3.3 Resource constraint

The primary resource constraint is **16 GB VRAM**, not RAM or storage.

Therefore the platform must treat VRAM as a first-class scheduling
resource.

The platform must not assume that a model which technically fits into 16
GB will remain safe while the workstation is also running a game engine.

------------------------------------------------------------------------

# Page 04 --- User Model and Access Control

## 4.1 User capacity

Initial scope:

``` text
Maximum registered accounts: 50
Expected typical users:      ~12
Maximum active inference:     3
```

The 50-user figure is a deliberate V1 boundary. It aligns with the
selected free access strategy and avoids prematurely building a large
identity platform.

## 4.2 Manual provisioning

Users are manually created by the project administrators.

There is no open registration.

``` text
Admin
  │
  ├── Create account
  ├── Assign role
  ├── Generate API credential
  ├── Enable / disable
  └── Revoke access
```

## 4.3 Authentication

The gateway must support:

-   individual user identities;
-   password authentication for administrative/user portal functions if
    introduced;
-   API keys for developer clients;
-   credential revocation;
-   disabled-account enforcement;
-   secure password hashing;
-   hashed API-key storage rather than plaintext key storage.

## 4.4 Authorization

Authorization is separate from authentication.

A user can be authenticated but still be denied access based on:

-   disabled account;
-   role;
-   operating mode;
-   service availability;
-   administrative restrictions.

## 4.5 Security principle

The service must not depend on:

> "The other lab does not know the URL."

Security must come from actual authentication, authorization, network
controls, and least-privilege service exposure.

------------------------------------------------------------------------

# Page 05 --- Network and Global Access

## 5.1 Network requirement

The AI station is connected through university Wi-Fi and cannot depend
on university IT configuring inbound routing.

Therefore the platform must not require:

-   a public inbound port on the university router;
-   static port forwarding;
-   special campus firewall rules;
-   direct Block-A-to-Block-B routing.

## 5.2 V2 transport

The target V2 architecture uses an **outbound tunnel**.

``` text
Authorized Client
       │
       ▼
Public HTTPS endpoint
       │
       ▼
Cloudflare edge
       │
       │ outbound tunnel
       ▼
AI workstation
```

Cloudflare Tunnel is suitable for this pattern because it uses an
outbound-only connection and does not require a public IP or open
inbound port.

## 5.3 Important distinction

The workstation can have normal outbound Internet access:

``` text
AI station
├── GitHub
├── Hugging Face
├── Docker registries
├── package repositories
├── model downloads
└── normal web access
```

while the inference service remains protected.

Outbound access does not imply that the inference port is directly
exposed.

## 5.4 Public endpoint

The intended user-facing endpoint is conceptually:

``` text
https://ai.<controlled-domain>/v1
```

The exact domain is deployment configuration.

The public edge must terminate HTTPS and forward only to the gateway.

## 5.5 Direct inference exposure prohibited

The following architecture is forbidden:

``` text
Internet
   │
   ▼
:8000
   │
   ▼
vLLM
```

Instead:

``` text
Internet
   │
   ▼
HTTPS / tunnel
   │
   ▼
Gateway
   │
   ▼
private Docker network
   │
   ▼
vLLM
```

------------------------------------------------------------------------

# Page 06 --- Client and Agent Architecture

## 6.1 Core philosophy

The AI server is **not the coding environment**.

The user's laptop remains the execution environment.

``` text
Laptop
├── source code
├── Git
├── terminal
├── compiler
├── test runner
└── coding agent
```

The AI station supplies inference.

## 6.2 Supported clients

The backend must remain compatible with any client that can consume the
selected OpenAI-compatible API.

Target clients include:

-   Cline;
-   Roo Code;
-   Continue;
-   Aider;
-   OpenCode;
-   OpenHands;
-   custom Python clients;
-   custom applications;
-   other compatible IDE integrations.

The server must not contain client-specific business logic.

## 6.3 Agentic workflow

The intended experience is:

``` text
User:
"Build X."

Agent:
1. Inspect repository
2. Plan changes
3. Read relevant files
4. Edit files
5. Run commands
6. Run tests
7. Observe errors
8. Diagnose
9. Modify code
10. Run tests again
11. Repeat
12. Report completion
```

This is fundamentally different from simple one-shot code generation.

## 6.4 Repository boundary

The AI server must not mount student repositories.

The agent decides what context to send to the model.

This minimizes:

-   unnecessary data transfer;
-   server-side storage;
-   privacy exposure;
-   accidental repository persistence.

## 6.5 Tool execution boundary

The coding agent executes tools on the user's development machine.

The inference server provides model intelligence but is not a general
remote shell for students.

------------------------------------------------------------------------

# Page 07 --- Inference Layer and Model Strategy

## 7.1 Inference runtime

Initial runtime:

**vLLM**

Reasons:

-   OpenAI-compatible APIs;
-   streaming support;
-   efficient serving;
-   Docker support;
-   support for modern generation workloads;
-   suitable separation between model serving and application gateway.

## 7.2 API contract

The gateway should expose an OpenAI-compatible surface.

Primary endpoints include:

``` text
/v1/models
/v1/chat/completions
/v1/responses
```

Additional APIs may be exposed later if required by selected models.

## 7.3 Model registry

The platform must support multiple models without forcing client
reconfiguration.

Conceptually:

``` text
Model Registry
├── campus-coder
├── campus-reasoner
├── campus-general
└── future aliases
```

Aliases should map to actual model identifiers.

## 7.4 Model lifecycle

Because the GPU has 16 GB VRAM, the system should not attempt to keep a
large model collection resident simultaneously.

Models may be:

``` text
SSD
  ↓
selected model
  ↓
GPU VRAM
  ↓
inference
```

Model switching is an operational event and should be measurable.

## 7.5 Initial model class

The first benchmark target should be a strong **7--8B-class
coding/reasoning model in an appropriate quantized format**.

The PRD deliberately does not hard-code a permanent model name. Model
selection must be benchmark-driven.

Evaluation criteria:

-   coding correctness;
-   agentic reliability;
-   tool-call quality;
-   context handling;
-   tokens/second;
-   VRAM usage;
-   latency;
-   behavior under 1, 2, and 3 concurrent jobs.

------------------------------------------------------------------------

# Page 08 --- Operating Modes

The platform has three primary operating modes.

## 8.1 Coding Serving Mode

Purpose:

> Serve selected campus users.

``` text
Users
  │
  ▼
Gateway
  │
  ▼
Priority Queue
  │
  ├── Job 1
  ├── Job 2
  └── Job 3
        │
        ▼
      vLLM
```

Default:

``` text
Maximum active jobs: 3
Additional requests: queue
```

## 8.2 Personal Coding Mode

Purpose:

> The owner is actively using the workstation as a remote coding
> inference engine.

The owner receives higher priority.

Initial intended behavior:

``` text
Owner request
    ↓
high priority
    ↓
next available slot
```

Running jobs should normally be allowed to complete rather than being
abruptly killed.

## 8.3 Game Dev Mode

Purpose:

> Run Unity/Unreal/game-development workloads while retaining limited AI
> assistance.

Policy:

``` text
Game engine
    ↓
highest GPU priority

AI
    ↓
reduced/conservative capacity
```

AI remains available.

The system should monitor GPU/VRAM pressure and queue or throttle new
inference work when necessary.

## 8.4 Mode transitions

Mode switching should be explicit and auditable.

Example:

``` text
ai-mode serving
ai-mode personal
ai-mode gamedev
```

The exact CLI is implementation-defined.

------------------------------------------------------------------------

# Page 09 --- Queue and Scheduling System

## 9.1 Global concurrency

The initial global concurrency limit is:

``` text
3 active inference jobs
```

This is a GPU-resource limit, not a user limit.

Example:

``` text
50 accounts
    ↓
12 active users
    ↓
3 running inference jobs
    ↓
9 waiting
```

## 9.2 Queue behavior

The fourth request should normally become:

``` text
QUEUED
```

rather than receiving an immediate "GPU busy" error.

## 9.3 Queue metadata

The API should expose useful state where practical:

``` json
{
  "status": "queued",
  "position": 4,
  "request_id": "..."
}
```

Exact API format is to be finalized during implementation.

## 9.4 Priority scheduling

The scheduler must support priority values.

Conceptual roles:

``` text
Administrator
Developer
Executive
Researcher
Member
```

Exact role names and weights are configuration.

The scheduler should select the highest-priority eligible queued request
when capacity becomes available.

## 9.5 Fairness

Priority must not become starvation.

Future scheduler features may include:

-   aging;
-   weighted fair queueing;
-   maximum consecutive jobs;
-   per-user active-job limits.

## 9.6 No artificial token quotas

Users do not receive a monthly token allowance.

The system instead enforces:

-   maximum active jobs;
-   queue capacity;
-   request validity;
-   abuse protection;
-   GPU safety.

------------------------------------------------------------------------

# Page 10 --- Resource Management and Game Dev Protection

## 10.1 Monitored resources

The platform should monitor:

-   GPU utilization;
-   GPU VRAM usage;
-   GPU temperature;
-   CPU utilization;
-   system RAM;
-   WSL memory;
-   Docker health;
-   inference latency;
-   queue depth;
-   tokens/second.

## 10.2 VRAM-aware behavior

The 16 GB GPU is shared between:

-   inference;
-   Windows display/desktop;
-   Unity/Unreal;
-   other GPU workloads.

Therefore model configuration must include:

-   context length;
-   maximum concurrent requests;
-   KV-cache limits;
-   model-specific memory configuration.

## 10.3 Game Dev Mode

Game Dev Mode should not simply claim:

> "AI gets 30% GPU."

GPU scheduling is not that simple.

Instead, the system should observe actual pressure.

Conceptual policy:

``` text
Low GPU pressure
    ↓
normal AI

Moderate pressure
    ↓
reduce AI concurrency/context

High VRAM pressure
    ↓
queue new AI jobs

Critical pressure
    ↓
AI inference paused
```

## 10.4 Personal Coding Mode

Personal Coding Mode can be more aggressive than Game Dev Mode.

It may permit:

-   larger context;
-   higher concurrency for owner tasks;
-   reduced campus priority;
-   more permissive model settings.

All such settings remain configurable.

------------------------------------------------------------------------

# Page 11 --- Authentication, API Keys, and Secrets

## 11.1 User credentials

Each user receives unique credentials.

Never use:

``` text
username: campus
password: shared-password
```

## 11.2 API keys

Coding clients use API keys.

Keys should be:

-   generated securely;
-   displayed once where possible;
-   stored as hashes;
-   revocable;
-   individually identifiable;
-   associated with a user.

## 11.3 Key metadata

Store:

``` text
key_id
user_id
created_at
last_used_at
revoked_at
label
```

Do not store raw API keys after initial issuance.

## 11.4 Admin secrets

Secrets must be injected through environment/configuration management
and never committed to Git.

Examples:

``` text
database credentials
JWT secret
API signing secret
Cloudflare credentials
model repository tokens
admin credentials
```

## 11.5 Service-to-service authentication

The gateway must authenticate to vLLM where supported.

vLLM must not be publicly reachable.

------------------------------------------------------------------------

# Page 12 --- Data, Logging, and Privacy

## 12.1 Storage target

A maximum operational log budget of approximately **20 GB** is
acceptable.

Storage is not a major constraint on the workstation.

## 12.2 Default telemetry

Store:

``` text
request ID
user ID
model
mode
priority
request timestamp
queue wait time
generation duration
input token count
output token count
completion status
error class
```

## 12.3 GPU telemetry

Store periodic:

``` text
GPU utilization
VRAM usage
temperature
power usage where available
```

## 12.4 Prompt/response storage

Full prompt/response logging should be **disabled by default**.

Reasons:

-   student source code may appear in prompts;
-   prompts may contain credentials or private material;
-   logs become a high-value privacy target;
-   full transcripts are not required for normal operation.

If enabled for debugging, it must be:

-   explicitly configured;
-   clearly documented;
-   retention-limited;
-   access-controlled.

## 12.5 Log rotation

Logs should rotate automatically.

When the configured storage budget is reached:

``` text
oldest eligible logs
        ↓
deleted/compacted
```

The service must never consume the entire system disk because logging
was forgotten.

------------------------------------------------------------------------

# Page 13 --- Usage Analytics and Leaderboard

## 13.1 Purpose

Analytics serve two purposes:

1.  operational monitoring;
2.  making the platform engaging for users.

## 13.2 Metrics

Potential metrics:

-   requests completed;
-   coding tasks completed;
-   generated tokens;
-   model usage;
-   successful requests;
-   average latency;
-   queue wait time;
-   active days;
-   agent sessions.

## 13.3 Leaderboard

The system should support a leaderboard, but raw token consumption
should not be the only ranking metric.

Possible ranking:

``` text
Activity
Task completions
Successful generations
Contribution points
```

A configurable scoring model can be introduced later.

## 13.4 Anti-gaming

The leaderboard must not reward:

-   spam;
-   deliberately huge prompts;
-   pointless generations;
-   repeated requests designed only to increase counters.

## 13.5 Privacy

Users should have a predictable display identity.

The leaderboard should not expose:

-   API keys;
-   private prompts;
-   source code;
-   private model responses;
-   internal authentication data.

------------------------------------------------------------------------

# Page 14 --- Docker and Repository Architecture

## 14.1 Repository

Proposed structure:

``` text
campus-ai/
├── README.md
├── LICENSE
├── .env.example
├── compose.yaml
│
├── gateway/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py
│       ├── config.py
│       ├── auth/
│       ├── api/
│       ├── scheduler/
│       ├── models/
│       ├── users/
│       ├── analytics/
│       └── monitoring/
│
├── inference/
│   ├── Dockerfile
│   ├── configs/
│   └── scripts/
│
├── database/
│   ├── migrations/
│   └── seed/
│
├── monitoring/
│   └── configs/
│
├── docs/
│   ├── architecture/
│   ├── operations/
│   ├── clients/
│   └── security/
│
├── scripts/
│   ├── start.sh
│   ├── stop.sh
│   ├── health.sh
│   └── mode.sh
│
└── tests/
    ├── unit/
    ├── integration/
    └── load/
```

## 14.2 Core containers

Initial target:

``` text
gateway
inference
database
monitoring
cloudflared
```

Do not add Redis, Kafka, Kubernetes, Qdrant, Neo4j, or other
infrastructure until an actual requirement appears.

## 14.3 Internal networking

``` text
Internet
   │
cloudflared
   │
gateway
   │
private Docker network
   │
inference
```

Database is reachable only by services that require it.

## 14.4 Model storage

Models must not live inside Git.

Conceptual host storage:

``` text
D:\CampusAI\models
```

or a WSL/Linux-mounted equivalent.

Container mount:

``` text
/models
```

The exact storage location is deployment configuration.

------------------------------------------------------------------------

# Page 15 --- Deployment and Operations

## 15.1 Development workflow

Development should happen on the user's laptop.

``` text
Laptop
   │
   ├── Git
   ├── Docker
   ├── unit tests
   └── mock inference
```

The production GPU station is not the primary development environment.

## 15.2 Deployment workflow

Target:

``` bash
git clone <repository>
cd campus-ai
cp .env.example .env
docker compose up -d
```

The actual command set may change during implementation.

## 15.3 GPU verification

Before inference deployment:

``` text
Windows NVIDIA driver
        ↓
WSL2 GPU visibility
        ↓
Docker GPU visibility
        ↓
CUDA container
        ↓
vLLM
```

Each layer must be independently verified.

## 15.4 Health checks

Every critical service should expose a health signal.

Example:

``` text
gateway     HEALTHY
database    HEALTHY
inference   HEALTHY
tunnel      HEALTHY
```

## 15.5 Automatic recovery

Docker restart policies should recover ordinary process failures.

The system should distinguish:

-   process failure;
-   model failure;
-   GPU failure;
-   network failure;
-   tunnel failure;
-   database failure.

## 15.6 Startup

The intended workstation behavior is:

``` text
Windows boot
   ↓
WSL2
   ↓
Docker
   ↓
Campus AI stack
   ↓
health checks
   ↓
service available
```

The exact Windows/WSL2 auto-start mechanism is implementation work.

------------------------------------------------------------------------

# Page 16 --- Security Model

## 16.1 Threat model

The system assumes that:

-   unauthorized students may discover the endpoint;
-   credentials may be stolen;
-   malicious requests may occur;
-   users may accidentally submit secrets;
-   users may attempt excessive request submission;
-   the workstation may be attacked from the network;
-   the public endpoint may receive automated scanning.

## 16.2 Security layers

``` text
Internet
   │
   ▼
Cloudflare edge
   │
   ▼
Encrypted tunnel
   │
   ▼
Gateway
   │
   ├── authentication
   ├── authorization
   ├── API key validation
   ├── request validation
   ├── queue controls
   └── audit logging
   │
   ▼
Private inference network
   │
   ▼
vLLM
```

## 16.3 Direct exposure rules

Never expose:

-   database ports;
-   Docker daemon;
-   WSL management interfaces;
-   vLLM administrative endpoints;
-   monitoring internals;
-   internal service ports.

Only the intended gateway/tunnel path should be externally reachable.

## 16.4 Secrets

Secrets must not be:

-   committed to Git;
-   embedded in Docker images;
-   printed in logs;
-   returned by diagnostic endpoints.

## 16.5 Student isolation

Students are consumers of inference, not administrators of the
workstation.

No student should receive:

-   shell access to the AI server;
-   Docker access;
-   WSL access;
-   model filesystem access;
-   database credentials;
-   admin credentials.

------------------------------------------------------------------------

# Page 17 --- Testing, Benchmarking, and Acceptance Criteria

## 17.1 Hardware acceptance

Pass criteria:

``` text
Windows GPU
    ↓
WSL2 GPU
    ↓
Docker GPU
    ↓
vLLM GPU
```

all operate reliably.

## 17.2 Inference benchmarks

Benchmark:

``` text
1 concurrent request
2 concurrent requests
3 concurrent requests
```

Measure:

-   time to first token;
-   tokens/sec;
-   total generation time;
-   VRAM;
-   GPU utilization;
-   CPU usage;
-   RAM usage.

## 17.3 Agentic benchmark

Use realistic coding tasks.

Example:

``` text
Task:
Implement a REST API endpoint,
write tests,
run tests,
fix failures,
and produce a working implementation.
```

Measure:

-   task completion;
-   number of agent turns;
-   failed tool calls;
-   test pass rate;
-   total tokens;
-   wall-clock time.

## 17.4 Queue acceptance

With four simultaneous requests:

``` text
Request 1 → RUNNING
Request 2 → RUNNING
Request 3 → RUNNING
Request 4 → QUEUED
```

When one completes:

``` text
Request 4 → RUNNING
```

## 17.5 Authentication acceptance

Test:

``` text
valid user      → allowed
invalid key     → denied
revoked key     → denied
disabled user   → denied
unknown user    → denied
```

## 17.6 Mode acceptance

Coding Serving:

``` text
≤3 jobs
```

Personal Coding:

``` text
owner receives higher scheduling priority
```

Game Dev:

``` text
AI remains available
AI becomes conservative under GPU pressure
```

## 17.7 Network acceptance

Verify that:

-   public endpoint uses HTTPS;
-   tunnel works without inbound port forwarding;
-   unauthorized users cannot access inference;
-   vLLM is not directly exposed;
-   API streaming works through the tunnel.

------------------------------------------------------------------------

# Page 18 --- Roadmap, Risks, and Definition of Done

## 18.1 Phase 0 --- Hardware validation

Tasks:

-   verify GPU;
-   verify driver;
-   verify WSL2;
-   verify Docker;
-   verify GPU inside container;
-   benchmark baseline.

Deliverable:

``` text
Docker container can execute CUDA workload.
```

## 18.2 Phase 1 --- Local inference

Tasks:

-   deploy vLLM;
-   load first coding model;
-   expose OpenAI-compatible API;
-   test streaming;
-   test OpenAI client;
-   test basic IDE integration.

Deliverable:

``` text
Laptop → AI station → model → streamed response
```

## 18.3 Phase 2 --- Gateway

Tasks:

-   authentication;
-   API keys;
-   model registry;
-   request validation;
-   health checks;
-   logging.

Deliverable:

``` text
Authenticated client → gateway → vLLM
```

## 18.4 Phase 3 --- Scheduler

Tasks:

-   three active jobs;
-   FIFO queue;
-   configurable priority;
-   queue metrics;
-   graceful cancellation.

Deliverable:

``` text
3 running + N queued
```

## 18.5 Phase 4 --- Operating modes

Tasks:

-   Coding Serving Mode;
-   Personal Coding Mode;
-   Game Dev Mode;
-   configuration profiles;
-   mode audit events.

## 18.6 Phase 5 --- Multi-model support

Tasks:

-   model registry;
-   model aliases;
-   model lifecycle;
-   benchmark multiple candidate models;
-   select default coding model.

## 18.7 Phase 6 --- Global V2

Tasks:

-   Cloudflare Tunnel;
-   public HTTPS endpoint;
-   domain;
-   hardened gateway;
-   rate/abuse protection;
-   external client testing.

## 18.8 Phase 7 --- Analytics

Tasks:

-   usage telemetry;
-   GPU dashboard;
-   queue dashboard;
-   leaderboard;
-   retention policies.

## 18.9 Primary risks

### VRAM pressure

The 16 GB GPU is the dominant constraint.

Mitigation:

-   quantized models;
-   bounded context;
-   controlled concurrency;
-   VRAM monitoring;
-   Game Dev Mode.

### Agentic workload amplification

One user task can generate many inference calls.

Mitigation:

-   queue;
-   priority;
-   fair scheduling;
-   request validation;
-   observability.

### University network restrictions

Mitigation:

-   outbound tunnel;
-   no inbound port dependency.

### Credential compromise

Mitigation:

-   individual API keys;
-   revocation;
-   secure storage;
-   HTTPS;
-   no shared credentials.

### Model quality

A small local model may be less capable than premium commercial models.

Mitigation:

-   benchmark several models;
-   support model switching;
-   optimize for coding rather than generic chat;
-   measure agentic task completion rather than benchmark scores alone.

### Power failure

The workstation is intended to operate 24/7 but depends on available
power backup.

Mitigation:

-   automatic service startup;
-   Docker restart policies;
-   health checks;
-   recovery testing.

## 18.10 Definition of Done --- V1

V1 is complete when all of the following are true:

-   [ ] RTX 5060 Ti 16 GB is usable from Docker under WSL2.
-   [ ] A coding model runs reliably.
-   [ ] vLLM exposes an OpenAI-compatible API.
-   [ ] A laptop can connect remotely.
-   [ ] At least one coding agent successfully uses the remote model.
-   [ ] Agentic coding can modify a local repository and run local
    tests.
-   [ ] Gateway authentication works.
-   [ ] Manual user provisioning works.
-   [ ] Three concurrent inference jobs work.
-   [ ] Additional requests queue correctly.
-   [ ] Priority scheduling exists.
-   [ ] Coding Serving Mode works.
-   [ ] Personal Coding Mode works.
-   [ ] Game Dev Mode works.
-   [ ] vLLM is not directly exposed.
-   [ ] Logs rotate within the configured storage budget.
-   [ ] Basic GPU/queue telemetry works.
-   [ ] Model selection is configurable.
-   [ ] Docker Compose can recreate the service from a clean deployment.
-   [ ] Failure/restart recovery has been tested.

## 18.11 Definition of Done --- V2

V2 is complete when:

-   [ ] Cloudflare Tunnel is operational.
-   [ ] Service is reachable globally through HTTPS.
-   [ ] No inbound port forwarding is required.
-   [ ] Only approved accounts can use the service.
-   [ ] Up to 50 accounts can be provisioned.
-   [ ] API clients work from outside the university network.
-   [ ] Usage analytics are available.
-   [ ] Leaderboard is operational.
-   [ ] Security controls have been tested.
-   [ ] 1/2/3 concurrent inference benchmarks are documented.
-   [ ] Game Dev Mode has been tested against a real game-development
    workload.

------------------------------------------------------------------------

# Appendix A --- Reference Architecture

``` text
                           PUBLIC INTERNET
                                  │
                                  ▼
                         ┌─────────────────┐
                         │   CLOUDFLARE    │
                         │     EDGE        │
                         └────────┬────────┘
                                  │
                           HTTPS / Tunnel
                                  │
                                  ▼
┌───────────────────────────────────────────────────────────┐
│                    AI WORKSTATION                         │
│                                                           │
│ Windows 11                                                │
│   │                                                       │
│   └── WSL2                                                │
│        │                                                  │
│        └── Docker                                         │
│             │                                             │
│       ┌─────┴───────────────────────────┐                 │
│       │                                 │                 │
│       ▼                                 ▼                 │
│  ┌──────────────┐                ┌──────────────┐         │
│  │ AI Gateway   │                │ Cloudflared  │         │
│  │              │                │              │         │
│  │ Auth         │◄──────────────►│ Tunnel       │         │
│  │ API keys     │                └──────────────┘         │
│  │ Queue        │                                         │
│  │ Priority     │                                         │
│  │ Modes        │                                         │
│  │ Analytics    │                                         │
│  └──────┬───────┘                                         │
│         │                                                 │
│         ▼                                                 │
│  ┌──────────────┐                                         │
│  │    vLLM      │                                         │
│  │              │                                         │
│  │ OpenAI API   │                                         │
│  │ Streaming    │                                         │
│  └──────┬───────┘                                         │
│         │                                                 │
│         ▼                                                 │
│  ┌─────────────────────┐                                  │
│  │ RTX 5060 Ti 16 GB   │                                  │
│  └─────────────────────┘                                  │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

# Appendix B --- Core API Concept

``` text
GET  /v1/models
POST /v1/chat/completions
POST /v1/responses

GET  /health
GET  /status
```

Administrative endpoints should live outside the public
OpenAI-compatible surface and require administrative authorization.

# Appendix C --- Operating State Model

``` text
                    ┌──────────────────────┐
                    │ CODING SERVING MODE  │
                    │ 3 active jobs        │
                    │ campus priority      │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │ PERSONAL CODING MODE │
                    │ owner priority       │
                    │ aggressive AI        │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │    GAME DEV MODE     │
                    │ game workload first  │
                    │ AI remains available │
                    └──────────────────────┘
```

# Appendix D --- Engineering Rules

1.  Do not expose vLLM directly.
2.  Do not store student repositories on the AI station.
3.  Do not put model weights in Git.
4.  Do not hard-code credentials.
5.  Do not build Kubernetes for this scale.
6.  Do not add infrastructure without a demonstrated requirement.
7.  Do not assume a model fits safely because its weights fit in VRAM.
8.  Do not use token quotas unless future abuse requires them.
9.  Do not allow leaderboard mechanics to reward spam.
10. Do not make campus routing a hard dependency.
11. Do not make the client depend on one coding-agent vendor.
12. Do not choose the final model before benchmarking it on actual
    agentic coding tasks.
13. Do not treat Game Dev Mode as a cosmetic setting; it is a resource
    policy.
14. Do not store full prompts/responses by default.
15. Measure before optimizing.

# Appendix E --- Verified Technical References

The architecture is based on the following current official
documentation:

-   vLLM OpenAI-compatible server documentation.
-   NVIDIA CUDA on WSL documentation.
-   NVIDIA Container Toolkit documentation.
-   Cloudflare Tunnel documentation.

These references should be rechecked during implementation because
runtime versions, model compatibility, and service-plan limits can
change.

------------------------------------------------------------------------

## Final Product Definition

**Campus AI Work Station** is a self-hosted, API-first, agentic coding
inference platform running on a Windows 11 workstation with an RTX 5060
Ti 16 GB and 64 GB RAM.

It provides selected users with access to multiple local models through
an OpenAI-compatible API. Coding agents remain on user machines and use
the remote model to perform iterative software-engineering work. The
platform supports three resource policies---**Coding Serving Mode,
Personal Coding Mode, and Game Dev Mode**---with three active inference
jobs as the initial global ceiling.

The service is authenticated, manually provisioned, queue-based,
priority-aware, observable, Dockerized, and designed for global HTTPS
access through an outbound tunnel without requiring university IT to
expose inbound ports.

The central engineering objective is not to maximize the number of
containers or models.

It is to make one 16 GB consumer GPU behave like a **reliable small
shared inference service** while remaining useful as a personal
development workstation.
