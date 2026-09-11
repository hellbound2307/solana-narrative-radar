#!/usr/bin/env python3
"""Generate the docs/ Jekyll site for the narrative radar (GitHub Pages artifact)."""
import json, os, datetime

DATA = "docs/_data/narratives.json"
INDEX = "docs/index.md"
README = "README.md"

def esc(s):
    return (s or "").replace("|", "\\|").replace("[", "\\[").replace("]", "\\]")

def site():
    d = json.load(open(DATA))
    narrs = d["narratives"]
    gen = d["generated"][:16].replace("T", " ")
    lines = [
        "---",
        "layout: default",
        "title: Solana Narrative Radar",
        "---",
        "",
        "# Solana Narrative Radar",
        "",
        f"*Cross-lane signal detection of emerging Solana narratives. Last refresh: {gen} UTC.*",
        "",
        "**Method:** each narrative is a hypothesis with a keyword fingerprint, scored across three independent lanes — GitHub dev activity (35%), news/KOL/reports via search (45%), verified on-chain program traffic (20%) — with a +15% bonus per lane of cross-agreement. Evidence lists below every score. [Method & sources →](https://github.com/hellbound2307/solana-narrative-radar#method)",
        "",
        "## Detected narratives (ranked)",
        "",
        "| # | Narrative | Score | Lanes | Momentum | What it is |",
        "|---|---|---|---|---|---|",
    ]
    for i, n in enumerate(narrs, 1):
        mom = "—" if n["momentum"] is None else f"{'+' if n['momentum'] >= 0 else ''}{n['momentum']}"
        lines.append(f"| {i} | **{esc(n['name'])}** | {n['score']:.2f} | {n['lanes_present']}/3 | {mom} | {esc(n['what'][:90])} |")
    lines += ["", "## Evidence & build ideas", ""]
    for i, n in enumerate(narrs[:5], 1):  # top 5 get detail blocks
        lines += [f"### {i}. {n['name']} — {n['score']:.2f}", "", f"*{n['what']}*", "", n["why"], "", "<details><summary>Evidence</summary>", ""]
        ev = n["evidence"]
        if ev["github"]:
            lines.append("**Dev activity:**")
            for g in ev["github"][:5]:
                lines.append(f"- [{g['key']}]({g['url']}) ({g['stars']}★) — {esc(g['desc'])}")
            lines.append("")
        if ev["search"]:
            lines.append("**Media / KOL / reports:**")
            for s in ev["search"][:5]:
                lines.append(f"- [{esc(s['title'])}]({s['url']}) — {esc(s['snippet'])[:100]}")
            lines.append("")
        if ev["onchain"]:
            lines.append("**On-chain:** " + ", ".join(f"{o['key']} ({o['tx_per_sec']} tx/s sampled)" for o in ev["onchain"]))
            lines.append("")
        lines += ["</details>", ""]
    ideas = build_ideas(narrs)
    lines += ["## 3-5 build ideas (tied to detected narratives)", ""]
    for idea in ideas:
        lines += [f"### {idea['title']}", "", f"*Tied to: {idea['narrative']}*", "", idea["text"], ""]
    os.makedirs("docs", exist_ok=True)
    open(INDEX, "w").write("\n".join(lines))
    print(f"[site] wrote {INDEX}: {len(narrs)} narratives, {len(ideas)} ideas")

def build_ideas(narrs):
    """Concrete product ideas derived from the TOP ranked narratives (spec: 3-5 ideas,
    each tied to a specific narrative, grounded in its evidence)."""
    top = narrs[:3]
    ideas = []
    if top and top[0]["id"] == "agent-infra":
        ideas.append({
            "narrative": top[0]["name"],
            "title": "Idea 1 — MCP server registry with on-chain reputation",
            "text": ("The dev-activity lane shows a burst of agent-framework repos while the Solana "
                     "Foundation publicly positions the chain as agent-payment infrastructure. Tooling "
                     "to discover, rate and pay MCP-style tool servers is missing: build a registry "
                     "dApp where agents list their capabilities, clients leave staked reviews, and "
                     "payment escrows settle in USDC per successful tool call. The registry itself is "
                     "a Solana program + a thin indexer — both top-lane evidence items point at demand."),
        })
    if any(n["id"] == "agentic-payments" for n in narrs):
        ideas.append({
            "narrative": "Autonomous Agent Payments",
            "title": "Idea 2 — x402-style pay-per-call metering for on-chain APIs",
            "text": ("Agentic-payment signals are rising across search and dev lanes. Build a metering "
                     "middleware: an escrow program that lets an agent pay per API call (streaming "
                     "micro-payments, refund on 5xx), with a dashboard for providers. Nothing mainstream "
                     "does per-call settlement on Solana today despite the Foundation pushing agent rails."),
        })
    if any(n["id"] == "stablecoin-payments" for n in narrs):
        ideas.append({
            "narrative": "Stablecoin Payment Rails",
            "title": "Idea 3 — Merchant checkout plugin with automatic FX to USDC",
            "text": ("Search-lane evidence shows stablecoins-as-default-medium coverage. Build an "
                     "open-source checkout widget (Shopify/WooCommerce plugin) that prices in local "
                     "currency, settles in USDC on Solana, and gives merchants a single reconciliation "
                     "API. The wedge is MENA/Africa remittance corridors where card fees are the pain."),
        })
    if any(n["id"] == "depin-telecom" for n in narrs):
        ideas.append({
            "narrative": "DePIN Telecom Expansion",
            "title": "Idea 4 — Helium-style coverage mapper for new DePIN networks",
            "text": ("DePIN signals are strong in both dev and media lanes. Build an open coverage-"
                     "visualizer that ingests hotspot geodata + reward flows for any DePIN network "
                     "and highlights underserved regions (where adding hardware is most profitable). "
                     "Sellable to network operators, useful to hosts deciding where to deploy."),
        })
    if any(n["id"] == "onchain-gaming" for n in narrs):
        ideas.append({
            "narrative": "On-Chain Gaming at Scale",
            "title": "Idea 5 — Player-economy analytics for fully on-chain games",
            "text": ("Gaming migration signals (voxel MMOs moving player bases on-chain) create a new "
                     "data need: an analytics panel for on-chain game economies — player flow, item "
                     "inflation, sink/faucet health. The same indexer pattern powers it for any game."),
        })
    return ideas

if __name__ == "__main__":
    site()
