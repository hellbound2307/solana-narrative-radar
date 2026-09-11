#!/usr/bin/env python3
"""
Solana Narrative Radar — analyzer.
Consumes signals/*.json, scores NARRATIVE HYPOTHESES across lanes,
and emits: narratives/<date>.json + docs/_data/narratives.json for the site.

Method (explainability-first, per the bounty spec):
  Each narrative is a hypothesis with a keyword/regex fingerprint. For every
  hypothesis we compute evidence across three independent lanes:
    - github:  new/hot repos matching the fingerprint (stars proxy dev energy)
    - search:  news/KOL/report mentions matching the fingerprint
    - onchain: verified program activity in the narrative's core venues
  Score = weighted lane agreement (a narrative that shows in ALL lanes with
  fresh timestamps ranks above one that only trends on social).
  Output per narrative: score, per-lane evidence lists, freshness, momentum
  (vs previous collection if present), and a human-readable "why".
"""
import json, os, re, glob, datetime

SIG_DIR = os.environ.get("RADAR_SIG", "signals")
OUT_DIR = os.environ.get("RADAR_OUT_N", "narratives")
SITE_DATA = os.path.join("docs", "_data")

# ---------------------------------------------------------------------------
# Narrative hypotheses: fingerprint + description + core venues.
# The set is reviewed each fortnight; new fingerprints enter when a cluster of
# cross-lane signals doesn't fit any existing hypothesis.
NARRATIVES = [
    {
        "id": "agentic-payments",
        "name": "Autonomous Agent Payments",
        "fingerprint": [r"\bagent(s)?\b.*\b(pay|payment|wallet|commerce|econom)", r"\bagentic\b", r"x402|xpay|agent.?to.?agent", r"\bagentic internet\b"],
        "what": "AI agents holding wallets and paying each other for services; stablecoin rails as the settlement layer.",
        "venues": {"github": ["agent", "x402", "payments"], "search": ["solana AI agents payments"]},
    },
    {
        "id": "agent-infra",
        "name": "Agent Infrastructure & Tooling",
        "fingerprint": [r"\bagent\b", r"\bautonomous\b", r"\bMCP\b", r"\btool.?call", r"\bskill\.md\b"],
        "what": "Frameworks, MCP servers, agent-runtimes and dev-tooling that make on-chain agents buildable.",
        "venues": {"github": ["agent", "mcp"], "search": ["solana AI agent"]},
    },
    {
        "id": "depin-telecom",
        "name": "DePIN Telecom Expansion",
        "fingerprint": [r"\bDePIN\b", r"\bhelium\b", r"\btelecom\b", r"\bwireless\b", r"\bhotspot\b"],
        "what": "Decentralized physical infrastructure — Helium-style wireless networks expanding coverage.",
        "venues": {"github": ["depin", "helium"], "search": ["solana DePIN telecom"]},
    },
    {
        "id": "stablecoin-payments",
        "name": "Stablecoin Payment Rails",
        "fingerprint": [r"\bstablecoin", r"\bUSDC\b", r"\bmerchant\b", r"\bcheckout\b", r"\bremittance\b"],
        "what": "Stablecoins as default payment medium for commerce, remittances and B2B settlement.",
        "venues": {"github": ["stablecoin", "pay", "checkout"], "search": ["solana stablecoin payments"]},
    },
    {
        "id": "rwa-tokenization",
        "name": "Real-World Asset Tokenization",
        "fingerprint": [r"\bRWA\b", r"real.?world.?asset", r"\btokencap", r"\btreasury\b.*\btoken", r"\bcommodity\b"],
        "what": "Treasuries, commodities and funds issued as Solana tokens.",
        "venues": {"github": ["rwa", "tokenization"], "search": ["solana RWA real world assets"]},
    },
    {
        "id": "onchain-gaming",
        "name": "On-Chain Gaming at Scale",
        "fingerprint": [r"\bgame\b", r"\bgaming\b", r"\bvoxel\b", r"\bmigrat", r"\bplayer", r"\bmmorpg\b|\bopen.?world\b"],
        "what": "Real games migrating player bases and economies fully on-chain (not just NFT skins).",
        "venues": {"github": ["game", "gaming"], "search": ["solana gaming on-chain"]},
    },
    {
        "id": "privacy-layer",
        "name": "Privacy Tooling",
        "fingerprint": [r"\bprivacy\b", r"\bshielded\b", r"\bzk.?proof|\bzero.?knowledge\b", r"\bstealth\b.*\baddress|\bumbra\b"],
        "what": "Privacy-preserving transfers and private DeFi positions returning as a user demand.",
        "venues": {"github": ["privacy", "zk"], "search": ["solana privacy"]},
    },
    {
        "id": "clob-perp-derivatives",
        "name": "Perps & CLOB Derivatives",
        "fingerprint": [r"\bperp", r"\bCLOB\b|central limit order", r"\bderivatives\b", r"\bleverage\b.*\btrading", r"\bzeta\b|\bdrift\b"],
        "what": "On-chain perp venues and orderbook infra replacing CEX flows.",
        "venues": {"github": ["perp", "clob", "orderbook"], "search": ["solana perps CLOB"]},
    },
    {
        "id": "validator-modernization",
        "name": "Validator Client Modernization",
        "fingerprint": [r"\bFiredancer\b", r"\bfrankendancer\b", r"\bvalidator\b.*\bclient", r"\bsingle.?slot\b|\bblock.?engine\b"],
        "what": "Firedancer rollout, shared-blocker architecture, throughput/latency milestones.",
        "venues": {"github": ["firedancer", "frankendancer", "agave"], "search": ["solana Firedancer validator"]},
    },
    {
        "id": "consumer-memecoins",
        "name": "Consumer Token Launch Culture",
        "fingerprint": [r"\bmeme", r"\bpump\.fun|\blaunpad\b|\btoken launch\b", r"\bvir", r"\bcoordinate wallets\b"],
        "what": "Token-launch platforms as consumer onboarding (pump.fun style) and the tooling around them.",
        "venues": {"github": ["pump", "launch", "meme"], "search": ["solana pump.fun launch"]},
    },
]

W = {"github": 0.35, "search": 0.45, "onchain": 0.20}

def text_of(sig):
    parts = [sig.get("desc", ""), sig.get("title", ""), sig.get("snippet", ""),
             sig.get("query", ""), str(sig.get("key", ""))]
    return " ".join(p for p in parts if p)

def match_narrative(n, sig):
    t = text_of(sig)
    for pat in n["fingerprint"]:
        if re.search(pat, t, re.IGNORECASE):
            return True
    return False

def analyze(signals):
    results = []
    prev = load_previous()
    for n in NARRATIVES:
        ev = {"github": [], "search": [], "onchain": []}
        for g in signals.get("github", []):
            if match_narrative(n, g):
                ev["github"].append({"key": g["key"], "stars": g.get("stars", 0),
                                     "url": g.get("url"), "desc": g.get("desc", "")[:90]})
        for s in signals.get("search", []):
            if match_narrative(n, s):
                ev["search"].append({"title": s["title"][:80], "url": s["url"],
                                     "snippet": s["snippet"][:120], "date": s.get("date", "")})
        for o in signals.get("onchain", []):
            # on-chain lane: narrative venue match is manual (pump_fun -> memecoins etc.)
            venue_map = {"consumer-memecoins": ["pump_fun"],
                         "clob-perp-derivatives": ["raydium_amm_v4"],
                         "agent-infra": ["spl_token_2022"]}
            if n["id"] in venue_map and o["key"] in venue_map[n["id"]]:
                ev["onchain"].append(o)
        lanes_present = sum(1 for k in ev if ev[k])
        # score: lane weights * normalized counts, bonus for cross-lane agreement
        s_g = min(len(ev["github"]) / 6.0, 1.0)
        s_s = min(len(ev["search"]) / 10.0, 1.0)
        s_o = 1.0 if ev["onchain"] else 0.0
        score = W["github"] * s_g + W["search"] * s_s + W["onchain"] * s_o
        score *= 1.0 + 0.15 * (lanes_present - 1)  # agreement bonus
        # momentum vs previous collection
        momentum = None
        if prev:
            pn = next((x for x in prev.get("narratives", []) if x["id"] == n["id"]), None)
            if pn: momentum = round(score - pn.get("score", 0), 3)
        results.append({
            "id": n["id"], "name": n["name"], "what": n["what"],
            "score": round(score, 3), "momentum": momentum,
            "lanes_present": lanes_present,
            "evidence": ev,
            "why": why_string(n, ev, lanes_present),
        })
    results.sort(key=lambda x: -x["score"])
    return results

def why_string(n, ev, lanes):
    bits = []
    if ev["github"]: bits.append(f"{len(ev['github'])} dev signals (top: {ev['github'][0]['key']})")
    if ev["search"]: bits.append(f"{len(ev['search'])} media/KOL signals")
    if ev["onchain"]: bits.append("active on-chain program traffic")
    return f"Detected via {' + '.join(bits) if bits else 'no current evidence'} — cross-lane agreement: {lanes}/3."

def load_previous():
    files = sorted(glob.glob(os.path.join(SIG_DIR, "*.json")))
    if len(files) < 2: return None
    # previous analysis, keyed by previous signal file
    prev_sig = files[-2]
    stem = os.path.basename(prev_sig).replace(".json", "")
    prev_out = os.path.join(OUT_DIR, stem + ".json")
    if os.path.exists(prev_out):
        return json.load(open(prev_out))
    # else: recompute from prev signals (cheap, same code)
    try:
        sig = json.load(open(prev_sig))
        return {"narratives": analyze(sig)}
    except Exception:
        return None

def main():
    files = sorted(glob.glob(os.path.join(SIG_DIR, "*.json")))
    if not files:
        print("[analyze] no signals"); return
    latest = files[-1]
    stamp = os.path.basename(latest).replace(".json", "")
    sig = json.load(open(latest))
    narratives = analyze(sig)
    out = {
        "generated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "signal_file": latest,
        "method": "cross-lane hypothesis scoring: github(0.35) + search(0.45) + onchain(0.20), +15%/lane agreement bonus",
        "narratives": narratives,
    }
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, stamp + ".json"), "w", encoding="utf-8", errors="replace") as f:
        json.dump(out, f, indent=1)
    os.makedirs(SITE_DATA, exist_ok=True)
    # Jekyll's safe_yaml parses _data/*.json as YAML — write pure-ASCII with
    # valid JSON escapes (no raw control chars / surrogates / non-ASCII bytes)
    # so the Pages build never chokes on scraped text.
    # Sanitize scraped text for Jekyll's YAML parser (Psych):
    #  - lone UTF-16 surrogates (from broken upstream escapes) — invalid in YAML & utf-8
    #  - non-BMP emoji — ensure_ascii emits surrogate-pair escapes Psych rejects
    def _clean(o):
        if isinstance(o, dict): return {k: _clean(v) for k, v in o.items()}
        if isinstance(o, list): return [_clean(v) for v in o]
        if isinstance(o, str):
            return "".join(c if (ord(c) <= 0xFFFF and not (0xD800 <= ord(c) <= 0xDFFF)) else "?" for c in o)
        return o
    out = _clean(out)
    with open(os.path.join(SITE_DATA, "narratives.json"), "w", encoding="ascii") as f:
        json.dump(out, f, indent=1, ensure_ascii=True)
    print(f"[analyze] {stamp}: {len(narratives)} narratives ranked")
    for n in narratives[:5]:
        m = "" if n["momentum"] is None else f" (Δ{n['momentum']})"
        print(f"  {n['score']:.2f} {n['name']}{m} — lanes {n['lanes_present']}/3")

if __name__ == "__main__":
    main()
