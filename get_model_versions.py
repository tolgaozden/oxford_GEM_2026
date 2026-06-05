
# %%

import requests, json, time
import matplotlib.pyplot as plt

def pkey(p):  y, q = p.split("Q"); return int(y)*4 + int(q)       # "2027Q3" -> sortable int
def to_x(p):  y, q = p.split("Q"); return int(y) + (int(q)-1)/4   # -> plot x-coordinate
def add_q(p, n): k = pkey(p)-1+n; return f"{k//4}Q{k%4+1}"        # advance a period

base_url = 'https://model.oxfordeconomics.com/api'
access_token = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6Ik1EWTVSak5ETlVVMk0wRkZPRVpHTlVOQ016azBSakl6TkRNek5qazNSVUZDTmpBMlJVTTBNQSJ9.eyJodHRwczovL3d3dy5veGZvcmRlY29ub21pY3MuY29tL29lQWNjb3VudElkIjoiQURCIiwiaXNzIjoiaHR0cHM6Ly9veGVjb24uYXV0aDAuY29tLyIsInN1YiI6ImF1dGgwfDVkYTU5YTFhOGU3ZTBkMGM2YzJmMTkwNCIsImF1ZCI6WyJodHRwczovL21vZGVsLm94Zm9yZGVjb25vbWljcy5jb20iLCJodHRwczovL294ZWNvbi5hdXRoMC5jb20vdXNlcmluZm8iXSwiaWF0IjoxNzgwNTYyMzEzLCJleHAiOjE3ODA2NDg3MTMsInNjb3BlIjoib3BlbmlkIHByb2ZpbGUiLCJhenAiOiI2TW5qRTVDQW1udzN3Q0pmSG9IWE1hSXBGNURLNHIyMiJ9.c-pC2SPaneiaF4SccPnk2Bei5LsglFZoQCRtMY13QuARnPo-Z5irueUKd2k_Y0FFabiAI1xzLTYHtBPQN8kXV5KA1zJd54TWo8WEEQYkptj9BBdkZa4hER-b6DbK91oKyC5p6eBrg5sungYH303XxYtlm-Fi6eTA-X-N6LGrleI3NVoTsw8ThEGQPwwBmcqs669QTccE70yj2pQBpZMW_ySFvluKucCwEuPY3rqAwJVkO3wosw7kZ3ogSBiXIWUGkhessOA_YP6Y5iH15moFGW0iwzZInQZ_VLVkOL0NC5tzucjYAoKs-wk8D7zkC7b_5haDAimhkO73EEUNXZgsfA"
headers = {'Authorization': f'Bearer {access_token}'}

def get_json(resp):
    resp.raise_for_status()
    return json.loads(resp.content.decode("utf-8-sig"))

# --- 1. Baseline = latest GEM release ---
gem_path = "oxford-economics/releases/Global Economic Model"
# ── Pinned baseline: the central forecast lives in 'Extension' ──
BASELINE_PATH = f"{gem_path}/Extension/May26_2 25yr"   # 25-yr central baseline
# (swap to "May26_2 5yr" to match the GSS scenarios' 2031Q4 range)

baseline = get_json(requests.get(f"{base_url}/v1/resources/{BASELINE_PATH}", headers=headers))
base_id = baseline["Id"]

fc_end = baseline["Versions"][-1]["Range"]["To"] if baseline.get("Versions") else "2050Q4"
SOLVE_END = min(["2035Q4", fc_end], key=pkey)          # 25-yr baseline → room to extend
print(f"Baseline pinned: {baseline['Name']} (Id {base_id}) | solving 2026Q1 -> {SOLVE_END}")


# --- 2. Define the shock in 3FS and submit the solve ---
# MULTIPLY scales US consumption 2% over four quarters; FIX holds it on that
# path so the rest of the world solves around it.
commands = "MULTIPLY C:US 2026Q3 1.02, 1.02, 1.02, 1.02\nFIX C:US 2026Q3:2027Q2"

# ── Discover the global oil price variable ──
indicators = get_json(requests.get(f"{base_url}/v1/forecast-contents/{base_id}/indicators", headers=headers))
groups = get_json(requests.get(f"{base_url}/v1/forecast-contents/{base_id}/groups", headers=headers))

#cands = [i for i in indicators if "oil" in i["Name"].lower()
#         and any(w in i["Name"].lower() for w in ("price", "brent", "barrel", "$/b"))]
#print("Oil-price candidates:", [(i["Code"], i["Name"]) for i in cands])
#OIL_CODE = cands[0]["Code"]

#all_codes = [g["Code"] for g in groups]
#likely = [c for c in ["WORLD", "OPEC", "GLOBAL", "OECD"] if c in all_codes]
#def oil_in(code):
#    r = requests.post(f"{base_url}/v1/forecast-contents/{base_id}/variables?onlyProps=Values",
#                      headers=headers, json=[{"IndicatorCode": OIL_CODE, "GroupCode": code}], timeout=30)
#    return r.status_code == 200 and bool((d := json.loads(r.content.decode("utf-8-sig"))) and d[0].get("Values"))
#found = [c for c in likely if oil_in(c)] or [c for c in all_codes if oil_in(c)]
#OIL_GROUP = "WORLD" if "WORLD" in found else found[0]
#print(f"Oil variable: {OIL_CODE}:{OIL_GROUP}")


asean_stems = ["indonesia", "malaysia", "thailand", "philippin", "singapore",
               "viet", "brunei", "cambodia", "lao", "myanmar"]
asean = [g["Code"] for g in groups if any(s in g["Name"].lower() for s in asean_stems)]
print("ASEAN economies found:", [(g["Code"], g["Name"]) for g in groups if g["Code"] in asean])

# bonus: is there a ready-made ASEAN bloc aggregate?
print("ASEAN aggregates:", [(g["Code"], g["Name"]) for g in groups if "asean" in g["Name"].lower()])