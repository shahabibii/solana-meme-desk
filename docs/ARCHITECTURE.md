# Architecture

## Flow

```
PumpPortal / fomo (Cope) → Scout → Safety → Copy/Research → Scorer → Executor → Monitor → Learner
                                      ↓
                              WebSocket → Onyx HUD
```

## Paper vs Live

| | Paper | Live |
|---|-------|------|
| Wallet | Simulated SOL balance | `SOLANA_PRIVATE_KEY` |
| Fills | Bonding-curve simulator | PumpPortal local API / Jupiter |
| Risk | Same gates | Same + confirm on mode switch |
| Journal | SQLite `data/desk.db` | Same + on-chain signatures |

Mode is stored in orchestrator state; switching to Live requires explicit API call + optional header confirm.

## Phase roadmap

1. Mock stream + Onyx (current)
2. PumpPortal `subscribeNewToken` + Safety stubs
3. Cope Capital watchlists + copy signals
4. Paper executor + TP/SL monitor
5. Rust sniper worker (optional latency path)
6. Live execution + Jito bundles
