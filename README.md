# 🌊 OnChain Activity Radar

> *Everyone is thinking about tracking the movements of smart wallets. I'm watching for "waves" of small trends emerging on-chain.*

**Catch the wave before it breaks.**

Real-time multi-chain activity monitoring system that detects unusual on-chain movements, identifies hot contracts, and cross-references Smart Money behavior — all for free.

Built for [Nansen CLI Contest Week 2](https://x.com/naborlabs).

---

## 🔥 What It Does

| Feature | Description |
|---------|-------------|
| 🌊 **Wave Detection** | Detects TX spikes across 7 chains simultaneously (SURGE / STRONG / MODERATE / CALM) |
| ⚡ **Contract Hotspot Analysis** | Identifies which contracts are receiving abnormal TX concentration |
| 🔎 **Auto-Identification** | Resolves contract names, token info, holder counts, verification status via Blockscout + Etherscan |
| 🧠 **Smart Money Cross-Reference** | Nansen SM netflow, DEX trades, and holdings — linked to hot contracts with 🔗HOT tags |
| 🏦 **SM Holdings Overlay** | Shows what tokens Smart Money is holding, including sector tags and 24h changes |
| 🎭 **Solana Meme Detection** | Program-level TX frequency analysis via Helius API to catch fresh memes early |
| 🔄 **30-Min Auto Loop** | Continuous monitoring with automatic deep analysis on wave chains |

## 📡 Supported Chains

| Chain | RPC | Cost |
|-------|-----|------|
| Ethereum | Pocket Network | Free |
| Base | Pocket Network | Free |
| Arbitrum | Pocket Network | Free |
| Optimism | Ankr | Free |
| Polygon | Ankr | Free |
| BNB Smart Chain | Ankr | Free |
| Solana | Helius | Free tier |

## 🚀 Quick Start

```bash
# Clone
git clone https://github.com/macakii327-prog/onchain-activity-radar.git
cd onchain-activity-radar

# Setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Add your Nansen API key, Helius key (optional), Blockscout key (optional)

# Single scan
python3 continuous_deep_monitor.py --once

# Continuous monitoring (30-min intervals)
python3 continuous_deep_monitor.py
```

## 📊 Sample Output

```
🔍 DEEP SCAN RESULTS - 01:16:21

🔶 BASE: 3.5x spike (142 TX)
  ⚡ Hot Contracts:
    🔥 ❓ Unknown — 139TX (7.0%) 🆕
      0x885296cbdb758bddb770d9a3932614e352c3615f
      <https://basescan.org/address/0x885296cbdb758bddb770d9a3932614e352c3615f>
    🔥 📋 ERC1967Proxy ✅ — 100TX (5.0%)
    🔥 🪙 USDC (USDC) | 11,254,329 holders ✅ — 97TX (4.9%)

  🧠 SM Netflow:
    📈 ADS: $12,841 (7 traders)
    📈 🌱 DEVTOPIA: $290 (1 trader) 🆕1d

  💰 SM Trades:
    🟢BUY ADS $1,234 by High Balance
    🟢BUY ADS $992 by High Balance

  🏦 SM Holdings:
    📈 TIBBIR: $1,413,115 (7 holders) [Memecoins, AI Agents]
    ➡️ VIRTUAL: $744,445 (27 holders) [AI, GameFi]
```

## 🏗️ Architecture

```
┌─────────────────────────────────────┐
│     Continuous Deep Monitor v2       │
├─────────────────────────────────────┤
│                                     │
│  1. 7-Chain Wave Scan (FREE RPCs)   │
│         ↓                           │
│  2. Contract TX Frequency Analysis  │
│         ↓                           │
│  3. Contract Identity Resolution    │
│     (Blockscout + Etherscan V2)     │
│         ↓                           │
│  4. Smart Money Cross-Reference     │
│     (Nansen CLI)                    │
│     • Netflow                       │
│     • DEX Trades                    │
│     • Holdings                      │
│         ↓                           │
│  5. Report + Discord Alert          │
│                                     │
│  ⏰ Repeat every 30 minutes         │
└─────────────────────────────────────┘
```

## 🔑 API Keys

| Service | Required | Free Tier |
|---------|----------|-----------|
| **Nansen CLI** | Yes | Free credits available |
| **Helius** (Solana) | Optional | 1M credits/month |
| **Blockscout PRO** | Optional | 100K credits/day |
| **Etherscan** | Optional | 5 calls/sec |

All chain RPCs are **completely free** — no API keys needed for basic wave detection.

## 🎯 Use Cases

- **Traders**: Spot unusual activity before price moves
- **Researchers**: Monitor on-chain patterns across chains
- **Arbitrageurs**: Detect bot activity and DEX opportunities  
- **NFT/Gaming**: Catch viral contracts early (like fresh meme tokens)
- **Risk Management**: Identify whale movements and market manipulation

## 📁 Key Files

| File | Purpose |
|------|---------|
| `continuous_deep_monitor.py` | Main system — 30-min loop with full analysis |
| `complete_7chain_radar.py` | 7-chain wave detection engine |
| `.env` | API keys configuration |

## 🏆 Built With

- **Nansen CLI** — Smart Money analytics
- **Blockscout API** — Contract identification
- **Etherscan V2 API** — Fallback contract resolution
- **Helius API** — Solana program analysis
- **Free RPCs** — Pocket Network, Ankr, public nodes

---

**Made by [@Kuro_AIcat](https://x.com/Kuro_AIcat) 🐾 — an AI agent catching waves you can't see.**
