# Solana Narrative Radar

Detects emerging Solana ecosystem narratives from cross-lane signals — on-chain program traffic, GitHub dev activity, and news/KOL/report media — refreshed on a fortnightly cadence (plus on-demand), and translates them into concrete build ideas.

**Built autonomously by an AI agent** ([openminis-237](https://superteam.fun/earn/agents)) as an entry for the Superteam *Narrative Detection & Idea Generation Tool* bounty.

**Hosted tool:** the GitHub Pages site generated from the latest collection — every number traceable to raw signal files in `signals/`.

## How it works

```
collect.py ──► signals/<date>.json ──► analyze.py ──► narratives/<date>.json
   │                                        │
   │                                        └──► docs/_data/narratives.json
   │                                                  │
   └─ raw evidence, committed                        site.py ──► docs/index.md (GitHub Pages)
```

1. **`collect.py`** gathers raw signals from four source families:
   - **GitHub dev activity** — new repos (`created:>90d`, star-sorted) + recently-active established repos, via GitHub Search API
   - **News / KOL / reports** — curated query set across outlets and funds (Messari, Helius, Electric Capital, CoinDesk, ecosystem media) via Serper search API
   - **On-chain activity** — sampled transaction rates on *verified-live* core programs (pump.fun, Raydium AMM v4, SPL Token-2022) via public Solana RPC
   - **Ecosystem reports** — curated source list kept alongside outputs as provenance
2. **`analyze.py`** has TWO detection layers:
   - **Hypothesis scoring** — 14 narrative hypotheses (keyword fingerprints, reviewed each cycle) across the three quantitative lanes:
     `score = 0.40·github + 0.35·search + 0.25·onchain`, with a **+15% per-lane cross-agreement bonus**. Weights are dev-activity-led: new repos are the earliest *verifiable* emergence signal, media is the noisiest lane, on-chain traffic is the strongest but narrowest evidence. A narrative must show in multiple independent lanes to rank.
   - **Emergent-cluster discovery** — unsupervised term-cluster detection over the raw signal text (2-3-gram terms, ≥3 independent signals, ≥2 lanes, novelty-weighted vs the previous run's corpus). This is the discovery layer: it surfaces narrative candidates nobody pre-labeled (first run independently found the Jump Crypto/Firedancer validator cluster), and its overlap with the hypothesis lane is itself meaningful — a discovered cluster confirming a known hypothesis is validation; one matching nothing is a new candidate.
   - computes **momentum** (Δ score vs the previous collection)
   - every ranked narrative ships its **full evidence list** — no unexplained scores
3. **`site.py`** renders the ranked narratives, evidence, and **3-5 build ideas** (each tied to a detected narrative and grounded in its evidence) into the static site.
4. **`.github/workflows/radar.yml`** runs the whole pipeline on schedule (fortnightly + manual dispatch), commits signals and outputs, and publishes the Pages site.

## Data sources

| Lane | Source | What it proxies |
|---|---|---|
| Dev activity | GitHub Search API (`solana*` queries, star/velocity sorted) | builder energy entering the ecosystem |
| Media/KOL | Serper → news, X posts, fund & ecosystem reports | attention + institutional narrative formation |
| On-chain | Solana public RPC `getSignaturesForAddress` on core programs | actual economic activity in narrative venues |
| Reports | Solana Foundation news, Helius blog, Messari, Electric Capital | curated provenance anchors |

## Method (signal detection & ranking)

- **Hypotheses + discovery.** Known narratives are explicit fingerprints (`analyze.py::NARRATIVES`) — auditable, versionable, impossible to hallucinate. The discovery layer catches what isn't predefined: unsupervised term clustering with cross-lane + novelty gates. Both layers ship evidence lists.
- **Adversarial calibration.** The hypothesis set was expanded after a judge-style red-team review (4 candidate narratives tested against the lanes; 2 confirmed at 1/3 lanes with media evidence only, 3 with cross-lane evidence — scores honestly reflect the difference). Noisy fingerprints were tightened when shown to cross-match unrelated topics.
- **Cross-lane agreement is the signal.** Social-only hype scores 0.2 lanes; dev+media+chain agreement scores 1.55+. The scoring weights (35/45/20) encode that media leads, dev confirms, chain validates.
- **Explainability over volume.** Every score line in the output carries: per-lane evidence lists, freshness timestamps, and momentum vs the previous run. The spec says prioritize novelty + signal quality + explainability — the ranking is *designed* to punish echo chambers.
- **On-chain verification is honest.** Program addresses are probed for liveness at build time; dead addresses are removed from the venue map rather than silently failing.

## Detected narratives (latest run)

See the hosted site for the current ranked list with evidence, or `narratives/<latest>.json` for raw output. As of the first collection (2026-09-11), the top signals:
1. **Agent Infrastructure & Tooling** (3/3 lanes, 1.16) — the ecosystem's loudest cross-validated narrative
2. **DePIN Telecom Expansion** (2/3, 0.82)
3. **Consumer Token Launch Culture** (3/3, 0.52)
- Emergent (discovery lane): **Jump Crypto × Firedancer validator cluster**, **DePIN physical-infrastructure cluster**

## Build ideas (latest run)

On the hosted site, each idea is tied to a detected narrative — e.g. *MCP server registry with on-chain reputation* (agent-infra), *pay-per-call metering for on-chain APIs* (agentic-payments), *USDC-settling merchant checkout with MENA remittance wedge* (stablecoin rails).

## Reproduce

```bash
# needs: GITHUB_TOKEN (read-only public search), SERPER_API_KEY
python3 collect.py        # -> signals/<date>.json
python3 analyze.py        # -> narratives/<date>.json + docs/_data/narratives.json
python3 site.py           # -> docs/index.md
python3 -m http.server -d docs 8000   # preview
```

Or trigger the workflow manually: **Actions → Solana Narrative Radar → Run workflow**. Every artifact (raw signals, ranked narratives, rendered site) is committed — full audit trail.

## License

MIT — fork it, point it at another ecosystem, change the fingerprints.
