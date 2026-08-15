# Understanding Klarnova

*A newcomer's guide to how the system works.*

If you just joined the team and want to understand what Klarnova is, what problem it
solves, and how all the pieces fit together — start here. This guide is deliberately
conceptual. It explains ideas first and points at code and references second. Once
you have read it, you should be able to answer: *"what happens in Klarnova when a
service starts failing?"*

- **Who this is for:** anyone new to the project (developers, reviewers, testers).
- **Prerequisite knowledge:** a rough idea of what a web server is. Kubernetes and
  Prometheus are explained briefly below — no deep expertise assumed.
- **Related docs:** [architecture](Klarnova_Technical_Architecture.md) (formal
  reference), [API reference](api-reference.md), [walkthrough](walkthrough.md),
  [evaluation results](evaluation-results.md).

---

## 1. What is Klarnova?

Klarnova is an **autonomous incident-remediation agent for Kubernetes**. In plain
English: it is software that lives inside a Kubernetes cluster, watches that cluster
for problems, and — when something breaks — figures out *why*, decides *what should be
done*, and (with human approval when needed) *fixes it by itself*.

Systems like this belong to a field called **AIOps** (applying AI to IT operations).
They exist because on-call engineers spend a lot of their time on repetitive,
mechanical work: an alert fires, they SSH into a box, look at logs, restart the same
deployment for the fifth time that week, and file a note about it. Klarnova automates
that loop so the human can concentrate on the alerts that actually need judgment.

The measurable goals of the project are standard SRE metrics:

| Metric | What it measures | How Klarnova helps |
|--------|------------------|--------------------|
| **MTTD** (Mean Time To Detect) | How long until a problem is noticed | Alerts reach Klarnova the moment they fire |
| **MTTR** (Mean Time To Resolve) | How long until the problem is fixed | Diagnosis + action run in seconds, not minutes |
| **Toil reduction** | Repetitive manual work | Routine fixes (restart, scale, rollback) run automatically |

> **One sentence summary:** *Klarnova turns "an alert fires" into "the root cause is
> understood, a safe fix is chosen, applied, and verified — with a human deciding
> whenever the risk is high."*

---

## 2. Key concepts first

Before we look at any component, here are the ideas Klarnova is built on. Every term
in this section also appears in the [glossary](#11-glossary) at the end.

### 2.1 The stage: Kubernetes, Prometheus, AlertManager

Kubernetes ("K8s") is the platform that runs the containers. It continuously makes
sure the services you asked for actually exist — if a container crashes, Kubernetes
tries to restart it.

Prometheus is a monitoring system. It scrapes metrics from the cluster and evaluates
rules against them. When a rule matches (for example, *"this pod has restarted 5 times
in 10 minutes"*), Prometheus produces an **alert**.

AlertManager is the component that takes those alerts and routes them somewhere a
human (or another system) can act on them. Klarnova plugs in right here: it registers
itself as an AlertManager **webhook receiver**, meaning AlertManager simply calls a
Klarnova URL and hands it the alert.

### 2.2 Alert vs. incident

| Term | Meaning |
|------|---------|
| **Alert** | A raw notification from AlertManager. It says *something* looks wrong. |
| **Incident** | Klarnova's internal record of *dealing with* that alert. An incident is born the moment Klarnova starts investigating and it carries the whole story: severity, diagnosis, chosen action, approvals, result. |

One important consequence: an alert can fire many times, but Klarnova **deduplicates**
— it will not start a second investigation for an incident that is already over
(`Resolved`, `Escalated`, or `Closed`).

### 2.3 Severity

Every incident is classified into one of four severity levels. Severity drives
everything downstream: which actions are allowed automatically, which require a human,
and how urgent the handling is.

| Level | Meaning | Alert label | Example |
|-------|---------|-------------|---------|
| SEV-1 | Critical — something is seriously broken | `critical` | Production service down |
| SEV-2 | High — degraded service | `high` | API errors elevated |
| SEV-3 | Warning — needs attention | `warning` | Pod crash-looping |
| SEV-4 | Info — cosmetic / low priority | `info` | Resource usage rising |

The mapping from alert label to severity is deterministic (rule-based), never guessed
by the AI.

### 2.4 Agent and agent graph

The word "agent" is used in two related ways here:

1. An **agent** is a single focused step of reasoning — for example *"look at the
   logs"* or *"propose a fix"*. Klarnova's pipeline is made of several such agents.
2. The **agent graph** is the choreography that decides in which order those steps
   run. Klarnova uses **LangGraph** for this. You can think of the graph as a
   flowchart: a box for each agent, an arrow showing the next step, and a shared
   blackboard (the *state*) on which every agent writes what it found.

The big idea of an agent graph (as opposed to one long AI prompt) is **control**. Each
step is a small, testable unit, and the flow can branch — for example, "if the fix did
not work, try again; if it still fails, escalate to a human."

### 2.5 Runbooks and RAG

A **runbook** is a written recipe for solving a known problem ("when this alert fires,
the most likely cause is X; try Y"). In a traditional team, runbooks live in a wiki and
a human reads them during an incident.

Klarnova keeps its runbooks in a **vector knowledge base** and retrieves the relevant
ones automatically. The retrieval part of this — *find the most relevant documents and
feed them to the AI as context* — is called **RAG** (Retrieval-Augmented Generation).
Instead of asking an AI to answer purely from memory, we give it the right paragraph
and let it answer from that. This makes answers more accurate and tied to *our* system
rather than generic AI knowledge.

### 2.6 Remediation actions

A "remediation action" is a concrete thing Klarnova can do to a Kubernetes cluster.
There are exactly five, and together they form the **action whitelist** — the complete
universe of things the system is ever allowed to do:

| Action | What it does |
|--------|--------------|
| `restart_pod` | Delete a pod so Kubernetes brings up a fresh one |
| `delete_pod` | Remove a pod (same effect as above, used in different contexts) |
| `scale_deployment` | Change the number of replicas of a deployment |
| `rollback_deployment` | Return a deployment to its previous, known-good revision |
| `cordon_node` | Mark a node unschedulable so no new work lands on it |

Everything outside this list is refused, no matter what the AI says. This is one of the
most important safety properties in the whole system.

### 2.7 Policy and the safety gate

Not all actions are equally risky. Restarting a pod is low-risk; rolling back a
production deployment is high-risk; touching a node is riskier still. Klarnova encodes
this as a **policy**: a table of *(action, severity) → how to proceed*.

For every pair, the policy answers one of three ways:

- **`auto`** — execute immediately, no human needed.
- **`require_approval`** — pause and ask a human first.
- **`deny`** — never do this; the action is refused outright.

Two extra rules always apply: a **confidence threshold** (if the AI is not confident
enough about its diagnosis, even an "auto" action becomes an approval), and the rule
that **SEV-1 always requires human approval**.

This human-in-the-loop step is the *safety gate*. It exists because an autonomous
system is only useful if operators trust it — and trust comes from having a veto point
where it counts.

### 2.8 Contextual bandit (how it learns)

When several actions are all allowed, which one should Klarnova choose? The system
uses a **contextual bandit** — a simple form of machine learning.

Think of it as a gambler with a bag of slot machines, one per action. Each "pull"
is one incident where an action was executed. The gambler keeps a score for each
machine: *when I chose this action in this kind of situation, did the incident get
resolved?* Over time, the algorithm favours actions that have worked — but it keeps a
small amount of exploration so it can still discover better ones. "Contextual" means
the choice also looks at the situation (severity, how many replicas are down, restart
count), not just the action name.

Learning is **offline from the human** — the AI's own choice history, plus what
happened, is what improves future choices. The human always retains the final say via
approvals.

---

## 3. The big picture

Here is the whole system in one diagram. Don't worry about the details yet — read the
paragraphs underneath, then come back to the picture.

```
                        ┌──────────────────────────────────────────────┐
                        │            Kubernetes cluster                │
                        │                                              │
   Your services ──────►│  ┌──────────┐   ┌───────────────┐            │
   (Sock Shop, etc.)    │  │ Prometheus│──►│ AlertManager  │            │
                        │  └──────────┘   └──────┬────────┘            │
                        │                        │  webhook             │
                        │                        ▼                     │
                        │  ┌──────────────────────────────────────┐    │
                        │  │            Klarnova backend          │    │
                        │  │  ┌────────────┐   ┌───────────────┐  │    │
                        │  │  │  agent      │   │  policy       │  │    │
                        │  │  │  pipeline   │   │  engine       │  │    │
                        │  │  │  (LangGraph)│   │  (safety gate)│  │    │
                        │  │  └─────┬──────┘   └───────┬───────┘  │    │
                        │  │        │                  │          │    │
                        │  │  ┌─────▼──────┐   ┌──────▼───────┐   │    │
                        │  │  │ K8s client  │   │ bandit +    │   │    │
                        │  │  │ (actions)   │   │ policy data │   │    │
                        │  │  └────────────┘   └──────────────┘   │    │
                        │  └──────────────────────────────────────┘    │
                        │           │        │       │                 │
                        └───────────┼────────┼───────┼─────────────────┘
                                    │        │       │
                       ┌────────────▼┐  ┌────▼────┐  ┌▼─────────────┐
                       │  PostgreSQL │  │ Ollama  │  │ ChromaDB     │
                       │  incidents, │  │ (LLM)   │  │ runbooks etc.│
                       │  users,     │  │         │  │ (RAG KB)     │
                       │  policy,    │  └─────────┘  └──────────────┘
                       │  audit      │
                       └─────────────┘

                              ┌──────────────┐
                              │  Next.js UI  │──── requests & approvals ──┐
                              │  dashboard   │                            │
                              └──────────────┘        human operator ◄────┘
```

Reading the diagram, left to right:

- **Monitoring.** Prometheus watches the workloads. When something breaks, it raises
  an alert and AlertManager routes that alert to the Klarnova backend over a webhook.
  This is the only way an incident *starts*.
- **The Klarnova backend** is the heart. The *agent pipeline* investigates and
  decides; the *policy engine* is the safety gate that decides whether an action may
  run automatically or must wait for a human; the *K8s client* actually performs
  actions against the cluster.
- **Supporting data stores.** *PostgreSQL* keeps the permanent record (incidents,
  users, policy, audit log). *Ollama* runs the local LLM used for diagnosis.
  *ChromaDB* is the vector knowledge base holding runbooks and past incidents for RAG.
- **The dashboard.** A Next.js web app talks to the backend over a REST API. Humans
  review incidents, approve or deny actions, browse analytics, and tune policy. The
  human sits *outside* the automatic loop, which is exactly the point.

---

## 4. The incident lifecycle (narrated)

The most reliable way to understand the system is to follow one incident end to end.
Here is the story of a crash-looping pod — the same scenario used in the live demo.

> **Scenario:** a service called `catalogue` starts crashing. Every attempt to start
> fails, Kubernetes restarts it, and it crashes again.

**Step 1 — The alert fires.** Prometheus sees the repeated restarts and raises the
`KubePodCrashLooping` alert. AlertManager sends it to Klarnova's webhook. Klarnova
checks the secret bearer token, classifies the incident as **SEV-3** (a warning), and
opens an incident record.

**Step 2 — Evidence.** The *investigation* agent fetches the pod's logs from the
Kubernetes API. These logs are attached to the incident as the raw material every later
step reasons over.

**Step 3 — Context.** The *retrieval* agent embeds the alert name and a log excerpt and
searches the runbook collection. If a runbook about crash-looping pods exists, it is
added to the context for the diagnosis step.

**Step 4 — Diagnosis.** The *root cause* agent asks the local LLM (Ollama) "what is
wrong, based on these logs and this runbook?" The answer, with a **confidence score**,
is recorded. If the LLM is unavailable, a deterministic keyword-based fallback takes
over (it looks for OOM-killed, image-pull failures, probe failures, and so on) so the
pipeline still produces a diagnosis.

**Step 5 — Plan.** The *planning* agent ranks the candidate actions. Its preferences
come from two sources: runbook hints (only trusted if strongly relevant) and the
bandit's learned history. In our story, the plan is `restart_pod` — but the confidence
is low (0.45), well below the 0.75 threshold.

**Step 6 — Safety gate.** The policy engine looks up `restart_pod` at SEV-3. Even
though the action itself is normally automatic at this severity, the low confidence
forces the incident into **`awaiting_approval`**. A human must decide.

**Step 7 — Human decision.** The incident appears in the dashboard under **Approvals**.
The operator looks at the diagnosis. Perhaps they disagree with the plan and choose a
stronger fix instead: they approve `rollback_deployment` (the known-good previous
version) rather than a plain restart.

**Step 8 — Execute.** The *remediation* agent re-checks that the chosen action is on
the whitelist and that it has approval, then performs the rollback through the
Kubernetes client.

**Step 9 — Verify.** The *validation* agent polls the pod's health every few seconds
for up to two minutes. The deployment comes back healthy → the incident is marked
**`Resolved`**. If it had still been crashing, the graph would try again (up to a
bounded number of retries) and then escalate to a human.

**Step 10 — Learn and record.** The bandit learns: `rollback_deployment` was executed
and the incident resolved, so its score goes up. The incident is written to the
historical-incidents knowledge base, so future incidents benefit from this one.
The whole story — every agent output, every decision — is persisted in PostgreSQL for
the audit log and the analytics dashboard.

```
 Alert ──► webhook ──► classify (SEV-3)
                          │
                          ▼
               ┌──────────────────────────┐
               │  INVESTIGATION GRAPH     │
               │  evidence ─► runbooks    │
               │      ─► diagnose ─► plan │
               │            ─► safety     │
               └──────────────────────────┘
                          │
                ┌─────────┴──────────┐
                │  requires approval? │
                └─────────┬──────────┘
                ┌─────────┴──────────┐
                │        no          │          yes
                │                    ▼
                │           waiting for human
                ▼             (Approvals page)
        ┌──────────────────────────┐
        │  REMEDIATION GRAPH       │
        │  execute ─► validate     │
        │              │           │
        │        ┌─────┴─────┐     │
        │     healthy     still broken
        │        │           (retry, then escalate)
        └────────┼──────────────┘
                 ▼
           RESOLVED  (bandit learns, history written back)
```

---

## 5. Backend walkthrough

The backend is a FastAPI application. Below is a map of the folders in
`backend/app/`, then a short prose section on each area.

| Folder | Responsibility |
|--------|----------------|
| `api/v1/endpoints/` | HTTP endpoints: auth, incidents, approvals, config, kubernetes, webhooks |
| `agents/` | The LangGraph pipeline: investigation, retrieval, root cause, planning, safety, remediation, validation, reporting, monitoring |
| `policy/` | The safety-gate engine and the YAML rules it evaluates |
| `bandit/` | The contextual bandit: prediction and learning |
| `rag/` | ChromaDB knowledge base: store, ingest, writeback, embedding |
| `k8s/` | Kubernetes client: actions, logs, events, metrics |
| `core/` | Database, security (auth), RBAC |
| `discovery/` | Prometheus metric scraper |
| `services/` | Slack notification |

### 5.1 The API layer

Everything external talks to the backend through REST under `/v1`. The webhook
endpoint is the *entry point for alerts*: it authenticates the call (bearer token),
deduplicates, classifies severity, and launches the agent pipeline as a background
task. The remaining endpoints serve the dashboard: incident listing and stats,
pending approvals, policy viewing and editing, Kubernetes pod inspection, and login.

### 5.2 The agent pipeline

The pipeline is two graphs that run in sequence. The **investigation graph**
(*evidence → retrieval → root cause → planning → safety*) never touches the cluster
beyond reading. Its output is a diagnosis, a ranked plan, and a decision about whether
approval is required. The **remediation graph** (*execute → validate → report*) only
runs once the action is permitted, and it contains the retry-then-escalate loop.

The shared **state** is the blackboard every agent reads from and writes to. If you
open an incident in the dashboard, the "agent runs" section is literally a render of
this state at each step.

### 5.3 The policy engine

The policy engine is deliberately dumb and rule-based. Given an action, a severity,
and a confidence, it returns a decision: `auto`, `require_approval`, or `deny`. The
rules live in a YAML file so they can be tuned by an admin from the dashboard without
touching code. Because the engine is deterministic, the safety guarantees of the
system *never depend on what the AI says* — the AI proposes, the policy disposes.

### 5.4 The bandit

The bandit sits between planning and execution. It scores each whitelisted action from
its history: when this action was executed in a similar context, did the incident
resolve? It mixes a fixed priority order (restart is the safest default, cordon the
riskiest) with learned experience. Learning only records actions that were actually
executed — a plan that was overridden by a human is not credited to the bandit.

### 5.5 RAG and the knowledge base

The knowledge base is three Chroma collections: **runbooks** (how-to-fix recipes),
**historical incidents** (what actually happened before), and **kubernetes docs**.
On startup, and periodically afterwards, the backend ingests the YAML source list into
the collections. Ingestion is idempotent — re-running it does not duplicate documents.
During an incident, retrieval queries the runbook collection and adds the best matches
to the LLM's context.

### 5.6 The Kubernetes client

This module isolates every interaction with the cluster. It loads credentials from the
in-cluster service account when deployed, or from the user's `kubeconfig` when running
locally — and it fails softly, so the backend can still start and answer questions even
if the cluster is unreachable. Actions like `rollback_deployment` are implemented here
by asking Kubernetes for the previous revision of the deployment, mirroring what a
human's `kubectl rollout undo` would do.

### 5.7 Auth, RBAC, and notifications

Authentication uses hashed passwords and short-lived JWTs. Role-based access control
defines three roles: **admin**, **engineer**, and **viewer** — and the same rules are
enforced on the backend *and* reflected in what the UI shows. Notifications to Slack
are best-effort: a failure to notify never aborts the pipeline.

---

## 6. The frontend

The dashboard is a Next.js application. It is a *client* of the backend — it holds no
business logic of its own. A small shared hook polls the API on a timer, so pages
refresh automatically while you watch them.

```
             /login ──────────────► dashboard
                                      │
                  ┌───────────────────┼────────────────────┐
                  ▼                   ▼                    ▼
            /incidents         /approvals             /analytics
        list of incidents     actions waiting         trends, SEV
        (filter by status)    for a human              breakdown
                  │
                  ▼
            /incidents/[id]   full trace: diagnosis, confidence,
                              chosen action, approvals, outcome
                  │
                  ▼
            /cluster  /settings  (Settings only for admin & engineer;
            pods the                non-admins see policy read-only)
            service
            account
            can see
```

What each page is for:

| Page | Purpose |
|------|---------|
| **Incidents** | The work queue. Every incident with its status and severity; click through to the full trace. |
| **Incident detail** | The story of one incident: root cause, confidence, the chosen action, each agent's output, and the outcome. Approve/deny buttons appear here when an approval is pending and you have the right. |
| **Approvals** | The human decision point. Actions that need approval are listed here; approving one kicks off the remediation graph. |
| **Analytics** | Aggregated health: resolved rate, severity and status breakdown, trend over the last week. |
| **Cluster** | A read-only view of the pods the Klarnova service account is allowed to see. |
| **Settings** | Governance. Admin can change the policy table (which action×severity is auto / approval / denied) and trigger a knowledge-base re-ingest. Everyone else sees it read-only. |

**Roles at a glance:**

| Capability | Viewer | Engineer | Admin |
|------------|--------|----------|-------|
| View incidents, analytics, cluster | ✅ | ✅ | ✅ |
| Approve / deny pending actions | ❌ | ✅ | ✅ |
| Change policy rules | ❌ | ❌ | ✅ |
| Re-ingest knowledge base | ❌ | ❌ | ✅ |

---

## 7. Safety & security model

Klarnova is an autonomous agent that is allowed to touch a production cluster — so
safety is the design's central concern. Three ideas carry most of the weight:

1. **Deterministic where it matters.** Detection, severity classification, policy
   evaluation, execution, and validation are all rule-based. The LLM is only consulted
   where its judgment is genuinely useful (diagnosis, reporting). The system's safety
   guarantees therefore never hinge on what a probabilistic model says.

2. **The whitelist as a hard boundary.** No action outside the five whitelisted ones
   can ever be executed. The whitelist is enforced in the policy engine *and* checked
   again at execution time — defence in depth, so even a confused or malicious prompt
   cannot make the agent invent new destructive operations.

3. **Human veto at the right point.** Risk is a function of action *and* severity.
   High-risk combinations and low-confidence diagnoses require a human. SEV-1 (the
   worst) always requires a human. The human is never an afterthought — approval is a
   first-class state in the pipeline.

Other security properties worth knowing:

- The webhook endpoint is authenticated with a shared secret (the token is set via
  configuration, not baked into code).
- Users authenticate with a password → JWT exchange; the UI stores the token and
  clears it on any unauthorized response.
- RBAC is enforced server-side; the UI merely hides what a role cannot do.
- Sensitive configuration (tokens, database URL) comes from environment variables /
  helm values, never from committed files.
- All failures are logged and persisted in the audit trail, so an operator can always
  reconstruct *what the agent did and why*.

---

## 8. How Klarnova learns over time

Klarnova improves with use. There are two learning loops.

**The bandit loop (choosing better actions).** When an executed action leads to a
resolved incident, the bandit increases that action's score for similar future
contexts. Over many incidents, the system drifts toward the actions that actually
work in *your* cluster — the more incidents it sees, the better its default plans.

```
   incident ──► plan picks action (bandit scores it)
        ──► execute ──► validate ──► resolved? ──► reward (+1 / 0)
        ──► bandit updates scores ──► better next plan
```

**The knowledge loop (remembering incidents).** Every resolved or escalated incident
is written back into the historical-incidents knowledge base. The knowledge base is
the system's long-term memory — the raw material future retrieval steps search.

Both loops are conservative: only executed actions earn credit, and every change is
visible in the dashboard and the database.

---

## 9. Failure and error-handling behavior

A good question to ask of any system is *what happens when a part of it dies?* Here is
Klarnova's answer for each important failure:

| Failure | Behavior |
|---------|----------|
| LLM (Ollama) is down | The root-cause agent falls back to deterministic keyword diagnosis. The incident still gets a diagnosis, just less nuanced. |
| Chroma (knowledge base) is down | Retrieval degrades gracefully — the pipeline runs without runbook context. (This is the current live state when the backend image is built without the RAG extras.) |
| Kubernetes API unreachable | The client fails softly; the backend still serves the dashboard and existing data. |
| Malformed or duplicate alert | Rejected or deduplicated at the webhook; no phantom incidents. |
| Unknown / non-whitelisted action | Denied by the policy engine and refused again at execution. |
| Action fails to help | The validation agent retries within a bounded limit, then escalates to a human. |
| Slack notification fails | Non-fatal — logged and ignored. |
| Invalid or expired user token | Backend returns 401; the UI redirects to the login page. |

The theme is *graceful degradation*: no single dependency can take down the whole
system, and there is always a human-visible record of what happened.

---

## 10. Known limitations

For an honest picture, these are the current gaps (they are also tracked in the
implementation plan):

- **The RAG loop is half-closed.** Retrieval searches runbooks, and resolved incidents
  are written back to history — but retrieval does not yet search the history
  collection. The learning loop works; it just isn't yet feeding retrieval.
- **RAG is degraded in the default cluster build.** The backend image is built without
  the RAG extras by default (`INSTALL_ML=false`), so Chroma is unavailable in the
  minikube deployment. The image can be rebuilt with `INSTALL_ML=true` to enable it.
- **Single-node / POC-grade.** The whole system is designed to be understood and
  evaluated on one cluster. Production hardening (HA, more operators, larger
  evaluations) is future work.
- **Live evaluation data is thin.** Formal evaluation with a larger set of scenarios
  (`N ≥ 30`) is on the roadmap and will give the bandit longitudinal evidence to
  improve on.

---

## 11. Glossary

| Term | Meaning |
|------|---------|
| **Agent** | A single focused step of the pipeline (e.g., "diagnose", "plan", "validate"). |
| **Agent graph** | The ordered, branching flow that links agents together; Klarnova uses LangGraph. |
| **AIOps** | Applying AI to IT operations, especially incident response and monitoring. |
| **Alert** | A raw notification from AlertManager that something may be wrong. |
| **AlertManager** | Prometheus's component for routing alerts to receivers (including Klarnova). |
| **Approval** | A human's explicit "go ahead" before a risky action is executed. |
| **Bandit / contextual bandit** | A learning algorithm that scores actions from history and context to choose better ones over time. |
| **ChromaDB** | The vector database that stores the knowledge base (runbooks, history, docs). |
| **Confidence** | How sure the diagnosis agent is, on a 0–1 scale; low confidence forces approval. |
| **Dedup** | Skipping work for alerts that refer to an incident that is already finished. |
| **Incident** | Klarnova's record of handling one alert, from investigation to resolution. |
| **LangGraph** | The framework used to define and run the agent graphs. |
| **MTTD / MTTR** | Mean Time To Detect / To Resolve — speed metrics for incident response. |
| **Ollama** | The local LLM runtime used for diagnosis and reporting. |
| **Policy** | The table of rules: for each action×severity, auto / require approval / deny. |
| **Prometheus** | The monitoring system that detects problems and raises alerts. |
| **RAG** | Retrieval-Augmented Generation — retrieve relevant runbook documents and give them to the LLM as context. |
| **Remediation** | The act of applying a fix action to the cluster. |
| **RBAC** | Role-based access control — admin / engineer / viewer. |
| **Runbook** | A recipe for solving a known kind of problem. |
| **Safety gate** | The policy check that decides whether an action runs automatically. |
| **Severity** | The four-level importance classification of an incident (SEV-1 worst). |
| **Webhook** | An HTTP callback; here, the way AlertManager delivers alerts to Klarnova. |
| **Whitelist** | The five actions Klarnova is ever allowed to perform. |

---

## 12. Where to go next

- **Run it yourself:** follow the quick-start in the [README](../README.md) (local dev,
  docker-compose, or the minikube + Sock Shop path).
- **See it working:** the [walkthrough](walkthrough.md) is a guided demo of the exact
  crash-loop scenario narrated in this guide.
- **Read the code:** start with `backend/app/main.py` and `backend/app/agents/graph.py`
  — together they are the wiring diagram of everything above.
- **Formal documentation:** [architecture](Klarnova_Technical_Architecture.md),
  [API reference](api-reference.md), [evaluation](evaluation.md).
