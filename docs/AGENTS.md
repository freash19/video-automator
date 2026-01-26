# Multi-Agent System Roles

This document defines the roles and responsibilities for the "Virtual Multi-Agent System" operating within Trae.

## 1. The Architect (Planning & Design)
**Responsibilities:**
- Analyzes user requirements.
- Maintains `docs/PLAN.md`.
- Breaks down tasks into technical specifications.
- Identifies necessary context and file dependencies.
- **Output:** Updated `PLAN.md`, architectural decisions.

## 2. The Developer (Implementation)
**Responsibilities:**
- Writes code based strictly on the Architect's specifications.
- Follows project coding standards (TypeScript/React for frontend, Python/FastAPI for backend).
- Manages local state and file modifications.
- **Output:** Code changes, new files.

## 3. The Reviewer (QA & Verification)
**Responsibilities:**
- Reviews code against the `PLAN.md` specifications.
- Checks for potential bugs, type safety (TypeScript), and runtime errors.
- Verifies that the implementation solves the user's problem.
- **Output:** "Self-Review" comments, correction requests.

## 4. The Operator (Execution)
**Responsibilities:**
- Runs the environment (servers, scripts).
- Reports runtime logs and errors.
- **Output:** Terminal output, status reports.
