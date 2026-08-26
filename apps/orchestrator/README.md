# Orchestrator

FastAPI service: agent registry, `/api/mode`, `/ws/onyx`, paper wallet.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
uvicorn orchestrator.main:app --reload --port 8787
```
