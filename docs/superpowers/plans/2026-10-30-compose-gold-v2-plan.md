# Compose Gold CSV v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Start PostgreSQL, run Alembic and import the selected Gold CSV v2 export, then start the backend in the same Compose invocation.

**Architecture:** Add a separate Compose overlay with a one-shot `gold-loader` service. It waits for the database, migrates and imports through the existing CLI; the backend waits for successful completion. Mount the local export read-only and keep its path in an ignored local env file.

**Tech Stack:** Docker Compose, existing backend image, Alembic, `scripts/load_gold.py`.

**Spec:** Existing loader command and limits in `backend/README.md` and `docs/contracts/gold-csv-v2.md`.

## Global Constraints

- Explicitly select `gold-csv-v2`; keep the v1 schema intact.
- Do not copy the dataset into the image or Git.
- The backend must not start when migration or import fails.
- Keep the default Compose startup unchanged unless the Gold v2 overlay is selected.

## Review Focus

- Missing local export path fails with a clear Compose configuration error.
- Loader waits for PostgreSQL health and completes before backend startup.
- Repeated startup uses the importer's idempotence and does not duplicate data.
- The bind mount is read-only and no database volume is deleted.

### Task 1: Gold v2 Compose startup

**Files:** create `docker-compose.gold-v2.yml` and `.env.gold-v2.example`; create ignored local `.env.gold-v2`; update `backend/README.md` and `.gitignore`.

- [x] Add one-shot loader, dependency ordering and read-only export mount.
- [x] Document local setup, Docker network URL, startup and logs.
- [x] Validate merged Compose configuration without starting services or changing the persistent database.

**Validation:** `docker compose --env-file .env.gold-v2 -f docker-compose.yml -f docker-compose.gold-v2.yml config --quiet` and `git diff --check` pass. The services were not started, so the persistent `pgdata16` volume was not changed.
