# Klarnova_PRD

KLARNOVA

Product Requirements Document

A Plug-and-Play, AI-Powered AIOps Platform for Kubernetes

Autonomous Incident Response using Multi-Agent AI and Retrieval-Augmented Generation (RAG)

Final Year BE Project  Â·  Version 1.0  Â·  2026

1.  Product Overview

Klarnova is a standalone, plug-and-play AIOps platform for Kubernetes. It installs into an existing cluster with a single Helm command, automatically discovers the clusterâ€™s resources and observability tools, and begins monitoring immediately â€” without extensive manual configuration. Once running, it acts as an intelligent operations assistant that continuously watches the cluster, investigates incidents when they occur, reasons about their root cause, and safely executes or recommends corrective action under human-governed safety policies.

Because Klarnova reasons at the Kubernetes infrastructure layer â€” pods, deployments, metrics, and events â€” rather than inside any single application, it works with any containerised workload running on the cluster: web services, APIs, data pipelines, or batch jobs alike. Infrastructure-level detection and remediation are application-agnostic; application-level root-cause depth scales with the quality of each workloadâ€™s own logging.

Two properties define the product. First, it is standalone â€” a complete platform in its own right, not a plugin dependent on a host tool. Second, it is plug-and-play â€” an Auto-Discovery and Auto-Configuration module detects Prometheus, the Kubernetes API, and other observability services and wires them up on install, so time-to-value is minutes rather than days.

Unlike conventional monitoring tools that stop at raising an alert, Klarnova closes the loop. A team of specialised AI agents, orchestrated as a LangGraph state machine, collaborates to move an incident from detection through diagnosis, remediation, and post-fix validation. The platform learns in two complementary ways: every resolved incident is recorded back into a knowledge base to enrich future retrieval, and a contextual bandit adjusts which remediation actions it prefers based on their observed success â€” so decision quality improves with use.

What we are building

A standalone backend service exposing a REST API, driven by a nine-agent pipeline (Monitoring, Investigation, Retrieval, Root Cause, Planning, Safety, Remediation, Validation, Reporting), working with any containerised workload on the cluster.

An Auto-Discovery & Auto-Configuration module that runs before monitoring begins â€” detecting available Kubernetes resources and observability endpoints (Prometheus, Loki if present) and establishing connections automatically, with manual override for non-standard setups.

A continuously-refreshed Retrieval-Augmented Generation layer: runbooks and documentation are ingested from live source URLs on a schedule, re-embedded into a vector database (ChromaDB), and kept current â€” while incident-time retrieval stays fast and resilient to source outages.

A policy-gated remediation engine, augmented by a contextual-bandit action-selection layer that re-ranks candidate actions by learned reward before the safety gate â€” never overriding it.

An operator-facing web dashboard for incident review, agent-reasoning traces, approvals, and analytics.

A cloud-portable deployment: developed on local Kubernetes and validated on a managed cloud cluster in the final phase, cloud-provider-agnostic through exclusive use of the standard Kubernetes API. One-command Helm install, native Alertmanager webhook integration, and an optional kubectl plugin.

What we are explicitly not building

Scope is bounded so the system can be built, evaluated, and demonstrated end-to-end within six months. Auto-discovery targets standard, conventionally-deployed observability services â€” it is not a claim of zero-configuration support for every possible cluster topology, and non-standard setups fall back to explicit configuration. The adaptive layer is a single-step contextual bandit, not full sequential reinforcement learning, and it only re-ranks actions the safety policy already permits. Klarnova does not write or modify application source code, does not operate fully autonomously without human oversight, does not replace existing monitoring tools, and does not function as a security or infrastructure-provisioning system. These boundaries are treated as first-class product decisions, not omissions.

2.  The Problem

Modern organisations run hundreds of microservices across thousands of containers. Kubernetes provides orchestration and resilience, but managing these environments generates an overwhelming volume of metrics, logs, and events. Existing tools detect abnormal behaviour and raise alerts â€” yet the entire investigation, decision, and recovery process still depends on human engineers.

Three gaps that drive cost

Gap

Consequence

Detection is not diagnosis

An alert reports that CPU spiked or a pod restarted, but not why. Engineers must manually correlate logs, metrics, and events before acting.

Knowledge stays siloed

Runbooks, postmortems, and past fixes are scattered across systems nobody searches under pressure. Expertise leaves when engineers leave.

Humans execute every step

Even routine, well-understood fixes require an engineer to run every command by hand, inflating Mean Time to Resolve and causing alert fatigue.

Net effect: high Mean Time to Detect (MTTD), high Mean Time to Resolve (MTTR), alert fatigue, dependence on scarce senior engineers, and repeated re-solving of problems the organisation has already solved before.

Why now

The industry is shifting from DevOps toward AIOps â€” from tools that observe infrastructure to systems that understand, reason about, and act on it. Advances in agentic AI, large language models, and retrieval-augmented generation make it feasible to ground automated reasoning in an organisationâ€™s own operational knowledge. Klarnova targets this shift directly.

3.  Who We Are Building For

Klarnova serves the operational teams responsible for the reliability, availability, and performance of Kubernetes-based production environments â€” not general application developers or end users.

User

What Klarnova does for them

DevOps Engineers

Primary users. Automates investigation and routine remediation so they can focus on delivery instead of repetitive troubleshooting.

Site Reliability Engineers

Reduces MTTD and MTTR, validates recovery actions, and surfaces reliability analytics and recurring-failure trends.

Platform & Cloud Infra Teams

Automates routine operations across clusters while keeping centralised operational visibility and control.

IT Operations Teams

Provides incident dashboards, audit trails, and policy-controlled automation for governance at scale.

System Administrators

Configure remediation policies, manage role-based access, and supervise AI-assisted activity.

Primary persona: a DevOps / SRE engineer on call, who needs an incident triaged and a safe fix proposed in seconds â€” with enough explanation and evidence to trust or override it.

4.  Features

Features are grouped into a Minimum Viable Product â€” the committed six-month build â€” and clearly separated future extensions.

4.1  Core features (MVP â€” committed)

Feature

Description

Plug-and-play deployment

Single Helm install; Auto-Discovery module detects the Kubernetes API, Prometheus, and Loki (if present) and self-configures, with fallback config for non-standard setups.

Continuous monitoring

Always-on ingestion from Prometheus and the Kubernetes API; detects anomalies against defined rules.

Automated investigation

On incident, gathers logs (including previous-container logs), metrics, events, pod state, and deployment history without manual effort.

Severity & priority classification

Each incident is labelled SEV-1 to SEV-4 with a matching P1â€“P4 priority, giving operators an at-a-glance sense of urgency and feeding severity into the risk-assessment decision.

Live-refreshed RAG retrieval

Runbooks and documentation are ingested from live source URLs on a schedule and re-embedded into the vector database, so analysis uses current data; incident-time retrieval stays fast and offline.

AI root cause analysis

LLM reasoning over live evidence plus retrieved precedent, producing an explanation and confidence score â€” not just a symptom.

Adaptive action selection

A contextual bandit re-ranks candidate remediation actions by their observed success for similar incidents, improving choices over time â€” always within the safety policyâ€™s approved set.

Policy-gated remediation

Executes low-risk actions (restart, scale, rollback, delete pod, cordon node) automatically; routes high-risk actions to human approval, with severity influencing the risk decision.

Post-fix validation

Re-checks live health after every action; retries an alternative or escalates if the incident persists. The outcome also feeds the contextual bandit as a reward signal.

Incident reporting

Auto-generates a record with root cause, evidence, action, outcome, and confidence; feeds it back into the knowledge base.

Operator dashboard

Live incident feed, agent-reasoning trace, approval workflow, historical reports, and MTTD/MTTR analytics.

Auth & RBAC

JWT authentication with three roles (Admin, Engineer, Viewer); cluster actions run through a scoped Kubernetes ServiceAccount.

Cloud-portable deployment

Developed on local Kubernetes and validated on a managed cloud cluster (EKS / AKS / GKE) in the final phase; provider-agnostic via the standard Kubernetes API.

Escalation

Notifies via Slack/email on high severity or failed remediation.

4.2  Future extensions (out of committed scope)

kubectl plugin â€” on-demand diagnosis (e.g. kubectl klarnova diagnose <pod>) as a thin client of the same API. Low effort, planned for Month 6 if time allows.

Enterprise distribution â€” Kubernetes Operator, Grafana / VS Code plugins, Slack bot, and multi-cluster SaaS, mapped as a phased productisation roadmap.

Predictive failure detection â€” anticipating incidents before they occur, and extension of the single-step bandit toward sequential planning if incident response is redesigned as a multi-step problem.

4.3  Severity and priority reference

Every incident is classified on a severity scale with a matching priority label, giving operators an immediate, human-readable sense of urgency. Severity is also an input to the risk-assessment decision â€” the same remediation action may be auto-approved at low severity yet require human sign-off at high severity, because blast radius depends on how critical the affected service is.

Severity

Priority

Meaning

Default handling

SEV-1 Critical

P1

Service down or customer-facing outage

Human approval always required

SEV-2 High

P2

Major degradation, not a full outage

Auto-remediate low-risk only, else approval

SEV-3 Medium

P3

Partial or localised issue

Auto-remediation permitted per policy

SEV-4 Low

P4

Minor or non-urgent

Auto-remediation permitted

5.  Success Metrics

Success is measured against a baseline of manual investigation and simple threshold-based automation, running the same injected failure scenarios. Metrics fall into three groups.

5.1  Operational performance

Metric

What it measures

Target direction

Mean Time to Detect

Time from failure to detection

Substantial reduction vs. baseline

Mean Time to Resolve

Time from detection to validated fix

Substantial reduction vs. baseline

Remediation success rate

Fixes validated as healthy first attempt

High, with honest reporting

Escalation rate

Incidents routed to humans

Appropriate, not zero

Time-to-first-monitor

Helm install to active monitoring on a standard cluster

Minutes, minimal manual config

Note on the escalation target: a zero escalation rate is not the goal. Correctly escalating incidents that fall outside the safe-action boundary is a sign the safety model works, not a failure.

5.2  Diagnostic quality

Root cause accuracy â€” proportion of incidents where the identified cause matches ground truth from the chaos-injection scenario.

Retrieval relevance â€” whether the RAG layer surfaces the genuinely applicable runbook or past incident.

Explainability â€” every recommendation carries a root cause, supporting evidence, confidence score, and cited precedent.

5.3  Ablation â€” does each component earn its place

Each major component is disabled in turn and the same scenario set re-run. The resulting change in MTTR and success rate quantifies each agentâ€™s contribution rather than asserting it â€” with inconclusive results reported honestly rather than omitted.

Configuration

Question it answers

Full system

Baseline for the complete pipeline

Without RAG retrieval

How much does grounded precedent improve diagnosis?

Without Validation Agent

How many failed fixes would go unnoticed?

Without Safety Agent

What is the risk cost of removing the policy gate?

Without Planning separation

Does separating planning from reasoning improve action choice?

Without contextual bandit

Does learned action-ranking improve remediation success over static selection?

Project-level definition of done: a working end-to-end system that detects, diagnoses, remediates, and validates real injected failures on a live cluster; a functional operator dashboard; and a documented evaluation with a baseline comparison and an ablation study.
