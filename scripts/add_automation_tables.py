import sys

# Read the current db.py
with open('C:\\Users\\saura\\agentdesk\\backend\\app\\db.py', 'r') as f:
    content = f.read()

marker = 'CREATE INDEX IF NOT EXISTS idx_approvals_created ON approvals(created_at DESC);\n"""'

addition = '''

CREATE TABLE IF NOT EXISTS automations (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    prompt TEXT NOT NULL,
    interval_minutes INTEGER NOT NULL DEFAULT 15,
    workspace TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    last_run_at REAL,
    next_run REAL,
    last_status TEXT,
    last_summary TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_automations_next_run ON automations(next_run, status);
CREATE INDEX IF NOT EXISTS idx_automations_status ON automations(status);

CREATE TABLE IF NOT EXISTS automation_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    automation_id TEXT NOT NULL,
    status TEXT NOT NULL,
    summary TEXT,
    seconds REAL,
    started_at REAL NOT NULL,
    finished_at REAL,
    run_key TEXT NOT NULL UNIQUE,
    FOREIGN KEY (automation_id) REFERENCES automations(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_automation_runs_automation ON automation_runs(automation_id, started_at);
CREATE INDEX IF NOT EXISTS idx_automation_runs_run_key ON automation_runs(run_key);

'''

if marker in content:
    content = content.replace(marker, addition + marker)
    with open('C:\\Users\\saura\\agentdesk\\backend\\app\\db.py', 'w') as f:
        f.write(content)
    print('db.py updated successfully')
else:
    print('Could not find the target marker')
    idx = content.find('idx_approvals_created')
    if idx >= 0:
        print(repr(content[idx-50:idx+100]))
    sys.exit(1)