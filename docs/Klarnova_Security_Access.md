# Klarnova_Security_Access

KLARNOVA

Security & Access Control Document

Access model, authentication, data protection, and failure handling

A Plug-and-Play, AI-Powered AIOps Platform for Kubernetes

Final Year BE Project  Â·  Version 1.0  Â·  2026

1.  Security Model Overview

Klarnova operates on live production infrastructure and can execute actions that change cluster state. Its security model is therefore built on a single guiding principle: authority is layered, least-privileged, and human-governed at every point where an action could cause harm.

Security is enforced at four boundaries, each independent so that a weakness at one does not compromise the others.

Boundary

What it protects

User â†’ Platform

Who may sign in and what they may do, via authentication and role-based access control.

Platform â†’ Cluster

What Klarnova itself may do to Kubernetes, via a scoped ServiceAccount and least-privilege RBAC.

Action governance

Which remediations execute automatically vs. require human approval, via the severity-aware policy engine.

Data protection

How data at rest, in transit, and in transient stores is secured, including secrets and audit trails.

2.  Who Can Access What

Access follows Role-Based Access Control (RBAC) with three roles, aligned to real operational responsibilities. A user has exactly one role; permissions are cumulative from Viewer upward.

2.1  Roles and permissions

Role

Permissions

Viewer

Read-only. May view incidents, root-cause analyses, agent traces, reports, and analytics. Cannot approve actions, trigger remediation, or change configuration.

Engineer

All Viewer rights, plus: trigger investigation, approve or reject remediation actions surfaced for sign-off, and manually invoke on-demand diagnosis. Cannot alter policies, manage users, or change system settings.

Admin

All Engineer rights, plus: configure remediation and risk policies, manage users and roles, adjust system settings, and manage knowledge-base sources.

2.2  Permission matrix

Capability

Viewer

Engineer

Admin

View incidents, reports, analytics

Yes

Yes

Yes

View agent reasoning traces

Yes

Yes

Yes

Trigger on-demand diagnosis

No

Yes

Yes

Approve / reject remediation

No

Yes

Yes

Manually trigger remediation

No

Yes

Yes

Configure risk / remediation policies

No

No

Yes

Manage users and roles

No

No

Yes

Manage knowledge-base sources

No

No

Yes

Change system settings

No

No

Yes

Severity interacts with role: even an Engineerâ€™s approval authority is bounded by the policy engine. A SEV-1 (P1) critical incident always requires explicit human approval before any action, regardless of how confident the AI is â€” no role and no confidence score can auto-execute against a critical, customer-facing outage.

3.  How Access Is Granted and Enforced

3.1  User authentication

Users authenticate to the platform with credentials, receiving a signed JSON Web Token (JWT) on success. Every subsequent API request carries this token; the backend validates its signature and expiry before processing, and derives the userâ€™s role from its claims.

Passwords are never stored in plaintext â€” they are hashed with a strong one-way algorithm (bcrypt) with per-user salt.

Tokens are short-lived and signed with a secret held only on the server; a tampered or expired token is rejected outright.

Role is read from the validated token on every request, so a user cannot escalate privileges by modifying client-side state.

3.2  Authorisation on every request

Authentication answers â€œwho are youâ€; authorisation answers â€œmay you do thisâ€. Both run on every protected endpoint. A request that is authenticated but lacks the required role is refused with an authorisation error â€” the action is never partially performed.

3.3  How Klarnova accesses the cluster

Klarnova does not use a humanâ€™s credentials to act on Kubernetes. It runs under a dedicated ServiceAccount bound to a narrowly scoped ClusterRole. The role grants only the specific verbs its remediation actions require â€” nothing more.

Resource

Permitted verbs

pods

get, list, watch, delete (restart via delete-and-reschedule)

deployments

get, list, watch, patch (scale and rollback)

nodes

get, list, watch, patch (cordon)

events

get, list, watch (read-only, for investigation)

pods/log

get (read logs, including previous-container logs)

This is a hard ceiling, not a guideline: even a bug in the Remediation Agent, a bad LLM suggestion, or a compromised process cannot perform an action outside this set, because the Kubernetes API server itself enforces the boundary. Klarnova has no permission to delete deployments, modify secrets, alter RBAC, or touch resources outside its target namespaces.

3.4  Secrets and credentials

Secrets (LLM API keys, JWT signing secret, database credentials, webhook tokens) are supplied through environment variables locally and Kubernetes Secrets in-cluster â€” never committed to the repository.

A committed .env.example documents every required variable by name only, with no real values.

The Alertmanager webhook endpoint is protected by a shared token, so only the clusterâ€™s own Alertmanager can post incidents to Klarnova.

4.  How Data Security Is Handled

Klarnova handles operational data (metrics, logs, incidents), organisational knowledge (runbooks), and sensitive material (credentials, tokens). Each is protected according to its sensitivity across three states: in transit, at rest, and in transient stores.

4.1  Data in transit

All API traffic between the dashboard, the backend, and external services is served over TLS, so data cannot be read or altered on the wire.

Sensitive values are never placed in URLs or query strings â€” only in request bodies or secure headers â€” so they do not leak into logs or browser history.

4.2  Data at rest

Store

Protection

PostgreSQL

Structured records (incidents, audit, users, policies). Credentials are hashed; access is restricted to the backend service account. Database is not exposed publicly.

ChromaDB

Embedded knowledge only â€” public runbooks and documentation, no secrets. Reachable only from within the platform.

Redis

Transient cache and queue data with short lifetimes; holds no long-term sensitive data.

Kubernetes Secrets

API keys and credentials, stored as Secrets and mounted into the pod at runtime rather than baked into images.

4.3  The audit trail

Every security-relevant event is recorded to an append-only audit log: who (or which agent) did what, when, and with what outcome.

User events â€” sign-in, approval or rejection of an action, policy or configuration changes.

Agent events â€” incident detection, knowledge retrieved, recommendation made with confidence score, action executed, validation result.

The audit trail serves two purposes: accountability (every automated action is attributable and reviewable after the fact) and forensics (if an action had an unexpected effect, the full decision chain that led to it can be reconstructed).

4.4  Sensitivity of AI inputs

Logs and metrics sent to an LLM for reasoning may contain operational detail. When the cloud LLM provider is used, this data leaves the cluster. The platform therefore offers a local-model path (via Ollama) so that, where data residency matters, reasoning can run entirely in-cluster with no external transmission â€” a deployment-time choice, not a code change.

5.  How the System Reacts When Something Goes Wrong

Klarnova is designed to fail safe: when a component is uncertain, degraded, or unavailable, the system defaults to caution â€” doing less, not more â€” and surfaces the problem to a human rather than proceeding blindly.

5.1  Component failures

If this failsâ€¦

What happens

Why it is safe

LLM (cloud) unavailable

Fall back to the local model, or if reasoning cannot proceed, halt at diagnosis and escalate to a human.

No remediation is attempted on a guess; a human takes over investigation.

Vector DB unavailable

Root-cause reasoning proceeds without retrieved precedent, with lowered confidence; retrieval-dependent steps are skipped, not faked.

Degraded, not wrong â€” the system does not fabricate precedent it could not retrieve.

Kubernetes API unreachable

Remediation cannot execute; the incident is flagged and escalated.

The platform cannot act blindly on a cluster it cannot read.

Prometheus / metrics missing

Detection and validation degrade; affected incidents are escalated rather than auto-resolved.

A fix cannot be validated without health data, so it is not declared resolved.

Database unavailable

The platform enters a read-limited state and stops accepting actions that require durable record-keeping.

No action is taken that could not be audited.

5.2  When remediation itself fails

If the Validation Agent finds that an executed action did not resolve the incident, the system does not silently mark it done. It follows a bounded retry-then-escalate path:

The outcome is recorded (and fed to the contextual bandit as a negative reward for that action in that context).

Control returns to the Planning Agent, which may propose an alternative action â€” subject to the same risk gate.

Retries are bounded. After a small, fixed number of failed attempts, the system stops trying and escalates to a human engineer with the full history rather than looping indefinitely.

5.3  When the AI is uncertain

Confidence is a first-class safety control. Every diagnosis carries a confidence score; if it falls below a configured threshold, the action is routed to a human regardless of the actionâ€™s risk tier. Combined with severity gating (SEV-1 always requires approval), this means the system escalates precisely when it should: when the stakes are high or the certainty is low.

5.4  Guarding against malicious or malformed input

Instructions found inside observed data â€” logs, events, retrieved documents â€” are treated as data, never as commands. The system does not execute actions requested by content it merely read.

LLM output is advisory: recommended actions are mapped to a fixed safe-action whitelist before anything executes. An action the LLM invents that is not on the whitelist simply cannot run.

The webhook endpoint is token-protected, so a forged incident cannot be injected by an unauthenticated caller.

5.5  Fail-safe summary

Situation

Default behaviour

Uncertain diagnosis

Escalate to human

High-severity incident

Require human approval

Missing or degraded data

Escalate, do not auto-resolve

Repeated remediation failure

Stop after bounded retries, escalate

Unknown or non-whitelisted action

Refuse to execute

Dependency outage

Degrade gracefully, never act blindly

The unifying rule: Klarnova is built so that the failure mode is always caution. It would rather escalate an incident it could have handled than act on one it should not have. Doing too little is recoverable; acting wrongly on production infrastructure may not be.
