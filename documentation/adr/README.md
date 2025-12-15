# Architecture Decision Records (ADRs)

This directory contains Architecture Decision Records (ADRs) for the Telegram Stats Bot project.

## What is an ADR?

An Architecture Decision Record (ADR) is a document that captures an important architectural decision made along with its context and consequences.

## ADR Format

Each ADR should include:

1. **Title**: Short descriptive title
2. **Status**: Proposed | Accepted | Deprecated | Superseded
3. **Context**: What is the issue we're seeing that is motivating this decision?
4. **Decision**: What is the change that we're proposing/doing?
5. **Consequences**: What becomes easier or more difficult to do because of this change?

## ADR List

1. [ADR-001: Layered Architecture Pattern](./001-layered-architecture.md)
2. [ADR-002: Repository Pattern for Data Access](./002-repository-pattern.md)
3. [ADR-003: Service Factory Pattern](./003-service-factory.md)
4. [ADR-004: Decorator-based Session Management](./004-decorator-sessions.md)
5. [ADR-005: Plugin System Architecture](./005-plugin-system.md)
6. [ADR-006: TimescaleDB with PostgreSQL Fallback](./006-timescaledb-fallback.md)

## Creating a New ADR

1. Copy the template: `cp template.md XXX-your-title.md`
2. Fill in the sections
3. Update this README with a link to your ADR
4. Submit for review
