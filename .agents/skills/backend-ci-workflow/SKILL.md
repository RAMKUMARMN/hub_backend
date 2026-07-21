---
name: backend-ci-workflow
description: Create a GitHub Actions CI workflow for FastAPI backend with ruff linting, pytest with PostgreSQL service container, type checking, and optional notifications.
metadata:
  model: models/gemini-3.1-pro-preview
  last_modified: Mon, 29 Jun 2026 00:00:00 GMT
---

# Backend CI Workflow

## Contents
- [Workflow Layout](#workflow-layout)
- [Triggers](#triggers)
- [Jobs](#jobs)
- [PostgreSQL Service Container](#postgresql-service-container)
- [Dependency Caching](#dependency-caching)
- [Required Secrets](#required-secrets)

## Workflow Layout

```
.github/workflows/
└── backend-ci.yml
```

## Triggers

```yaml
name: Backend CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  workflow_dispatch:
```

## Jobs

| Job | Command | Purpose |
|---|---|---|
| `lint` | `ruff check .` | Python linting |
| `typecheck` | `mypy .` | Static type checking |
| `test` | `pytest -q` | FastAPI endpoint tests with PostgreSQL container |

### Example workflow

```yaml
name: Backend CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: "pip"
      - run: pip install -r requirements.txt
      - run: ruff check .

  typecheck:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: "pip"
      - run: pip install -r requirements.txt
      - run: mypy .

  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_DB: hub_test
          POSTGRES_USER: hub
          POSTGRES_PASSWORD: hub
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: "pip"
      - run: pip install -r requirements.txt
      - run: pytest -q
        env:
          DATABASE_URL: postgresql+asyncpg://hub:hub@localhost:5432/hub_test
```

## PostgreSQL Service Container

The test job runs a PostgreSQL container as a service. Tests use `DATABASE_URL` pointing to the service container:

```yaml
services:
  postgres:
    image: postgres:16
    env:
      POSTGRES_DB: hub_test
      POSTGRES_USER: hub
      POSTGRES_PASSWORD: hub
    ports:
      - 5432:5432
```

## Dependency Caching

```yaml
- uses: actions/setup-python@v5
  with:
    python-version: "3.11"
    cache: "pip"
```

## Required Secrets

| Secret | Description |
|---|---|
| `DATABASE_URL` | Database connection string for production |
| `SECRET_KEY` | JWT signing secret |
| `SLACK_WEBHOOK_URL` | Slack webhook for failure notifications (optional) |
