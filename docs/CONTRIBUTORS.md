# Klarnova — Contributors & Working Agreement

Project conventions, team expectations, and the branching model.
Final Year BE Project · Version 1.0 · 2026

---

## 1. Purpose

Klarnova is built by a team over six months. This file captures the shared working agreement so
everyone lands the same way: same conventions, same review bar, same definition of done.
Every teammate must have a first commit on `main` (KLR-A1) to prove the toolchain works.

---

## 2. Team & Rotations

- Work in pairs per epic; rotate weekly so knowledge does not concentrate in one person
  (matters for the viva).
- One person per week owns integration: everything merged that week must run end-to-end.
- Keep the backlog `blocked` column honest — a ticket blocked for more than a day is a standup topic.

---

## 3. Branching Model

We use a lightweight, trunk-based workflow with short-lived branches and pull-request review.

### 3.1 Branches

| Branch | Lifecycle | Rule |
|--------|-----------|------|
| `main` | Permanent | Always deployable. Every commit passes CI. Protected. |
| `feat/<epic>-<ticket>` | Short-lived | One feature branch per ticket, e.g. `feat/a3-agent-state` |
| `fix/<epic>-<ticket>` | Short-lived | Bug fixes, e.g. `fix/c4-webhook-token` |
| `chore/<ticket>` | Short-lived | Docs, CI, tooling |

### 3.2 Rules

1. **Never push to `main` directly.** Work in a feature branch; merge via pull request.
2. **Branch from current `main`** and keep it rebased so merge conflicts stay small.
3. **One ticket per branch** where practical — keeps review and history coherent.
4. **PR requires at least one review** and a passing CI (lint + tests, KLR-A9).
5. **Delete the branch after merge.**
6. **First commit on `main`** for each teammate may be a trivial `chore` PR that proves access
   and toolchain; after that, all work flows through branches.

### 3.3 Commit messages

Use Conventional Commits so the log stays greppable and release notes are easy to write.

```
feat(agents): add Monitoring Agent poll loop
fix(webhooks): validate alertmanager token before creating incident
docs(api): document /events SSE schema
test(rag): add retrieval threshold unit tests
chore(ci): pin backend and frontend versions at kickoff
```

### 3.4 Definition of done (per ticket)

- Code merged via reviewed PR with passing CI.
- Tests cover the ticket's core behaviour (unit; integration where it touches a boundary).
- `make dev` still boots the full stack (integration owner verifies weekly).
- No secrets, no `.env`, no real credentials in the diff.
- Ticket marked `done` in the backlog; `review` while the PR is open.

---

## 4. Reproducibility Rule

A new team member must be able to: clone the repo → copy `.env.example` to `.env` → fill in
secrets → run `make dev` → get the full local stack up. Every deviation from this is
configuration debt to fix, not work around (Architecture doc §6).

---

## 5. Version Pin Discipline

Versions are pinned at kickoff (`requirements.txt`, `package-lock.json`) and held fixed for the
duration of the project. Upgrades are deliberate, reviewed, and recorded. (Architecture doc §2, §6.)

---

## 6. Code of Conduct

- Treat every teammate's work as a shared asset: review kindly, critique the code not the person.
- Ask before refactoring another person's in-flight epic area.
- Log progress honestly in tickets; a blocked ticket is normal, a hidden one is not.
- Rotate roles so everyone can answer every question about the system at the viva.

---

## 7. Contributor List

> Populate at kickoff (KLR-A1). Each entry needs name, role, primary epic areas, and a first
> commit on `main`.

| Name | Role | Primary epic areas | First commit on `main` |
|------|------|--------------------|------------------------|
| | | | |
| | | | |
| | | | |
