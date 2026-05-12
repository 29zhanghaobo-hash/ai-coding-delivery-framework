# Boundary Awareness

AI agents must not assume that the visible repository contains the entire system.

## Common Unknown Areas

- External runtimes
- Third-party services
- GUI runtime state
- Cross-team owned systems
- Deployment orchestration
- Infrastructure capabilities

## Rules

1. Explicitly identify unknown areas.
2. Do not make strong assumptions about invisible systems.
3. Separate confirmed facts from inferred assumptions.
4. Expose risks caused by incomplete context.
5. Request clarification only when truly blocking.

## Goal

The framework should help AI make stable decisions even with incomplete information.
