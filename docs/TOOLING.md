# Tooling map — Awesome AI in Finance × Onyx Solana desk

Curated repos from [Awesome AI4Finance](https://github.com/AI4Finance-Foundation/Awesome_AI4Finance), [awesome-llm-trading-agents](https://github.com/bettyguo/awesome-llm-trading-agents), and Solana-native agents — **what we adopt, borrow, or skip**.

## Rule of thumb

| Layer | Need | Wrong tool |
|-------|------|------------|
| **Hot path** (<500ms) | PumpPortal / gRPC + Jito + Jupiter | Freqtrade, Backtrader, Jesse |
| **Safety** | On-chain rug/honeypot | LLM “is this a rug?” |
| **Research** | fomo + thesis + metadata | Stock fundamental agents |
| **Learning** | Journal → weights / RL | Training LLM to memorize tickers |
| **HUD** | Onyx WebSocket events | Exchange UI widgets |

---

## ✅ Adopt or integrate (Onyx stack)

### Solana execution & data (core)

| Repo | Role in Onyx |
|------|----------------|
| [sendaifun/solana-agent-kit](https://github.com/sendaifun/solana-agent-kit) | Jupiter swaps, PumpPortal, Jito bundles — live execution seam |
| [PumpPortal](https://pumpportal.fun/data-api/real-time/) | `subscribeNewToken`, account trades, trade-local API |
| [Cope Capital / fomo](https://api.cope.capital/v1) | Smart-money watchlists, convergence, theses (Copy agent) |
| [MrWizardlyLoaf/rugcheck-ai](https://github.com/MrWizardlyLoaf/rugcheck-ai) | MCP: authorities, honeypot simulate, safe swap build |
| [rugpullnet/solana-rug](https://github.com/rugpullnet/solana-rug) | 13-factor rug score, sniper-pattern check (Safety agent) |
| [ponkssol/Cavion](https://github.com/Cavion) | TS rug score SDK (optional Safety backend) |

### Solana agent patterns (architecture inspiration)

| Repo | Borrow |
|------|--------|
| [underdeathsolana/circuit-agent](https://github.com/underdeathsolana/circuit-agent) | Scan → buy → monitor 10s → reflect; swarm rug blacklist |
| [BryanFrontend/AIVA](https://github.com/BryanFrontend/AIVA) | Reason codes on every signal; audit journal; paper/live modes |
| [ankushKun/pumpmyclaw](https://github.com/ankushKun/pumpmyclaw) | pump.fun bonding curve + profit buyback + leaderboard |
| [TradeSEB/solana-pumpfun-sniper-bot](https://github.com/TradeSEB/solana-pumpfun-sniper-bot) | Rust gRPC Create-instruction filter |

### Multi-agent / LLM (warm path only)

| Repo | Role |
|------|------|
| [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents) | **Research agent** debate pattern — never on sniper hot path |
| [AI4Finance-Foundation/FinRobot](https://github.com/AI4Finance-Foundation/FinRobot) | Perception → Brain → Action; good Onyx agent naming |
| [OpenBB-finance/OpenBB](https://github.com/OpenBB-finance/OpenBB) | Optional macro/context for chat — not for meme entries |

### Backtest & learning (after journal has trades)

| Repo | Role |
|------|------|
| [polakowo/vectorbt](https://github.com/polakowo/vectorbt) | Fast vectorized backtests on our closed-trade DB |
| [AI4Finance-Foundation/FinRL](https://github.com/AI4Finance-Foundation/FinRL) | **Learner agent** — RL on signal weights (offline) |
| [freqtrade/freqai](https://github.com/freqtrade/freqai) | ML retrain pattern (adapt features to mint outcomes, not CEX candles) |

---

## ⚠️ Borrow ideas only (attached infographics)

| Repo | Stars | Why not core for pump.fun memes |
|------|-------|----------------------------------|
| [freqtrade/freqtrade](https://github.com/freqtrade/freqtrade) | 40k+ | CEX/ccxt bots; too slow for launch sniping |
| [hummingbot/hummingbot](https://github.com/hummingbot/hummingbot) | 8k+ | Market-making on CEX/DEX pairs, not bonding curves |
| [nautechsystems/nautilus_trader](https://github.com/nautechsystems/nautilus_trader) | 15k+ | Institutional engine; overkill + no pump.fun native |
| [QuantConnect/Lean](https://github.com/QuantConnect/Lean) | 19k+ | Multi-asset brokerage; not Solana meme native |
| [mementum/backtrader](https://github.com/mementum/backtrader) | 15k+ | Daily/hourly bars; wrong latency class |
| [jesse-ai/jesse](https://github.com/jesse-ai/jesse) | 6k+ | Research/backtest UX reference for Onyx charts |
| [microsoft/qlib](https://github.com/microsoft/qlib) | 11k+ | Stock alpha factory; not launch detection |
| [tensortrade-org/tensortrade](https://github.com/tensortrade-org/tensortrade) | 5k+ | RL env design ideas for Learner phase |
| [Drakkar-Software/OctoBot](https://github.com/Drakkar-Software/OctoBot) | 7k+ | Multi-exchange DCA/grid — different product |

**Reuse from these:** dashboard stats (equity curve, win rate, profit factor), modular strategy plugins, backtest-before-live workflow — all in **Onyx UI**, fed by our journal.

---

## Onyx module mapping

```
ScoutAgent     ← PumpPortal WS + fomo activity + (optional) Yellowstone gRPC
SafetyAgent    ← rugcheck-ai + solana-rug + Jupiter simulate_sell
CopyAgent      ← Cope /v1/convergence + subscribeAccountTrade
ResearchAgent  ← fomo /tokens/{mint}/thesis + TradingAgents-style LLM summary
ScorerAgent    ← weighted ensemble (circuit-agent dip score + copy boost)
ExecutorAgent  ← solana-agent-kit / PumpPortal local (paper sim in Phase 1)
LearnerAgent   ← vectorbt + FinRL on SQLite journal (nightly)
Onyx HUD       ← Jesse/Lean-style panels + AIVA reason codes + live agent rail
```

---

## Master lists (bookmarks)

- [AI4Finance-Foundation/Awesome_AI4Finance](https://github.com/AI4Finance-Foundation/Awesome_AI4Finance)
- [bettyguo/awesome-llm-trading-agents](https://github.com/bettyguo/awesome-llm-trading-agents)
- [OpenBB-finance/awesome-openbb](https://github.com/OpenBB-finance/awesome-openbb)
- [e2b-dev/awesome-ai-agents](https://github.com/e2b-dev/awesome-ai-agents)

---

## Implementation order

1. Wire **PumpPortal + Cope** into Scout/Copy (replace mock stream)
2. Wire **rugcheck-ai / solana-rug** into Safety (hard veto)
3. **Paper executor** + TP/SL monitor (circuit-agent pattern)
4. **Onyx panels**: equity curve, win rate, agent latency (Freqtrade/Jesse UX)
5. **Learner**: export journal → vectorbt → adjust scorer weights
6. **Live** toggle → solana-agent-kit + Jito

Do **not** embed Freqtrade/Hummingbot/Lean as dependencies — they fight the Solana hot path.
