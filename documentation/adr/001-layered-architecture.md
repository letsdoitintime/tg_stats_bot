# ADR-001: Layered Architecture Pattern

**Status**: Accepted

**Date**: 2024-12-15

## Context

The Telegram Stats Bot needs a clear separation of concerns to:
- Make the codebase maintainable and testable
- Enable independent development of different layers
- Support future scaling and evolution
- Provide clear boundaries for different responsibilities

We needed to choose an architectural pattern that would provide structure while remaining flexible enough for a bot application with analytics, webhooks, and background tasks.

## Decision

We adopt a **layered architecture** with the following layers:

```
┌─────────────────────────────────────┐
│        Handlers Layer               │  (Telegram updates, API endpoints)
├─────────────────────────────────────┤
│        Services Layer               │  (Business logic)
├─────────────────────────────────────┤
│        Repositories Layer           │  (Data access)
├─────────────────────────────────────┤
│        Models Layer                 │  (Database entities)
└─────────────────────────────────────┘
```

### Layer Responsibilities

1. **Handlers Layer** (`tgstats/handlers/`, `tgstats/web/`)
   - Receive Telegram updates and HTTP requests
   - Extract and validate input
   - Call appropriate services
   - Format and return responses
   - Should NOT contain business logic

2. **Services Layer** (`tgstats/services/`)
   - Implement business logic
   - Orchestrate multiple repositories
   - Handle transactions
   - Apply business rules
   - Should NOT know about Telegram or HTTP

3. **Repositories Layer** (`tgstats/repositories/`)
   - Implement data access patterns
   - Execute queries
   - Handle ORM operations
   - Should NOT contain business logic

4. **Models Layer** (`tgstats/models.py`)
   - Define database schema
   - ORM mappings
   - Basic relationships

### Key Principles

- **Dependency Rule**: Dependencies flow downward (Handlers → Services → Repositories → Models)
- **Single Responsibility**: Each layer has one reason to change
- **Dependency Injection**: Pass dependencies through constructors
- **No Skip**: Layers don't skip levels (handlers don't call repositories directly)

## Consequences

### Positive

- **Testability**: Each layer can be tested in isolation with mocks
- **Maintainability**: Changes in one layer don't cascade unnecessarily
- **Clear Boundaries**: Developers know where to put code
- **Reusability**: Services can be used by both bot handlers and API endpoints
- **Flexibility**: Easy to swap implementations (e.g., different data sources)

### Negative

- **More Files**: More boilerplate and structure overhead
- **Indirection**: Simple operations require going through multiple layers
- **Learning Curve**: New developers need to understand the pattern
- **Potential Over-engineering**: Some simple features might not need all layers

### Neutral

- **Transaction Management**: Handled via decorators and service layer
- **Error Handling**: Each layer handles its own error types
- **Logging**: Each layer logs at appropriate level

## Alternatives Considered

1. **Flat Structure**: All code in handlers
   - Rejected: Poor separation of concerns, hard to test

2. **Vertical Slices**: Feature-based organization
   - Rejected: Less clear for shared functionality

3. **Hexagonal Architecture**: Ports and adapters
   - Rejected: Too complex for current needs

## References

- [Clean Architecture by Robert C. Martin](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
- [Layered Architecture Pattern](https://www.oreilly.com/library/view/software-architecture-patterns/9781491971437/ch01.html)
