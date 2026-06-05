import os, requests, json

base_url = 'https://model.oxfordeconomics.com/api'
access_token = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6Ik1EWTVSak5ETlVVMk0wRkZPRVpHTlVOQ016azBSakl6TkRNek5qazNSVUZDTmpBMlJVTTBNQSJ9.eyJodHRwczovL3d3dy5veGZvcmRlY29ub21pY3MuY29tL29lQWNjb3VudElkIjoiQURCIiwiaXNzIjoiaHR0cHM6Ly9veGVjb24uYXV0aDAuY29tLyIsInN1YiI6ImF1dGgwfDVkYTU5YTFhOGU3ZTBkMGM2YzJmMTkwNCIsImF1ZCI6WyJodHRwczovL21vZGVsLm94Zm9yZGVjb25vbWljcy5jb20iLCJodHRwczovL294ZWNvbi5hdXRoMC5jb20vdXNlcmluZm8iXSwiaWF0IjoxNzgwNTYyMzEzLCJleHAiOjE3ODA2NDg3MTMsInNjb3BlIjoib3BlbmlkIHByb2ZpbGUiLCJhenAiOiI2TW5qRTVDQW1udzN3Q0pmSG9IWE1hSXBGNURLNHIyMiJ9.c-pC2SPaneiaF4SccPnk2Bei5LsglFZoQCRtMY13QuARnPo-Z5irueUKd2k_Y0FFabiAI1xzLTYHtBPQN8kXV5KA1zJd54TWo8WEEQYkptj9BBdkZa4hER-b6DbK91oKyC5p6eBrg5sungYH303XxYtlm-Fi6eTA-X-N6LGrleI3NVoTsw8ThEGQPwwBmcqs669QTccE70yj2pQBpZMW_ySFvluKucCwEuPY3rqAwJVkO3wosw7kZ3ogSBiXIWUGkhessOA_YP6Y5iH15moFGW0iwzZInQZ_VLVkOL0NC5tzucjYAoKs-wk8D7zkC7b_5haDAimhkO73EEUNXZgsfA"
headers = {'Authorization': f'Bearer {access_token}'}


def get_json(resp):
    resp.raise_for_status()
    return json.loads(resp.content.decode("utf-8-sig"))

# 1. Find the latest GEM release — full folder name, spaces and all
gem_path = "oxford-economics/releases/Global Economic Model"
folder = get_json(requests.get(f"{base_url}/v1/resources/{gem_path}", headers=headers))
forecasts = [c for c in folder["Children"] if c["Type"] == "Forecast"]

if not forecasts:                       # safety net: forecasts might be nested deeper
    print("No forecasts directly here. Children are:")
    for c in folder["Children"]:
        print("  ", c["Type"], "|", c.get("Name"), "|", c.get("Path"))
    raise SystemExit

latest = sorted(forecasts, key=lambda f: f["Versions"][-1]["CreatedAt"], reverse=True)[0]
forecastId = latest["Id"]
print("Using forecast:", latest["Name"], "—", latest["Path"])

# 2. Peek at the available indicators and groups
indicators = get_json(requests.get(f"{base_url}/v1/forecast-contents/{forecastId}/indicators", headers=headers))
groups = get_json(requests.get(f"{base_url}/v1/forecast-contents/{forecastId}/groups", headers=headers))
print(f"\n{len(indicators)} indicators, {len(groups)} groups available")
print("Sample indicators:", [(i['Code'], i['Name']) for i in indicators[:5]])
print("Sample groups:", [(g['Code'], g['Name']) for g in groups[:5]])

# 3. Pull real GDP for three economies
selection = [{"IndicatorCode": "GDP", "GroupCode": g} for g in ["US", "CHINA", "EURO_11"]]
variables = get_json(requests.post(
    f"{base_url}/v1/forecast-contents/{forecastId}/variables?onlyProps=Values,Metadata",
    headers=headers, json=selection
))

# 4. Print the last few periods of each series (history runs into forecast)
for v in variables:
    md = v["Metadata"]
    print(f"\n{v['IndicatorCode']}:{v['GroupCode']} — {md.get('Description','')} ({md.get('Units','')})")
    for point in v["Values"][-40:]:
        print(f"   {point['Period']}: {point['Value']:.1f}")