# Onyx Jarvis UI

## Layout

- **Header** — mode toggle (Paper / Live), wallet SOL, stream health
- **Agent rail** — Scout, Safety, Copy, Research, Scorer, Executor, Learner
- **Center** — selected mint chart (bonding curve), Onyx orb, agent timeline
- **Signal feed** — live mints, blocks, fills, fomo convergence
- **Chat bar** — voice + text commands to Onyx

## WebSocket events

See `apps/orchestrator/orchestrator/ws/events.py` for `OnyxEvent` schema.

## Visual language

Dark glass, cyan primary, violet accents, animated agent pulses on `agent.start` / `agent.done`.
