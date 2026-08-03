-- Sabong Arena (Cockfighting) Event & Fight Tracking
-- Revenue: plasada (house commission), event fees, concessions
-- Personnel: handlers, security, staff (same roster/payroll as ice plant)
-- Multi-tenant: Each boss owns an arena with isolated data

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'staff' CHECK(role IN ('super_admin', 'admin', 'boss', 'staff')),
    boss_id INTEGER,
    arena_name TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (boss_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

-- Events: hackfights, regular derbies, special tournaments
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    boss_id INTEGER NOT NULL REFERENCES users(id),
    arena_id TEXT NOT NULL,
    date TEXT NOT NULL,
    name TEXT NOT NULL,
    event_type TEXT NOT NULL CHECK(event_type IN ('hackfight','derby','tournament','special')),
    location TEXT,
    note TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    created_by TEXT,
    deleted_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_events_boss_id ON events(boss_id);
CREATE INDEX IF NOT EXISTS idx_events_date ON events(date);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);

-- Individual fights within an event
CREATE TABLE IF NOT EXISTS fights (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    boss_id INTEGER NOT NULL REFERENCES users(id),
    event_id INTEGER NOT NULL REFERENCES events(id),
    fight_number INTEGER,
    date TEXT NOT NULL,
    meron_owner TEXT,
    wala_owner TEXT,
    winner TEXT CHECK(winner IN ('Meron','Wala','Draw',NULL)),
    plasada_amount REAL,
    pit_fee REAL,
    notes TEXT,
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','live','finished')),
    started_at TEXT,
    finished_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    created_by TEXT,
    deleted_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_fights_boss_id ON fights(boss_id);
CREATE INDEX IF NOT EXISTS idx_fights_event_id ON fights(event_id);
CREATE INDEX IF NOT EXISTS idx_fights_date ON fights(date);

-- Live bets placed on fights
CREATE TABLE IF NOT EXISTS fight_bets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    boss_id INTEGER NOT NULL REFERENCES users(id),
    fight_id INTEGER NOT NULL REFERENCES fights(id),
    side TEXT NOT NULL CHECK(side IN ('Meron','Wala')),
    amount REAL NOT NULL,
    bettor_name TEXT,
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','won','lost','push')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    created_by TEXT,
    deleted_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_fight_bets_boss_id ON fight_bets(boss_id);
CREATE INDEX IF NOT EXISTS idx_fight_bets_fight_id ON fight_bets(fight_id);
CREATE INDEX IF NOT EXISTS idx_fight_bets_side ON fight_bets(side);
CREATE INDEX IF NOT EXISTS idx_fight_bets_date ON fight_bets(created_at);

-- Revenue: each fight generates plasada (house commission), pit fees, misc revenue per event
CREATE TABLE IF NOT EXISTS event_revenue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    boss_id INTEGER NOT NULL REFERENCES users(id),
    event_id INTEGER NOT NULL REFERENCES events(id),
    date TEXT NOT NULL,
    source TEXT NOT NULL CHECK(source IN ('plasada','pit_fee','gate','concession','sponsor','other')),
    amount REAL NOT NULL,
    description TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    created_by TEXT,
    deleted_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_event_revenue_boss_id ON event_revenue(boss_id);
CREATE INDEX IF NOT EXISTS idx_event_revenue_event_id ON event_revenue(event_id);
CREATE INDEX IF NOT EXISTS idx_event_revenue_date ON event_revenue(date);

-- Expenses: feed, supplies, prizes, staff bonuses, etc
CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    boss_id INTEGER NOT NULL REFERENCES users(id),
    date TEXT NOT NULL,
    amount REAL NOT NULL,
    description TEXT,
    category TEXT,
    note TEXT,
    remittance_id INTEGER REFERENCES cash_remittances(id),
    source TEXT NOT NULL DEFAULT 'manual',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    created_by TEXT,
    deleted_at TEXT,
    ref_number TEXT
);

CREATE INDEX IF NOT EXISTS idx_expenses_boss_id ON expenses(boss_id);
CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(date);
CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses(category);
CREATE INDEX IF NOT EXISTS idx_expenses_remittance_id ON expenses(remittance_id);

-- Cash remittances (to owner/HQ)
CREATE TABLE IF NOT EXISTS cash_remittances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    boss_id INTEGER NOT NULL REFERENCES users(id),
    date TEXT NOT NULL,
    amount REAL NOT NULL,
    note TEXT,
    proof_filename TEXT,
    source TEXT NOT NULL DEFAULT 'manual',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    created_by TEXT,
    deleted_at TEXT,
    ref_number TEXT
);

CREATE INDEX IF NOT EXISTS idx_cash_remittances_boss_id ON cash_remittances(boss_id);
CREATE INDEX IF NOT EXISTS idx_cash_remittances_date ON cash_remittances(date);

-- Explicit transaction links for manual remittances
CREATE TABLE IF NOT EXISTS remittance_events (
    remittance_id INTEGER NOT NULL REFERENCES cash_remittances(id),
    event_id INTEGER NOT NULL REFERENCES events(id),
    PRIMARY KEY (remittance_id, event_id)
);

-- Proof files for remittances
CREATE TABLE IF NOT EXISTS remittance_proofs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    remittance_id INTEGER NOT NULL REFERENCES cash_remittances(id),
    filename TEXT NOT NULL,
    original_filename TEXT,
    uploaded_at TEXT NOT NULL DEFAULT (datetime('now')),
    uploaded_by TEXT,
    deleted_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_remittance_proofs_remittance_id ON remittance_proofs(remittance_id);

-- Proof verification audit trail
CREATE TABLE IF NOT EXISTS proof_verifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    note TEXT,
    verified_by TEXT,
    verified_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_proof_verifications_lookup ON proof_verifications(kind, entity_id, verified_at DESC, id DESC);

-- Reference number counters
CREATE TABLE IF NOT EXISTS reference_counters (
    counter_key TEXT PRIMARY KEY,
    next_value INTEGER NOT NULL DEFAULT 1
);

-- Personnel: handlers, security, administrative staff
CREATE TABLE IF NOT EXISTS personnel (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    boss_id INTEGER NOT NULL REFERENCES users(id),
    name TEXT NOT NULL,
    position TEXT NOT NULL CHECK(position IN ('pit_manager','referee','cashier','security','cleaner','other')),
    contact_number TEXT,
    date_hired TEXT,
    status TEXT NOT NULL DEFAULT 'Active' CHECK(status IN ('Active','Inactive')),
    rate_per_shift REAL,
    user_id INTEGER REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    created_by TEXT,
    deleted_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_personnel_boss_id ON personnel(boss_id);
CREATE INDEX IF NOT EXISTS idx_personnel_status ON personnel(status);
CREATE INDEX IF NOT EXISTS idx_personnel_position ON personnel(position);
CREATE UNIQUE INDEX IF NOT EXISTS idx_personnel_user_id_unique
    ON personnel(user_id) WHERE user_id IS NOT NULL AND deleted_at IS NULL;

-- Fixed 3 shifts
CREATE TABLE IF NOT EXISTS shift_types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT,
    updated_by TEXT
);

-- Daily shift roster
CREATE TABLE IF NOT EXISTS shift_roster (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    boss_id INTEGER NOT NULL REFERENCES users(id),
    date TEXT NOT NULL,
    shift_type_id INTEGER NOT NULL REFERENCES shift_types(id),
    personnel_id INTEGER NOT NULL REFERENCES personnel(id),
    status TEXT NOT NULL DEFAULT 'Present' CHECK(status IN ('Present','Late','Absent')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    created_by TEXT,
    updated_at TEXT,
    updated_by TEXT,
    deleted_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_shift_roster_boss_id ON shift_roster(boss_id);
CREATE INDEX IF NOT EXISTS idx_shift_roster_date ON shift_roster(date);
CREATE INDEX IF NOT EXISTS idx_shift_roster_personnel ON shift_roster(personnel_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_shift_roster_unique_active
    ON shift_roster(date, shift_type_id, personnel_id) WHERE deleted_at IS NULL;

-- Penalties & deductions (late, absence, loans, SSS, etc)
CREATE TABLE IF NOT EXISTS personnel_penalties (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    boss_id INTEGER NOT NULL REFERENCES users(id),
    personnel_id INTEGER NOT NULL REFERENCES personnel(id),
    date TEXT NOT NULL,
    type TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'penalty' CHECK(category IN ('penalty','deduction')),
    description TEXT,
    amount REAL NOT NULL,
    is_auto INTEGER NOT NULL DEFAULT 0,
    source_roster_id INTEGER REFERENCES shift_roster(id),
    recurring INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    created_by TEXT,
    deleted_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_personnel_penalties_boss_id ON personnel_penalties(boss_id);
CREATE INDEX IF NOT EXISTS idx_personnel_penalties_personnel_date ON personnel_penalties(personnel_id, date);
CREATE INDEX IF NOT EXISTS idx_personnel_penalties_source_roster ON personnel_penalties(source_roster_id);
