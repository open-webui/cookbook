# Introducing Terminals: Per-User Sandboxed Environments for Open WebUI Teams

[Open Terminal](https://docs.openwebui.com/features/open-terminal/) gives your AI a real computer to work in, enabling code execution, graph generation, web previews, software development, and more inside Open WebUI. Today we're launching **Terminals**, an orchestration layer that gives every user on your team their own isolated Open Terminal instance.

## What Open Terminal does

Open Terminal connects a real computing environment to Open WebUI. The AI can write code, execute it, read the output, fix errors, and iterate, all without leaving the chat. It handles files, installs packages, runs servers, and returns results directly to you.

It's the difference between an AI that talks about code and one that actually runs it. Upload a spreadsheet and get a finished analysis. Describe a website and see it rendered live. Clone a repo and let the AI debug a failing test suite. Open Terminal makes all of this possible through a sandboxed environment that the AI controls on your behalf, without exposing your users' local computers to an agent with a risky amount of control over their local environment.

For a single user or a small trusted team, this works great out of the box. But what happens when you need to scale it to dozens or hundreds of users?

## The scaling problem

Open Terminal includes a [built-in multi-user mode](https://docs.openwebui.com/features/open-terminal/advanced/multi-user) that works well for small teams. Each person gets their own files, but everyone shares the same container: the same CPU, memory, network, and system processes.

This creates problems as you grow. One user running a heavy computation slows everyone else down. There's no way to set per-user resource limits. You can't offer different environments to different teams. The data science group and the interns all get the same setup. And every user on the system shares network access, which makes isolation for untrusted users impossible.

For a handful of trusted colleagues, shared infrastructure is fine. For production deployments, larger organizations, or any situation where users shouldn't have visibility into each other's work, you need something more.

## Terminals: one container per user

[Terminals](https://docs.openwebui.com/features/open-terminal/terminals/) solves this by provisioning a fully isolated Open Terminal container for every user. Instead of sharing a single environment, each person gets their own, with separate files, processes, resource limits, and network isolation.

Containers are created on demand the first time a user activates a terminal, and automatically cleaned up after a configurable idle timeout (30 minutes is typical). No wasted resources sitting idle. When a user comes back, a fresh container spins up and their persistent storage reattaches, picking up right where they left off.

Users never connect to their container directly. All traffic flows through a central **orchestrator** service that handles provisioning, authentication, and proxying. From the user's perspective, nothing changes. They open a terminal in Open WebUI and start working. From the platform team's perspective, every user is sandboxed.

## The orchestrator

The Terminals orchestrator is the service that makes this work. It sits between Open WebUI and the per-user containers, managing the full lifecycle: provisioning new containers, proxying traffic, running health checks, cleaning up idle instances, and recovering state on restart.

Critically, the orchestrator exposes the same OpenAPI-based tool interface as Open Terminal itself. This means the AI's tool calls (execute a command, read a file, run a script) are transparently routed to the correct user's container. No changes needed to models, prompts, or workflows. If Open Terminal works for you today, Terminals will work the same way, just with isolation underneath.

Authentication is built in. In production, the orchestrator validates JWTs directly against your Open WebUI instance. For simpler setups, a shared API key works too. No tokens to manage manually. The Docker Compose and Helm deployments configure this automatically.

On Kubernetes, a dedicated operator watches Terminal custom resources and manages the underlying infrastructure: Pods, Services, PVCs, and Secrets for each user's terminal. This gives you the full power of Kubernetes lifecycle management: readiness probes, persistent volumes that survive idle cleanup, and declarative state you can inspect with `kubectl`.

## Terminals for teams: policies and access control

Different teams have different needs. A data science group wants a beefy environment with heavy libraries like PyTorch and 32 GiB of RAM. An intern cohort should get limited resources with a short idle timeout. A development team needs persistent storage and network access to internal services.

[Policies](https://docs.openwebui.com/features/open-terminal/terminals/policies) make this possible. A policy is a named environment profile that specifies the container image, CPU and memory limits, persistent storage, environment variables, and idle timeout for a group of users. Create a `data-science` policy with 8 CPUs and 32 GiB of RAM. Create an `intern` policy with 1 CPU, 1 GiB of memory, and a 15-minute timeout. Each user gets their own container matching their policy's spec.

Access control ties it together. Each policy maps to a terminal connection in Open WebUI, and each connection can be restricted to specific groups. The engineering team sees only the engineering terminal. The data team sees only theirs. A user in both groups sees both. Admins configure this through Open WebUI's existing group system, so there's no separate access layer to maintain.

For platform administrators who delegate policy creation to team leads, hard caps provide a safety net. Set global maximums on CPU, memory, storage, and allowed container images at the orchestrator level. No matter what a team lead configures in their policy, the orchestrator silently clamps values to stay within bounds.

## Two ways to deploy

Terminals supports two deployment backends, depending on your infrastructure.

**Docker Compose** is the fastest path. A single Compose file deploys Open WebUI and the Terminals orchestrator together. Set an API key, run `docker compose up -d`, and you're running. The orchestrator uses the Docker API to create and manage per-user containers on the same host. Best for small-to-medium teams, quick evaluation, or environments without Kubernetes. [Get started with Docker](https://docs.openwebui.com/features/open-terminal/terminals/#quick-start-with-docker-compose).

**Helm chart** is the more scalable path for production environments. Terminals integrates as a subchart of the Open WebUI Helm chart. Add `terminals.enabled: true` to your values file, and the chart handles everything. It deploys the orchestrator and operator, installs the Terminal CRD, auto-generates API keys, and configures the connection so terminals appear in the UI immediately. No manual wiring. Best for production environments and larger teams already running Kubernetes. [Get started with Helm](https://docs.openwebui.com/features/open-terminal/terminals/#deployment).

Both backends support the same policies, access controls, and orchestrator features. The difference is how containers are managed underneath.

## Get started

Terminals is available now as part of [Open WebUI Enterprise](https://openwebui.com/enterprise).

- [Terminals documentation](https://docs.openwebui.com/features/open-terminal/terminals/): overview, architecture, and deployment guides
- [Policies guide](https://docs.openwebui.com/features/open-terminal/terminals/policies): per-team environments and access control
- [Terminals on GitHub](https://github.com/open-webui/terminals): source and issue tracker

Want to know more about Open WebUI Enterprise and Terminals?

[Contact Enterprise Sales → sales@openwebui.com](mailto:sales@openwebui.com)
