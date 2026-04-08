---
title: Hospital Resource Management
emoji: 🏥
colorFrom: blue
colorTo: green
sdk: docker
pinned: false
app_port: 8000
---

# Hospital Resource Management — OpenEnv

An OpenEnv environment for AI agents to manage hospital operations: bed allocation, staff management, equipment distribution, and patient flow under resource constraints.

**Team:** Ignitors  
**Version:** 1.0.0

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/reset` | Initialize environment: `{"task": "easy"}` |
| `POST` | `/step` | Execute action |
| `GET`  | `/state` | Get current state |
| `POST` | `/grade` | Grade current task |
| `GET`  | `/health` | Health check |

## Tasks: `easy` · `medium` · `hard`
