%% GEM oil price shock — MATLAB port
% Set your token once per session:  setenv('OE_TOKEN','eyJ...')

baseUrl = 'https://model.oxfordeconomics.com/api';
setenv('OE_TOKEN',...
    'eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6Ik1EWTVSak5ETlVVMk0wRkZPRVpHTlVOQ016azBSakl6TkRNek5qazNSVUZDTmpBMlJVTTBNQSJ9.eyJodHRwczovL3d3dy5veGZvcmRlY29ub21pY3MuY29tL29lQWNjb3VudElkIjoiQURCIiwiaXNzIjoiaHR0cHM6Ly9veGVjb24uYXV0aDAuY29tLyIsInN1YiI6ImF1dGgwfDVkYTU5YTFhOGU3ZTBkMGM2YzJmMTkwNCIsImF1ZCI6WyJodHRwczovL21vZGVsLm94Zm9yZGVjb25vbWljcy5jb20iLCJodHRwczovL294ZWNvbi5hdXRoMC5jb20vdXNlcmluZm8iXSwiaWF0IjoxNzgwNTYyMzEzLCJleHAiOjE3ODA2NDg3MTMsInNjb3BlIjoib3BlbmlkIHByb2ZpbGUiLCJhenAiOiI2TW5qRTVDQW1udzN3Q0pmSG9IWE1hSXBGNURLNHIyMiJ9.c-pC2SPaneiaF4SccPnk2Bei5LsglFZoQCRtMY13QuARnPo-Z5irueUKd2k_Y0FFabiAI1xzLTYHtBPQN8kXV5KA1zJd54TWo8WEEQYkptj9BBdkZa4hER-b6DbK91oKyC5p6eBrg5sungYH303XxYtlm-Fi6eTA-X-N6LGrleI3NVoTsw8ThEGQPwwBmcqs669QTccE70yj2pQBpZMW_ySFvluKucCwEuPY3rqAwJVkO3wosw7kZ3ogSBiXIWUGkhessOA_YP6Y5iH15moFGW0iwzZInQZ_VLVkOL0NC5tzucjYAoKs-wk8D7zkC7b_5haDAimhkO73EEUNXZgsfA')
token   = getenv('OE_TOKEN');                 % token kept out of the file

opts = weboptions('HeaderFields', {'Authorization', ['Bearer ' token]}, ...
                  'MediaType',   'application/json', ...   % JSON request bodies
                  'ContentType', 'text', ...              % raw response text back
                  'Timeout', 60);

% BOM-safe JSON helpers (equivalent of get_json)
getJson  = @(url)       jsondecode(regexprep(webread(url, opts),                  '^\x{FEFF}', ''));
postJson = @(url, body) jsondecode(regexprep(webwrite(url, jsonencode(body), opts),'^\x{FEFF}', ''));

%% 1. Pinned baseline — the central forecast lives in 'Extension'
gemPath      = 'oxford-economics/releases/Global Economic Model';
baselinePath = [gemPath '/Extension/May26_2 25yr'];     % swap to 'May26_2 5yr' for the 2031Q4 range
baselineUrl  = [baseUrl '/v1/resources/' strrep(baselinePath, ' ', '%20')];

baseline = getJson(baselineUrl);
baseId   = baseline.Id;

fcEnd = '2050Q4';
try
    V = baseline.Versions;
    if iscell(V), last = V{end}; else, last = V(end); end
    fcEnd = last.Range.To;
catch
end
cands = {'2035Q4', fcEnd};
[~, idx]  = min(cellfun(@pkey, cands));
SOLVE_END = cands{idx};
fprintf('Baseline pinned: %s (Id %s) | solving 2026Q1 -> %s\n', baseline.Name, baseId, SOLVE_END);

%% 2. Define the shock in 3FS and submit the solve
OIL_CODE  = 'WPO';        % World oil price, Brent crude spot, US$/barrel
OIL_GROUP = 'WORLD';

commands = sprintf(['MULTIPLY %s:%s 2026Q3 1.10, 1.10, 1.10, 1.10\n' ...
                    'FIX %s:%s 2026Q3:2027Q2'], OIL_CODE, OIL_GROUP, OIL_CODE, OIL_GROUP);

outPath = sprintf('/me/oil-shock-%d', round(posixtime(datetime('now','TimeZone','UTC'))));
req = struct('InputForecast',  baseline.Path, ...
             'SolutionRange',   struct('From','2026Q1','To','2030Q4'), ...
             'Commands',        commands, ...
             'OutputForecast',  outPath);
op = postJson([baseUrl '/v1/operations/solve'], req);
fprintf('Solve queued: %s\n', op.Id);

%% 3. Wait for completion
opId = op.Id;
while ismember(op.Status, {'Queued','InProgress'})
    op = getJson([baseUrl '/v1/operations/' opId '/await']);
end
if ~strcmp(op.Status, 'Succeeded')
    if isfield(op,'FailureReason'), error('SOLVE FAILED: %s', op.FailureReason); else, error('SOLVE FAILED'); end
end
if isfield(op,'Duration'), fprintf('Solved in %g ms\n', op.Duration); else, fprintf('Solved\n'); end

%% 4. Pull GDP from baseline and scenario, compare
groups = {'US','CHINA','EURO_11','INDONESI','MALAYSIA','PHILIPPI','SINGPORE', ...
          'THAILAND','VIETNAM'};

scenario = getJson([baseUrl '/v1/resources' outPath]);
baseGdp  = gdp(baseUrl, baseId,      groups, postJson);
scenGdp  = gdp(baseUrl, scenario.Id, groups, postJson);

checkPeriods = {'2026Q3','2027Q1','2027Q3','2028Q1','2029Q1'};
for gi = 1:numel(groups)
    grp = groups{gi};
    if ~isKey(baseGdp, grp) || ~isKey(scenGdp, grp)
        fprintf('\nGDP %s — (no data returned)\n', grp); continue;
    end
    fprintf('\nGDP %s — scenario vs baseline:\n', grp);
    bm = baseGdp(grp); sm = scenGdp(grp);
    for pi = 1:numel(checkPeriods)
        p = checkPeriods{pi};
        if isKey(bm,p) && isKey(sm,p)
            b = bm(p); s = sm(p);
            fprintf('   %s: %+.2f%%\n', p, 100*(s-b)/b);
        end
    end
end

%% Visualization — GDP deviation from baseline
toX = @(p) str2double(extractBefore(p,'Q')) + (str2double(extractAfter(p,'Q'))-1)/4;

plotGroups = {'US','CHINA','EURO_11','INDONESI','MALAYSIA','PHILIPPI','SINGPORE','THAILAND','VIETNAM'};
cmap = lines(numel(plotGroups));            % auto palette (replaces the partial color dict)

fig = figure('Position',[100 100 760 460]);
ax1 = axes(fig); hold(ax1,'on');

for i = 1:numel(plotGroups)
    g = plotGroups{i};
    if ~isKey(baseGdp, g) || ~isKey(scenGdp, g)     % skip groups with no data
        continue;
    end
    bm = baseGdp(g); sm = scenGdp(g);
    P = intersect(keys(bm), keys(sm));              % periods present in both
    x = cellfun(toX, P);
    keep = x >= 2025 & x <= 2031;
    P = P(keep); x = x(keep);
    if isempty(x), continue; end
    [x, order] = sort(x); P = P(order);
    dev = cellfun(@(p) 100*(sm(p) - bm(p))/bm(p), P);
    plot(ax1, x, dev, 'LineWidth', 2, 'Color', cmap(i,:), 'DisplayName', g);
end

yline(ax1, 0, 'Color', [.5 .5 .5], 'LineWidth', 0.8, 'HandleVisibility','off');

% shaded FIX window 2026Q3–2027Q2
yl = ylim(ax1);
patch(ax1, [2026.5 2027.25 2027.25 2026.5], yl([1 1 2 2]), [1 0.6 0], ...
      'FaceAlpha', 0.15, 'EdgeColor', 'none', 'HandleVisibility', 'off');
ylim(ax1, yl);

title(ax1, 'GDP deviation from baseline — global oil +10% shock');
ylabel(ax1, '% difference from baseline');
legend(ax1, 'Location', 'best');
grid(ax1, 'on');

exportgraphics(fig, 'scenario_vs_baseline.png', 'Resolution', 120);
disp('Saved chart to scenario_vs_baseline.png');


%% ---- local functions (must sit at the end of the script) ----
function k = pkey(p)
    v = sscanf(p, '%dQ%d');           % "2027Q3" -> [2027; 3]
    k = v(1)*4 + v(2);
end

function out = gdp(baseUrl, fid, groups, postJson)
    sel  = struct('IndicatorCode', repmat({'GDP'}, 1, numel(groups)), 'GroupCode', groups);
    url  = [baseUrl '/v1/forecast-contents/' fid '/variables?onlyProps=Values'];
    data = postJson(url, sel);
    out  = containers.Map('KeyType','char','ValueType','any');
    for i = 1:numel(data)
        if iscell(data), v = data{i}; else, v = data(i); end
        if isempty(v.Values), continue; end
        out(v.GroupCode) = containers.Map({v.Values.Period}, num2cell([v.Values.Value]));
    end
end


