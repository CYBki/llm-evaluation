# Day 1 Migration Issue Report

## Problem
Alembic migration failed with:

`sqlalchemy.exc.InvalidRequestError: Attribute name 'metadata' is reserved when using the Declarative API.`

The issue was in `app/models/trace.py` where a model attribute was named `metadata`.

## Root Cause
In SQLAlchemy Declarative API, `metadata` is a reserved attribute used by the base model registry.
Using it as a mapped class attribute causes model initialization to fail before migrations run.

## Fix Applied
Updated model field in `app/models/trace.py`:
- Python attribute renamed from `metadata` -> `meta`
- Database column name preserved as `metadata` via:
  - `mapped_column("metadata", JSONB, nullable=True)`

This keeps DB schema compatibility while removing ORM conflict.

## Validation
1. Re-ran migration command:
   - `alembic upgrade head`
2. Confirmed created tables:
   - `users`
   - `traces`
   - `evaluation_results`
   - `alembic_version`

## Status
Resolved ✅
