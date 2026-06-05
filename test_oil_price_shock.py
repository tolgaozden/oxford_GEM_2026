import requests, json, time
import matplotlib.pyplot as plt

base_url = 'https://model.oxfordeconomics.com/api'
access_token = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6Ik1EWTVSak5ETlVVMk0wRkZPRVpHTlVOQ016azBSakl6TkRNek5qazNSVUZDTmpBMlJVTTBNQSJ9.eyJodHRwczovL3d3dy5veGZvcmRlY29ub21pY3MuY29tL29lQWNjb3VudElkIjoiQURCIiwiaXNzIjoiaHR0cHM6Ly9veGVjb24uYXV0aDAuY29tLyIsInN1YiI6ImF1dGgwfDVkYTU5YTFhOGU3ZTBkMGM2YzJmMTkwNCIsImF1ZCI6WyJodHRwczovL21vZGVsLm94Zm9yZGVjb25vbWljcy5jb20iLCJodHRwczovL294ZWNvbi5hdXRoMC5jb20vdXNlcmluZm8iXSwiaWF0IjoxNzgwNTYyMzEzLCJleHAiOjE3ODA2NDg3MTMsInNjb3BlIjoib3BlbmlkIHByb2ZpbGUiLCJhenAiOiI2TW5qRTVDQW1udzN3Q0pmSG9IWE1hSXBGNURLNHIyMiJ9.c-pC2SPaneiaF4SccPnk2Bei5LsglFZoQCRtMY13QuARnPo-Z5irueUKd2k_Y0FFabiAI1xzLTYHtBPQN8kXV5KA1zJd54TWo8WEEQYkptj9BBdkZa4hER-b6DbK91oKyC5p6eBrg5sungYH303XxYtlm-Fi6eTA-X-N6LGrleI3NVoTsw8ThEGQPwwBmcqs669QTccE70yj2pQBpZMW_ySFvluKucCwEuPY3rqAwJVkO3wosw7kZ3ogSBiXIWUGkhessOA_YP6Y5iH15moFGW0iwzZInQZ_VLVkOL0NC5tzucjYAoKs-wk8D7zkC7b_5haDAimhkO73EEUNXZgsfA"
headers = {'Authorization': f'Bearer {access_token}'}

# ── Config: oil is auto-detected; confirm rate/CPI codes via find() if a panel is empty ──
OIL_CODE, OIL_GROUP = None, None      # leave None to auto-detect
RATE_CODE = "RSH"                      # short-term interest rate (policy-rate proxy)
CPI_CODE  = "CPI"                      # consumer price index
COUNTRIES = ["US", "CHINA", "EURO_11"]
SHOCK_START, SHOCK_SIZE = "2026Q3", 1.20   # +20%

def get_json(r):
    r.raise_for_status()
    return json.loads(r.content.decode("utf-8-sig"))

def pkey(p):  y, q = p.split("Q"); return int(y)*4 + int(q)        # sortable
def to_x(p):  y, q = p.split("Q"); return int(y) + (int(q)-1)/4    # plot x
def add_q(p, n): k = pkey(p)-1+n; return f"{k//4}Q{k%4+1}"

# ── 1. Baseline ──
gem_path = "oxford-economics/releases/Global Economic Model"
folder = get_json(requests.get(f"{base_url}/v1/resources/{gem_path}", headers=headers))
forecasts = [c for c in folder["Children"] if c["Type"] == "Forecast"]
baseline = sorted(forecasts, key=lambda f: f["Versions"][-1]["CreatedAt"], reverse=True)[0]
base_id = baseline["Id"]
SOLVE_END = min(["2032Q4", baseline["Versions"][-1]["Range"]["To"]], key=pkey)   # cap at horizon
print("Baseline:", baseline["Name"], "| solving 2026Q1 ->", SOLVE_END)

# ── 2. Discover the oil price variable + its group ──
indicators = get_json(requests.get(f"{base_url}/v1/forecast-contents/{base_id}/indicators", headers=headers))
groups = get_json(requests.get(f"{base_url}/v1/forecast-contents/{base_id}/groups", headers=headers))
if OIL_CODE is None:
    cands = [i for i in indicators if "oil" in i["Name"].lower()
             and any(w in i["Name"].lower() for w in ("price", "brent", "barrel", "$/b"))]
    print("\nOil-price candidates:", [(i["Code"], i["Name"]) for i in cands])
    if not cands: raise SystemExit("No oil candidate — run find('oil') and set OIL_CODE.")
    OIL_CODE = cands[0]["Code"]
if OIL_GROUP is None:
    all_codes = [g["Code"] for g in groups]
    likely = [c for c in ["WORLD", "OPEC", "GLOBAL", "OECD", "ADVANECO", "EMERGMAR"] if c in all_codes]

    def oil_in(code):
        r = requests.post(f"{base_url}/v1/forecast-contents/{base_id}/variables?onlyProps=Values",
                          headers=headers,
                          json=[{"IndicatorCode": OIL_CODE, "GroupCode": code}], timeout=30)
        if r.status_code != 200:
            return False
        d = json.loads(r.content.decode("utf-8-sig"))
        return bool(d and d[0].get("Values"))

    found = [c for c in likely if oil_in(c)]
    if not found:                          # fall back to a full one-by-one scan
        print(f"Not in likely groups; scanning all {len(all_codes)} groups...")
        found = [c for c in all_codes if oil_in(c)]
    print("Oil price found in groups:", found)
    if not found:
        raise SystemExit(f"{OIL_CODE} returned no data anywhere — wrong code? run find('oil').")
    OIL_GROUP = "WORLD" if "WORLD" in found else found[0]
print(f"Using oil variable: {OIL_CODE}:{OIL_GROUP}\n")

# ── 3. Build + run the three scenarios ──
def oil_commands(end_shock):
    n = pkey(end_shock) - pkey(SHOCK_START) + 1
    factors = ", ".join([f"{SHOCK_SIZE}"] * n)
    return (f"MULTIPLY {OIL_CODE}:{OIL_GROUP} {SHOCK_START} {factors}\n"
            f"FIX {OIL_CODE}:{OIL_GROUP} {SHOCK_START}:{end_shock}")

scenarios = {"Oil +20% (1yr)":  add_q(SHOCK_START, 3),     # 4 quarters held
             "Oil +20% (2yr)":  add_q(SHOCK_START, 7),     # 8 quarters held
             "Oil +20% (perm)": SOLVE_END}                 # held to horizon
solved = {}
for name, end_shock in scenarios.items():
    out = f"/me/{name.replace(' ','_').replace('%','pct').replace('(','').replace(')','')}-{int(time.time())}"
    req = {"InputForecast": baseline["Path"], "SolutionRange": {"From": "2026Q1", "To": SOLVE_END},
           "Commands": oil_commands(end_shock), "OutputForecast": out}
    op = get_json(requests.post(f"{base_url}/v1/operations/solve", headers=headers, json=req))
    print(f"Solving '{name}' ...", end=" ", flush=True)
    while op["Status"] in ("Queued", "InProgress"):
        op = get_json(requests.get(f"{base_url}/v1/operations/{op['Id']}/await", headers=headers))
    if op["Status"] != "Succeeded":
        print("FAILED:", op.get("FailureReason")); continue
    solved[name] = get_json(requests.get(f"{base_url}/v1/resources{out}", headers=headers))["Id"]
    print(f"done ({op.get('Duration')}ms)")

# ── 4. Pull GDP / rate / CPI for baseline + scenarios ──
def pull(fid):
    sel = [{"IndicatorCode": ind, "GroupCode": c}
           for ind in ("GDP", RATE_CODE, CPI_CODE) for c in COUNTRIES]
    data = get_json(requests.post(f"{base_url}/v1/forecast-contents/{fid}/variables?onlyProps=Values",
                                  headers=headers, json=sel))
    return {(v["IndicatorCode"], v["GroupCode"]): {p["Period"]: p["Value"] for p in v["Values"]} for v in data}

runs = {"Baseline": pull(base_id)}
for name, fid in solved.items(): runs[name] = pull(fid)

# ── 5. Transform + plot (rows = metric, cols = country) ──
def ordered(s): ps = sorted(s, key=pkey); return ps, [s[p] for p in ps]
def qoq(s): ps, v = ordered(s); return ps[1:], [100*(v[i]/v[i-1]-1) for i in range(1, len(v))]
def yoy(s): ps, v = ordered(s); return ps[4:], [100*(v[i]/v[i-4]-1) for i in range(4, len(v))]
def lvl(s): return ordered(s)

metrics = [("GDP growth q/q (%)", "GDP", qoq),
           ("Policy rate (%)",     RATE_CODE, lvl),
           ("CPI inflation y/y (%)", CPI_CODE, yoy)]
colors = {"Baseline": "black", "Oil +20% (1yr)": "tab:blue",
          "Oil +20% (2yr)": "tab:orange", "Oil +20% (perm)": "tab:red"}
LO, HI = "2025Q1", SOLVE_END

fig, axes = plt.subplots(3, 3, figsize=(14, 9), sharex=True)
for r, (title, ind, fn) in enumerate(metrics):
    for c, country in enumerate(COUNTRIES):
        ax = axes[r][c]
        for run_name, d in runs.items():
            s = d.get((ind, country))
            if not s: continue
            ps, vs = fn(s)
            pts = [(to_x(p), v) for p, v in zip(ps, vs) if pkey(LO) <= pkey(p) <= pkey(HI)]
            if pts:
                ax.plot([x for x, _ in pts], [v for _, v in pts], label=run_name,
                        color=colors.get(run_name), lw=1.6, ls="--" if run_name == "Baseline" else "-")
        ax.axvline(to_x(SHOCK_START), color="gray", ls=":", lw=0.8)
        if r == 0: ax.set_title(country)
        if c == 0: ax.set_ylabel(title)
        ax.grid(alpha=0.3)
axes[0][-1].legend(fontsize=8)
fig.suptitle("Oil price +20% — temporary (1yr, 2yr) vs permanent", fontsize=13)
fig.tight_layout(); fig.savefig("oil_scenarios.png", dpi=120); plt.show()
print("Saved chart to oil_scenarios.png")