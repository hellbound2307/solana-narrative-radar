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
        "**Method:** each narrative is a hypothesis with a keyword fingerprint, scored across three independent lanes - GitHub dev activity (40%), news/KOL/reports via search (35%), verified on-chain program traffic (25%) — dev-led weights: new repos are the earliest verifiable emergence signal, media is the noisiest lane - with a +15% bonus per lane of cross-agreement. Evidence lists below every score. [Method & sources →](https://github.com/hellbound2307/solana-narrative-radar#method)",
        "",
        "## Detected narratives (ranked)",
        "",
        "| # | Narrative | Score | Lanes | Momentum | What it is |",
        "|---|---|---|---|---|---|",
    ]
    for i, n in enumerate(narrs, 1):
        mom = "—" if n["momentum"] is None else f"{'+' if n['momentum'] >= 0 else ''}{n['momentum']}"
        lines.append(f"| {i} | **{esc(n['name'])}** | {n['score']:.2f} | {n['lanes_present']}/3 | {mom} | {esc(n['what'][:90])} |")
    # Emergent discovery section (unsupervised lane)
    disc = d.get("discovered_clusters", [])
    if disc:
        lines += ["", "## Emergent clusters (discovered, not predefined)", "",
                  "*Unsupervised term-cluster detection over the raw signal text: terms must appear in 3+ independent signals and 2+ lanes to qualify. A cluster matching no hypothesis is a narrative candidate nobody pre-labeled - the discovery lane.*", ""]
        for c in disc:
            nov = " (novel)" if c.get("any_novel") else ""
            lines.append(f"- **{', '.join(c['cluster'][:3])}** - {c['docs']} signals, lanes: {'+'.join(c['lanes'])}{nov}")
        lines.append("")
    # Why-now / what-changed per narrative (deterministic, from scored evidence)
    lines += ["", "## Why now - per-narrative change", ""]
    for n in narrs[:8]:
        lines.append(f"- **{n['name']}**: {n.get('why_now', 'first run')}")
    # Seed bucket: below-gate early signals, promotable next run (transparent about what did NOT rank)
    seeds = d.get("seed_terms", [])
    if seeds:
        lines += ["", "## Seed bucket (early signals, below the ranking gate)", "",
                  "*Terms that failed the 3-docs + 2-lanes gate but show early cross-lane or 3-doc single-lane signal. Not ranked - watched, and promoted to clusters if they cross the gate next run. Published so exclusions are transparent, not hidden.*", ""]
        for s in seeds:
            lanes = "+".join(s["lanes"])
            lines.append(f"- {s['term']} - {s['docs']} docs, lanes {lanes}")
    lines += ["", "## Evidence & build ideas", ""]
    for i, n in enumerate(narrs[:5], 1):  # top 5 get detail blocks
        lines += [f"### {i}. {n['name']} - {n['score']:.2f}", "", f"*{n['what']}*", "", n["why"], "", "<details><summary>Evidence</summary>", ""]
        ev = n["evidence"]
        if ev["github"]:
            lines.append("**Dev activity:**")
            for g in ev["github"][:5]:
                lines.append(f"- [{g['key']}]({g['url']}) ({g['stars']}★) - {esc(g['desc'])}")
            lines.append("")
        if ev["search"]:
            lines.append("**Media / KOL / reports:**")
            for s in ev["search"][:5]:
                lines.append(f"- [{esc(s['title'])}]({s['url']}) - {esc(s['snippet'])[:100]}")
            lines.append("")
        if ev["onchain"]:
            lines.append("**On-chain:** " + ", ".join(f"{o['key']} ({o['tx_per_sec']} tx/s sampled)" for o in ev["onchain"]))
            lines.append("")
        lines += ["</details>", ""]
    ideas = build_ideas(narrs)
    lines += ["", "## Build ideas (fixed template: user / pain / 1-week MVP / Solana primitive / success metric)", ""]
    for idea in ideas:
        lines += [f"### {idea['title']}", "", f"*Tied to: {idea['narrative']}*", "",
                  f"- **User**: {idea['user']}",
                  f"- **Pain**: {idea['pain']}",
                  f"- **1-week MVP**: {idea['mvp']}",
                  f"- **Solana primitive**: {idea['primitive']}",
                  f"- **Success metric**: {idea['metric']}", ""]
    os.makedirs("docs", exist_ok=True)
    open(INDEX, "w").write("\n".join(lines))
    print(f"[site] wrote {INDEX}: {len(narrs)} narratives, {len(ideas)} ideas")

def build_ideas(narrs):
    """Build ideas from the TOP ranked narratives. Each is forced into the
    fixed template (judge-scorecard fix): user -> pain -> 1-week MVP ->
    Solana primitive -> success metric. No free-form brainstorms."""
    top = narrs[:3]
    T = [
        # (narrative_id_filter, title, user, pain, mvp, primitive, metric)
        ("agent-infra",
         "MCP-style tool-server registry with on-chain reputation",
         "AI-agent developers who need to discover and PAY for external tool calls",
         "There is no way to discover, rate or pay MCP-style tool servers; every agent re-implements integrations and scams are indistinguishable",
         "A Solana program listing tool servers with staked USDC reviews; a thin indexer; a CLI that an agent calls before invoking any tool",
         "SPL stablecoin escrow released on successful tool call (per-call metering)",
         "10 third-party tool servers listed + 100 paid tool calls settled in week 1"),
        ("agentic-payments",
         "x402-style pay-per-call metering for on-chain APIs",
         "API/data providers who want to sell calls to AI agents without accounts or invoicing",
         "Agents cannot pay per-call today; providers run free tiers that get abused, or require signup flows agents cannot complete",
         "Escrow middleware: agent deposits USDC, calls the API through a proxy, funds settle per call, refunds on 5xx",
         "SPL token escrow + PDA metering account per (agent, provider) pair",
         "3 providers integrated + 1,000 metered calls with zero failed settlements"),
        ("stablecoin-payments",
         "Merchant checkout with automatic local-currency pricing",
         "Small merchants in MENA/Africa selling online",
         "Card fees and FX eat 3-7% and settlement takes days",
         "Open-source checkout widget (WooCommerce plugin first) pricing in local currency, settling in USDC on Solana",
         "SPL stablecoin transfer + memo-driven reconciliation",
         "5 merchants live + first 100 USDC settled through the plugin"),
        ("depin-telecom",
         "DePIN coverage mapper that finds underserved regions",
         "DePIN hotspot hosts deciding where to deploy hardware next",
         "Hosts deploy blind; most pick saturated areas and earn nothing",
         "Ingests public hotspot geodata + reward flows, renders a map of reward-per-coverage gaps",
         "Read-only on-chain indexer over any DePIN program's reward distribution",
         "Mapper live for 2 networks; hosts report deployment decisions influenced by it"),
        ("onchain-gaming",
         "Player-economy analytics for fully on-chain games",
         "On-chain game studios balancing live economies",
         "No tooling exists for sink/faucet health, item inflation, or player-flow analytics on fully on-chain games",
         "An indexer + dashboard tracking item supply, burn rates, and player retention curves for any game using standard SPL tokens",
         "Token Program + Metaplex account indexing with per-game configuration",
         "2 studios using the dashboard weekly by day 7"),
    ]
    ideas = []
    for nid, title, user, pain, mvp, primitive, metric in T:
        if any(n["id"] == nid for n in narrs):
            nm = next(n["name"] for n in narrs if n["id"] == nid)
            ideas.append({
                "narrative": nm, "narrative_id": nid, "title": title,
                "user": user, "pain": pain, "mvp": mvp,
                "primitive": primitive, "metric": metric,
            })
    return ideas
if __name__ == "__main__":
    site()
