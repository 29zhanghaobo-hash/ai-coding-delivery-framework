# Extension Specification

Extensions allow the framework to support different project types without forcing unnecessary complexity.

## Core Principle

Core framework stays minimal.
Project complexity is introduced only through extensions.

## Example Extensions

- frontend
- backend
- fullstack
- multi-repo
- plugin-system
- agent-runtime
- cross-team-dependency
- cui-gui

## Loading Rules

1. Read project-profile.md
2. Detect enabled capabilities
3. Load only matching extensions
4. Ignore unsupported extensions

## Goal

Allow the framework to scale from simple frontend projects to complex AI-integrated systems.
