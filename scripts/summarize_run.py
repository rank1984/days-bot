import re, json, sys

log = open(sys.argv[1], encoding='utf-8').read()

def find(pat, default=None):
    m = re.search(pat, log)
    return m.group(1) if m else default

pre = int(find(r'Pre-scan DB state:\s+snapshots:\s+(\d+)', 0))
saved = int(find(r'V5\.0\.6 snapshots saved:\s+(\d+)', 0))

summary = {
    "run": find(r'Run:\s+(\d+)'),
    "time_et": find(r'ET:\s+(\d{2}:\d{2})'),
    "event": find(r'Event:\s+(\w+)'),
    "is_scheduled": find(r'IS_SCHEDULED:\s+(\d)'),
    "in_pm_window": find(r'IN_PM_WINDOW:\s+(\d)'),
    "preflight_passed": find(r'PREFLIGHT_PASSED:\s+(\d)'),
    "universe": find(r'Final:\s+(\d+) symbols'),
    "strict": find(r'Discovery returned (\d+) candidates'),
    "liquidity_rejects": find(r'Liquidity rejects:\s+(\d+)'),
    "dataquality_blocked": find(r'DataQuality blocked:\s+(\d+)'),
    "plan_blocked": len(re.findall(r'PLAN_BLOCKED', log)),
    "plan_blocked_list": re.findall(r'PLAN_BLOCKED (\w+) \| reason=(\S+)', log),
    "top5_returned": find(r'Top 5 returned:\s+(\d+)'),
    "pre_scan_snapshots": pre,
    "post_scan_snapshots": pre + saved,
}

print(json.dumps(summary, ensure_ascii=False, indent=2))
