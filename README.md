# copilot-custom-agents-demo

A demo Python Flask REST API used to explore **GitHub Copilot CLI custom agents**.

## Purpose

This repo is intentionally imperfect — it has missing tests, no docstrings, security issues, and refactoring opportunities — so you can use Copilot CLI custom agents to improve it step by step.

## Project structure

```
app/
  models/       # SQLAlchemy models (User, Product)
  routes/       # Flask blueprints (users, products)
  db.py         # SQLAlchemy instance
  __init__.py   # App factory
tests/          # Empty — let the test-writer agent fill this
.github/
  agents/       # Custom agent profiles
    security-audit.md
    test-writer.md
    docstring.md
    refactor.md
run.py          # Entry point
requirements.txt
```

## Setup

```bash
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

## Custom agents

Use Copilot CLI to invoke agents:

```
/agent
```

Or directly in your prompt:

```
Use the security-audit agent to review the codebase
Use the test-writer agent to write tests for the products routes
Use the docstring agent to document all functions
Use the refactor agent to improve code quality
```
