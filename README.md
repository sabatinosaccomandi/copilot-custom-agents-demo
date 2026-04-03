# copilot-custom-agents-demo

A hands-on study repo for learning **GitHub Copilot CLI custom agents**.

## Purpose

This project is a deliberately imperfect Flask REST API used as a playground to explore how Copilot CLI custom agents work. Each session focuses on a different aspect of the agent system — from invoking built-in agents, to defining and testing custom ones, to combining them in multi-step workflows.

The codebase has intentional issues baked in (missing tests, no docstrings, security vulnerabilities, refactoring opportunities) so there is always something meaningful for agents to work on.

## Study plan

| Session | Topic |
|---------|-------|
| ✅ Session 1 | Project setup — scaffold the base Flask API and define custom agent profiles |
| 🔜 Session 2 | Invoke the **security-audit** agent — find and fix security issues |
| 🔜 Session 3 | Invoke the **test-writer** agent — generate a full pytest test suite |
| 🔜 Session 4 | Invoke the **docstring** agent — document the entire codebase |
| 🔜 Session 5 | Invoke the **refactor** agent — improve code structure and quality |
| 🔜 Session 6 | Build the frontend and extend agents to cover full-stack scenarios |
| 🔜 Session 7 | Combine agents in multi-step workflows and explore autopilot mode |

## Project structure

```
backend/
  app/
    models/       # SQLAlchemy models (User, Product)
    routes/       # Flask blueprints (users, products)
    db.py         # SQLAlchemy instance
    __init__.py   # App factory
  tests/          # Empty — the test-writer agent will fill this
  run.py          # Entry point
  requirements.txt
frontend/         # Coming in a future session
.github/
  agents/         # Custom agent profiles
    security-audit.md
    test-writer.md
    docstring.md
    refactor.md
```

## Backend setup

```bash
cd backend
pip install -r requirements.txt
python run.py
```

The API runs at `http://localhost:5000`.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /users/ | List all users |
| GET | /users/\<id\> | Get a user |
| POST | /users/ | Create a user |
| DELETE | /users/\<id\> | Delete a user |
| GET | /users/search?q= | Search users by username |
| GET | /products/ | List all products |
| GET | /products/\<id\> | Get a product |
| POST | /products/ | Create a product |
| PUT | /products/\<id\> | Update a product |
| POST | /products/\<id\>/discount | Apply a discount |

## Using the custom agents

Navigate to the repo in Copilot CLI, then use the `/agent` slash command to browse available agents, or invoke one directly in your prompt:

```
Use the security-audit agent to review the codebase
Use the test-writer agent to write tests for the products routes
Use the docstring agent to document all functions
Use the refactor agent to improve code quality
```
