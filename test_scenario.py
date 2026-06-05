
# %%

import requests, json, time
import matplotlib.pyplot as plt

base_url = 'https://model.oxfordeconomics.com/api'
access_token = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6Ik1EWTVSak5ETlVVMk0wRkZPRVpHTlVOQ016azBSakl6TkRNek5qazNSVUZDTmpBMlJVTTBNQSJ9.eyJodHRwczovL3d3dy5veGZvcmRlY29ub21pY3MuY29tL29lQWNjb3VudElkIjoiQURCIiwiaXNzIjoiaHR0cHM6Ly9veGVjb24uYXV0aDAuY29tLyIsInN1YiI6ImF1dGgwfDVkYTU5YTFhOGU3ZTBkMGM2YzJmMTkwNCIsImF1ZCI6WyJodHRwczovL21vZGVsLm94Zm9yZGVjb25vbWljcy5jb20iLCJodHRwczovL294ZWNvbi5hdXRoMC5jb20vdXNlcmluZm8iXSwiaWF0IjoxNzgwNTYyMzEzLCJleHAiOjE3ODA2NDg3MTMsInNjb3BlIjoib3BlbmlkIHByb2ZpbGUiLCJhenAiOiI2TW5qRTVDQW1udzN3Q0pmSG9IWE1hSXBGNURLNHIyMiJ9.c-pC2SPaneiaF4SccPnk2Bei5LsglFZoQCRtMY13QuARnPo-Z5irueUKd2k_Y0FFabiAI1xzLTYHtBPQN8kXV5KA1zJd54TWo8WEEQYkptj9BBdkZa4hER-b6DbK91oKyC5p6eBrg5sungYH303XxYtlm-Fi6eTA-X-N6LGrleI3NVoTsw8ThEGQPwwBmcqs669QTccE70yj2pQBpZMW_ySFvluKucCwEuPY3rqAwJVkO3wosw7kZ3ogSBiXIWUGkhessOA_YP6Y5iH15moFGW0iwzZInQZ_VLVkOL0NC5tzucjYAoKs-wk8D7zkC7b_5haDAimhkO73EEUNXZgsfA"
headers = {'Authorization': f'Bearer {access_token}'}

def get_json(resp):
    resp.raise_for_status()
    return json.loads(resp.content.decode("utf-8-sig"))

# --- 1. Baseline = latest GEM release ---
gem_path = "oxford-economics/releases/Global Economic Model"
folder = get_json(requests.get(f"{base_url}/v1/resources/{gem_path}", headers=headers))
forecasts = [c for c in folder["Children"] if c["Type"] == "Forecast"]
baseline = sorted(forecasts, key=lambda f: f["Versions"][-1]["CreatedAt"], reverse=True)[0]
print("Baseline:", baseline["Name"], "—", baseline["Path"])

# --- 2. Define the shock in 3FS and submit the solve ---
# MULTIPLY scales US consumption 2% over four quarters; FIX holds it on that
# path so the rest of the world solves around it.
commands = "MULTIPLY C:US 2026Q3 1.02, 1.02, 1.02, 1.02\nFIX C:US 2026Q3:2027Q2"

out_path = f"/me/us-consumption-shock-{int(time.time())}"   # unique name avoids re-run clashes
solve_request = {
    "InputForecast": baseline["Path"],
    "SolutionRange": {"From": "2026Q1", "To": "2030Q4"},
    "Commands": commands,
    "OutputForecast": out_path,
}
op = get_json(requests.post(f"{base_url}/v1/operations/solve", headers=headers, json=solve_request))
print("Solve queued:", op["Id"])

# --- 3. Wait for completion ---
op_id = op["Id"]
while op["Status"] in ("Queued", "InProgress"):
    op = get_json(requests.get(f"{base_url}/v1/operations/{op_id}/await", headers=headers))
if op["Status"] != "Succeeded":
    print("SOLVE FAILED:", op.get("FailureReason"))
    raise SystemExit
print(f"Solved in {op.get('Duration')}ms")

# --- 4. Pull GDP from baseline and scenario, compare ---
def gdp(forecast_id, groups=("US", "CHINA", "EURO_11")):
    sel = [{"IndicatorCode": "GDP", "GroupCode": g} for g in groups]
    data = get_json(requests.post(
        f"{base_url}/v1/forecast-contents/{forecast_id}/variables?onlyProps=Values",
        headers=headers, json=sel))
    return {v["GroupCode"]: {p["Period"]: p["Value"] for p in v["Values"]} for v in data}

scenario = get_json(requests.get(f"{base_url}/v1/resources{out_path}", headers=headers))
base_gdp, scen_gdp = gdp(baseline["Id"]), gdp(scenario["Id"])

for grp in ("US", "CHINA", "EURO_11"):
    print(f"\nGDP {grp} — scenario vs baseline:")
    for p in ("2026Q3", "2027Q1", "2027Q3", "2028Q1", "2029Q1"):
        b, s = base_gdp[grp].get(p), scen_gdp[grp].get(p)
        if b and s:
            print(f"   {p}: {100*(s-b)/b:+.2f}%")
            
            
            
#### visualization 



def to_x(p):                       # "2027Q3" -> 2027.5
    y, q = p.split("Q")
    return int(y) + (int(q) - 1) / 4

groups = ("US", "CHINA", "EURO_11")
colors = {"US": "tab:blue", "CHINA": "tab:red", "EURO_11": "tab:green"}
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 8))

# Top: % deviation from baseline
for g in groups:
    periods = [p for p in sorted(set(base_gdp[g]) & set(scen_gdp[g]), key=to_x)
               if 2025 <= to_x(p) <= 2031]
    x = [to_x(p) for p in periods]
    dev = [100 * (scen_gdp[g][p] - base_gdp[g][p]) / base_gdp[g][p] for p in periods]
    ax1.plot(x, dev, label=g, color=colors[g], lw=2)
ax1.axhline(0, color="gray", lw=0.8)
ax1.axvspan(2026.5, 2027.25, color="orange", alpha=0.15)   # the FIX window
ax1.set_title("GDP deviation from baseline — US consumption +2% shock")
ax1.set_ylabel("% difference from baseline"); ax1.legend(); ax1.grid(alpha=0.3)

# Bottom: US GDP in levels, baseline vs scenario
g = "US"
periods = [p for p in sorted(set(base_gdp[g]) & set(scen_gdp[g]), key=to_x)
           if 2025 <= to_x(p) <= 2031]
x = [to_x(p) for p in periods]
ax2.plot(x, [base_gdp[g][p] for p in periods], label="US baseline", color="black", lw=2)
ax2.plot(x, [scen_gdp[g][p] for p in periods], label="US scenario", color="tab:blue", lw=2, ls="--")
ax2.axvspan(2026.5, 2027.25, color="orange", alpha=0.15)
ax2.set_title("US GDP — levels")
ax2.set_ylabel("Real GDP (bn)"); ax2.set_xlabel("Year"); ax2.legend(); ax2.grid(alpha=0.3)

plt.tight_layout()
plt.savefig("scenario_vs_baseline.png", dpi=120)
plt.show()
print("Saved chart to scenario_vs_baseline.png")