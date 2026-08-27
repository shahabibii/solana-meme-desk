# ONYX Desk — Figma Frame Checklist

Copy this into Figma as frame notes, a spec page, or component descriptions.
**Target frame:** `1440 × 900` (desktop). Min width `1280`. Mobile optional later.

---

## Frame setup

| Setting | Value |
|---------|-------|
| Frame name | `ONYX / Desk / Default` |
| Size | `1440 × 900` |
| Background | `#040810` + optional 48px grid at 4% cyan |
| Grid overlay | 48px square, `#00f5ff` @ 4% opacity, radial fade at edges |

### Design tokens (create as Figma variables)

| Token | Hex | Use |
|-------|-----|-----|
| `bg/base` | `#040810` | Page background |
| `bg/panel` | `#081020` @ 72% | Glass panels |
| `border/default` | `#00f5ff` @ 18% | Panel borders |
| `text/primary` | `#e8f4ff` | Body |
| `text/muted` | `#6b8fa3` | Labels |
| `accent/cyan` | `#00f5ff` | Primary, candidates, active |
| `accent/violet` | `#a78bfa` | Fills, equity |
| `accent/ok` | `#3dffaa` | Pass, stream OK |
| `accent/danger` | `#ff4d6d` | Blocks, down PnL |
| `mode/paper` | `#38bdf8` | Paper mode |
| `mode/live` | `#f97316` | Live mode |

**Fonts:** Orbitron (headers, labels, buttons) · Rajdhani (body, numbers)

---

## Layout map (pixel regions)

All coords from top-left of frame `(0,0)`.

```
┌──────────────────────────────────────────────────────────────── 1440 ─┐
│  TOP BAR                                    y:0   h:72              │
├─────────────────────────────────────────────────────────────────────┤
│  VITALS STRIP                               y:72  h:36              │
├──────────┬──────────────────────────────────────┬──────────────────┤
│ AGENT    │  CENTER STAGE                        │  RIGHT COLUMN      │
│ RAIL     │                                      │                    │
│ x:0      │  x:200                             │  x:1140            │
│ w:200    │  w:940                             │  w:300             │
│ y:108    │  y:108                             │  y:108             │
│ h:692    │  h:692                             │  h:692             │
├──────────┴──────────────────────────────────────┴──────────────────┤
│  CHAT BAR                                   y:800 h:100             │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Layer checklist (name exactly for handoff)

### 0. Background
- [ ] `bg/grid-overlay` — full bleed decorative
- [ ] `bg/radial-glow` — ellipse top-center `#0a1628 → transparent`

---

### 1. `TopBar` — `1440 × 72` @ `(0, 0)`

| Sub-component | Region (inside TopBar) | Data bind | States |
|---------------|------------------------|-----------|--------|
| `Brand/Mark` | x:24, y:16, 32×32 | static `◈` | — |
| `Brand/Title` | x:64, y:14 | static `ONYX` | — |
| `Brand/Subtitle` | x:64, y:36 | static `Solana Meme Desk` | — |
| `ModeToggle` | x:520, y:20, 200×32 | `mode: paper\|live` | paper-active, live-active, disabled |
| `WalletPill` | x:900, y:16, 220×40 | `equity_sol`, label | paper-label, live-label |
| `StreamBadge` | inside WalletPill | `connected: bool` | ok, reconnecting |

**Interactions:** `ModeToggle/Paper`, `ModeToggle/Live` → live needs confirm modal (`Modal/LiveConfirm`)

---

### 2. `VitalsStrip` — `1440 × 36` @ `(0, 72)`

| Chip name | Example text | Data bind | Color variant |
|-----------|--------------|-----------|---------------|
| `Vital/Mode` | `LIVE` or `PAPER` | `mode`, `live_ready` | live, paper |
| `Vital/Stream` | `STREAM OK` | `connected` | ok, bad |
| `Vital/Agent` | `SAFETY…` or `IDLE` | `busyAgent` | default |
| `Vital/Blocks` | `142 blocks` | `stats.blocks` | default |
| `Vital/Trades` | `3 trades` | `stats.total_trades` | default |
| `Vital/Open` | `1 open` | `positions.length` | default |

Layout: horizontal flex, gap 16px, padding `8px 24px`, Orbitron 10px uppercase.

---

### 3. `AgentRail` — `200 × 692` @ `(0, 108)`

Section title: `AGENTS` (Orbitron 11px muted)

Create **one component** `Agent/Row` with variants, instance × 7:

| Instance name | Agent id |
|---------------|----------|
| `Agent/Scout` | scout |
| `Agent/Safety` | safety |
| `Agent/Copy` | copy |
| `Agent/Research` | research |
| `Agent/Scorer` | scorer |
| `Agent/Executor` | executor |
| `Agent/Learner` | learner |

**`Agent/Row` anatomy (row h: ~56px):**
- [ ] `Agent/Row/Dot` — 8×8 circle
- [ ] `Agent/Row/Label` — agent name
- [ ] `Agent/Row/Verdict` — e.g. `PASS`, `BLOCK`, `FILLED`
- [ ] `Agent/Row/Latency` — e.g. `12ms` (optional)

**Variants (property `status`):**
`idle` · `running` · `pass` · `block` · `trade`

| status | Dot color | Extra |
|--------|-----------|-------|
| idle | muted | no verdict |
| running | cyan + pulse glow | — |
| pass | green | verdict text |
| block | red | verdict text |
| trade | violet | verdict text |

---

### 4. `CenterStage` — `940 × 692` @ `(200, 108)`

Stack top → bottom, centered, max content width `520px`, gap 16px.

#### 4a. `EquityCurve` — `520 × 100`
- [ ] `EquityCurve/Title` — `EQUITY`
- [ ] `EquityCurve/Value` — `1.042 SOL` → bind `equity_sol`
- [ ] `EquityCurve/Chart` — SVG line area, stroke `#a78bfa`

#### 4b. `MintChart` — `520 × 120`
- [ ] `MintChart/Title` — `SELECTED MINT`
- [ ] `MintChart/MintId` — `7xK9…` → bind `selectedMint`
- [ ] `MintChart/Sparkline` — uPnL line → bind `chartPoints[]`

#### 4c. `OnyxOrb` — `200 × 200` (hero)
- [ ] `Orb/RingOuter` — rotating ring, cyan @ 30%
- [ ] `Orb/RingInner` — rotating ring reverse, violet @ 30%
- [ ] `Orb/Core/Glyph` — `◈`
- [ ] `Orb/Core/StateLabel` — `IDLE` / `ACTIVE` / `ARMED`
- [ ] `Orb/Core/AgentName` — e.g. `SAFETY` when active

**Variants (property `orbState`):** `idle` · `active` · `armed`

#### 4d. `OpenPositions` — `520 × flex`
- [ ] `Positions/Title` — `OPEN`
- [ ] `Positions/Empty` — `No positions — PumpPortal + Safety scanning…`
- [ ] `Positions/Row` component × N

**`Positions/Row` anatomy:**
- `symbol` · `entry_sol` · `upnl_pct` (green/red) · `mint` truncated

**Row variant:** `up` · `down` · `flat`

---

### 5. `RightColumn` — `300 × 692` @ `(1140, 108)`

Stack top → bottom. Each section separated by 1px border `#00f5ff18`.

#### 5a. `CommandDeck` — `300 × ~140`
Title: `COMMAND DECK`

Button grid 2×3 (each ~140×36):

| Button | Label | Action |
|--------|-------|--------|
| `Cmd/Status` | Status | refresh + announce |
| `Cmd/Learner` | Run learner | POST learner |
| `Cmd/Backtest` | Backtest | POST backtest |
| `Cmd/Keys` | Keys | show integrations |
| `Cmd/Blocks` | Why blocks? | chat "blocks" |

States: default · hover · disabled · loading (`…`)

#### 5b. `IntegrationsPanel` — `300 × ~180`
Title: `INTEGRATIONS`

Row component `Integration/Row` × 8:

| Row | Key | Shows |
|-----|-----|-------|
| Solana RPC | `solana_rpc` | on/off |
| Helius | `helius` | on/off |
| Live wallet | `live_wallet` | on/off + pubkey snippet |
| Cope fomo | `cope_fomo` | on/off |
| PumpPortal key | `pumpportal_key` | on/off |
| PumpPortal stream | `pumpportal_stream` | on/off |
| Jito | `jito` | on/off |
| Sniper ingest | `sniper_ingest` | on/off |

Variant: `on` (green em) · `off` (muted em)

#### 5c. `StatsPanel` — `300 × ~200`
Title: `DESK STATS`

Stat grid 2 columns:
- Trades · Closed · Blocks · Win rate · Avg PnL

Sub-section `Learner weights` — list: pump, fomo, convergence, safety (numbers)

Footer note: `PumpPortal live · fomo on/off`

#### 5d. `SignalFeed` — `300 × remaining` (scroll)
Title: `SIGNAL FEED`

**`Feed/Item` component** variants by `kind`:

| kind | Color | Example |
|------|-------|---------|
| candidate | cyan | `New PEPE via pump` |
| block | pink | `BLOCKED — mint_authority_active` |
| fill | violet | `buy 0.05 SOL (live)` |
| agent | muted | `safety → PASS (8ms)` |
| mode | muted | `Desk mode → live` |

Anatomy: `Feed/Item/Time` · `Feed/Item/Text` · optional `Feed/Item/MintLink`

Interaction: click mint → selects chart (prototype link optional)

---

### 6. `ChatBar` — `1440 × 100` @ `(0, 800)`

| Sub-component | Region | Notes |
|---------------|--------|-------|
| `Chat/Log` | full width, h:48 | last 2–4 lines, user + onyx |
| `Chat/Input` | flex 1 | placeholder `Ask Onyx…` |
| `Chat/Mic` | 40×40 | listening glow when active |
| `Chat/VoiceToggle` | 40×40 | 🔊 / 🔇 |
| `Chat/Send` | 80×40 | `SEND` |

Message variants: `Chat/Message/User` · `Chat/Message/Onyx`

---

## Additional frames to design (variants)

Create separate frames or use component variants:

| Frame name | Purpose |
|------------|---------|
| `ONYX / Desk / Paper` | Paper mode active, blue accents |
| `ONYX / Desk / Live Armed` | Live + live_ready, orange accents |
| `ONYX / Desk / Agent Active` | One agent `running`, orb active |
| `ONYX / Desk / Reconnecting` | Stream badge bad, vitals bad |
| `ONYX / Desk / Empty` | No positions, empty feed starter |
| `ONYX / Desk / With Positions` | 2–3 open positions, fills in feed |
| `ONYX / Modal / LiveConfirm` | "Real SOL at risk" confirm |
| `ONYX / Modal / BacktestResult` | round-trips, win rate (future) |
| `ONYX / Panel / TradeHistory` | optional v2 — table from `/api/trades` |

---

## Component naming convention

```
[Section]/[Element]/[Variant]

Examples:
  Agent/Row/status=running
  Feed/Item/kind=candidate
  ModeToggle/state=live-active
  Orb/state=armed
  Positions/Row/pnl=up
```

Figma page structure:
```
📄 Cover
📄 Tokens
📄 Components
   ├── Agent/
   ├── Feed/
   ├── Orb/
   ├── Positions/
   ├── Integrations/
   └── Chat/
📄 Screens
   ├── Default (1440)
   ├── Live Armed
   └── Empty
📄 Spec (paste this checklist)
```

---

## Data binding cheat sheet

| UI element | REST poll (15s) | WebSocket |
|------------|-----------------|-----------|
| Mode, wallet, stats, weights | `GET /api/status` | `desk.status`, `desk.mode` |
| Equity chart | `GET /api/equity-curve` | — |
| Integrations | `GET /api/integrations` | partial in status |
| Agent rail | — | `agent.start`, `agent.done` |
| Signal feed | — | all event types |
| Positions uPnL | status poll | `position.update` |
| Mint chart | — | `position.update`, select mint |
| Fills voice | — | `trade.fill` |

---

## Decorative vs functional

**Must be data-bound (don't fake long-term):**
- Mode, wallet SOL, stream, vitals, agents, positions, feed, stats, integrations, equity line

**Can be decorative:**
- Grid background, orb rings animation, glass blur intensity, particle effects
- Chart gradient fills (data drives line, not gradient)

**Placeholder OK in v1 design:**
- On-chain wallet balance (separate from paper equity)
- Yellowstone / sniper worker heartbeat
- Real Pump.fun bonding curve (use uPnL sparkline for now)

---

## Handoff checklist (when design is done)

Send me:
- [ ] Figma link or exported PNGs @ 1440 and 1280
- [ ] Variables/tokens exported (or screenshot)
- [ ] Component list matches names above
- [ ] All 7 variant frames or component variant sets
- [ ] Notes on any layout changes from this spec
- [ ] Font files or Google Fonts links

I will map each component → React + existing `/api/*` + `/ws/onyx` with minimal backend additions.
