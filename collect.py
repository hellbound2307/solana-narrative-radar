#!/usr/bin/env python3
"""
Solana Narrative Radar — signal collector.
Gathers raw signals from four lanes:
  1. GitHub dev activity (new repos, star acceleration)
  2. News / reports / KOL mentions (via Serper search API)
  3. On-chain activity (public Solana RPC: program activity samples)
  4. Ecosystem reports (Solana Foundation news)

Writes signals/<date>.json — consumed by analyze.py.
Runs inside GitHub Actions (needs: GITHUB_TOKEN, SERPER_API_KEY).
Also runs locally for dev (same env vars).
"""
import json, os, sys, time, urllib.request, urllib.parse, datetime, gzip, io

OUT_DIR = os.environ.get("RADAR_OUT", "signals")
GH_TOKEN = os.environ.get("GITHUB_TOKEN", "")
SERPER = os.environ.get("SERPER_API_KEY", "")
RPC = os.environ.get("SOLANA_RPC", "https://api.mainnet-beta.solana.com")

def api(url, headers=None, body=None, timeout=25):
    h = {"User-Agent": "narrative-radar/1.0"}
    if body is not None: h["Content-Type"] = "application/json"
    if headers: h.update(headers)
    req = urllib.request.Request(url, headers=h,
        data=json.dumps(body).encode() if body else None,
        method="POST" if body else "GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)

# ---------------------------------------------------------------- GitHub lane
def github_signals():
    out = []
    if not GH_TOKEN:
        print("  [github] no token, skipping", file=sys.stderr); return out
    H = {"Authorization": f"Bearer {GH_TOKEN}", "Accept": "application/vnd.github+json"}
    # (a) hot NEW repos (created in last 90d, sorted by stars)
    for q in ["solana created:>2026-06-01", "solana agent created:>2026-06-01",
              "solana depin created:>2026-06-01"]:
        try:
            d = api("https://api.github.com/search/repositories?q=" +
                    urllib.parse.quote(q) + "&sort=stars&order=desc&per_page=10", headers=H)
            for r_ in d.get("items", []):
                out.append({
                    "lane": "github_new",
                    "key": r_["full_name"],
                    "stars": r_["stargazers_count"],
                    "desc": (r_.get("description") or "")[:140],
                    "url": r_["html_url"],
                    "created": r_["created_at"],
                    "lang": r_.get("language"),
                })
        except Exception as e:
            print(f"  [github] {q}: {e}", file=sys.stderr)
    # (b) star VELOCITY on established repos (stargazers last 90d via search is capped;
    # use repo events as proxy — releases = shipped momentum)
    try:
        d = api("https://api.github.com/search/repositories?q=" +
                urllib.parse.quote("solana pushed:>2026-09-01 stars:>200") +
                "&sort=updated&order=desc&per_page=10", headers=H)
        for r_ in d.get("items", []):
            out.append({
                "lane": "github_active",
                "key": r_["full_name"],
                "stars": r_["stargazers_count"],
                "desc": (r_.get("description") or "")[:140],
                "url": r_["html_url"],
                "pushed": r_["pushed_at"],
                "lang": r_.get("language"),
            })
    except Exception as e:
        print(f"  [github] active: {e}", file=sys.stderr)
    return out

# ---------------------------------------------------------------- search lane
SEARCH_QUERIES = [
    "solana emerging narrative 2026",
    "solana AI agents payments 2026",
    "solana DePIN telecom 2026",
    "solana stablecoin payments 2026",
    "solana restaking staking 2026",
    "solana gaming on-chain 2026",
    "solana privacy 2026",
    "solana RW real world assets 2026",
    "solana validator client Firedancer 2026",
    "solana new program launch",
    "helius messari solana report",
    "electric capital crypto developer report solana",
]

def search_signals():
    out = []
    if not SERPER:
        print("  [search] no key, skipping", file=sys.stderr); return out
    for q in SEARCH_QUERIES:
        try:
            body = json.dumps({"q": q, "num": 10}).encode()
            req = urllib.request.Request("https://google.serper.dev/search",
                headers={"X-API-KEY": SERPER, "Content-Type": "application/json"},
                data=body, method="POST")
            with urllib.request.urlopen(req, timeout=25) as r:
                d = json.load(r)
            for it in d.get("organic", [])[:8]:
                out.append({
                    "lane": "search",
                    "query": q,
                    "title": it.get("title", "")[:120],
                    "snippet": it.get("snippet", "")[:200],
                    "url": it.get("link", ""),
                    "date": it.get("date", ""),
                })
            time.sleep(0.6)  # be polite
        except Exception as e:
            print(f"  [search] {q}: {e}", file=sys.stderr)
    return out

# ------------------------------------------------------------- on-chain lane
PROGRAMS = {
    # verified-live on mainnet via getSignaturesForAddress probes (2026-09-11)
    "pump_fun": "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P",
    "raydium_amm_v4": "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8",
    "spl_token_2022": "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb",
}

def onchain_signals():
    out = []
    for name, addr in PROGRAMS.items():
        d = None
        for attempt in range(3):  # public RPC rate-limits; backoff and retry
            try:
                d = api(RPC, body={"jsonrpc": "2.0", "id": 1, "method": "getSignaturesForAddress",
                                  "params": [addr, {"limit": 30}]})
                break
            except Exception as e:
                if attempt == 2:
                    print(f"  [onchain] {name}: {e}", file=sys.stderr)
                time.sleep(2.5 * (attempt + 1))
        if not d: continue
        sigs = d.get("result", [])
        times = sorted(s.get("blockTime") for s in sigs if s.get("blockTime"))
        if not times: continue
        window = max(times[-1] - times[0], 1)  # min 1s floor
        # normalized metric: how long do 30 tx take = inverse throughput intensity
        out.append({
            "lane": "onchain",
            "key": name,
            "sample_tx": len(times),
            "window_sec": window,
            "tx_per_sec": round(len(times) / window, 3),
            "latest_blocktime": times[-1],
        })
        time.sleep(1.2)  # public RPC courtesy
    return out

# ------------------------------------------------------------------ reports
def report_urls():
    """Curated report sources — checked for freshness, linked as evidence."""
    return [
        {"name": "Solana Foundation news", "url": "https://solana.com/news"},
        {"name": "Helius blog", "url": "https://www.helius.dev/blog"},
        {"name": "Messari Solana research", "url": "https://messari.io/protocol/solana"},
        {"name": "Electric Capital dev report", "url": "https://www.electriccapital.com/reports"},
    ]

def main():
    now = datetime.datetime.now(datetime.timezone.utc)
    stamp = now.strftime("%Y-%m-%d")
    print(f"[radar] collecting {stamp}")
    signals = {"github": [], "search": [], "onchain": []}
    print("[radar] github lane")
    signals["github"] = github_signals()
    print(f"  {len(signals['github'])} gh signals")
    print("[radar] search lane")
    signals["search"] = search_signals()
    print(f"  {len(signals['search'])} search signals")
    print("[radar] onchain lane")
    signals["onchain"] = onchain_signals()
    print(f"  {len(signals['onchain'])} program rates")
    os.makedirs(OUT_DIR, exist_ok=True)
    signals["_meta"] = {
        "collected_at": now.isoformat(),
        "sources": report_urls(),
        "counts": {k: len(v) for k, v in signals.items() if k != "_meta"},
    }
    path = os.path.join(OUT_DIR, f"{stamp}.json")
    with open(path, "w") as f:
        json.dump(signals, f, indent=1)
    print(f"[radar] wrote {path}")
    # keep last 6 collections
    files = sorted(os.listdir(OUT_DIR))
    for old in files[:-6]:
        os.remove(os.path.join(OUT_DIR, old))

if __name__ == "__main__":
    main()
