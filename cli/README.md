# kubectl-klarnova

A [kubectl plugin](https://kubernetes.io/docs/tasks/extend-kubectl/kubectl-plugins/)
for Klarnova incident response. Zero dependencies — pure Python 3.8+ standard
library (stdlib `urllib`).

It talks to the Klarnova backend REST API, so you can triage incidents from
your terminal exactly like the web dashboard.

## Install

kubectl discovers plugins named `kubectl-<name>` on your `PATH`:

```bash
chmod +x cli/kubectl-klarnova
export PATH="$PWD/cli:$PATH"

kubectl klarnova --help
```

Windows: run it via `python cli/kubectl-klarnova <args>` (kubectl plugin
discovery also works with the file on `PATH` when Python is your file
association).

## Configure

| Config        | Source (priority order)                                   |
| ------------- | --------------------------------------------------------- |
| API base URL  | `--api`, `KLR_API`, `~/.klarnova` (cached), `http://localhost:8000` |
| Token         | `--token`, `KLR_TOKEN`, `~/.klarnova` (cached by `login`) |

## Usage

```bash
# One-time auth (caches the token in ~/.klarnova)
kubectl klarnova login --username admin          # prompts for password

# Incident summary
kubectl klarnova status

# List incidents (optional --status, --limit)
kubectl klarnova incidents list
kubectl klarnova incidents list --status "Awaiting Approval"

# Detail + agent trace
kubectl klarnova incidents show 17

# Approve / reject the proposed remediation (role-gated server-side)
kubectl klarnova incidents approve 17
kubectl klarnova incidents reject 17
```

The approve/reject commands reuse the same `/v1/actions/approve` endpoint as
the dashboard, so the same RBAC rules apply (admin/engineer only).
