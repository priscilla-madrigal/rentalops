"""Local storage for maintenance requests and service providers."""
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

STATUSES = ['Find a provider', 'Awaiting response', 'Schedule a visit', 'Repair in progress', 'Verify repair', 'Closed']

def database_url():
    return os.environ.get('DATABASE_URL', '').strip()


class PostgresConnection:
    """Adapt our parameterized queries to PostgreSQL; never interpolate user values."""
    def __init__(self, db):
        self.db = db

    def execute(self, sql, args=()):
        sql = sql.replace('?', '%s').replace('CURRENT_TIMESTAMP',
            "to_char(CURRENT_TIMESTAMP AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS')")
        return self.db.execute(sql, args)

    def executescript(self, sql):
        for statement in sql.split(';'):
            if statement.strip():
                self.execute(statement.replace('INTEGER PRIMARY KEY', 'SERIAL PRIMARY KEY'))


@contextmanager
def connect():
    if database_url():
        import psycopg
        from psycopg.rows import dict_row
        with psycopg.connect(database_url(), row_factory=dict_row, connect_timeout=10) as db:
            yield PostgresConnection(db)
        return
    path = Path(os.environ.get('RENTAL_DB_PATH', 'data/rentals.db'))
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    try:
        with db:
            yield db
    finally:
        db.close()

def initialize():
    with connect() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS providers (
          id INTEGER PRIMARY KEY, name TEXT NOT NULL, specialty TEXT NOT NULL,
          zone TEXT NOT NULL, phone TEXT NOT NULL, notes TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS incidents (
          id INTEGER PRIMARY KEY, property TEXT NOT NULL, rental_type TEXT NOT NULL,
          description TEXT NOT NULL, specialty TEXT NOT NULL, priority TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'Find a provider', provider_id INTEGER,
          visit TEXT NOT NULL DEFAULT '', cost REAL);
        CREATE TABLE IF NOT EXISTS updates (
          id INTEGER PRIMARY KEY, incident_id INTEGER NOT NULL,
          note TEXT NOT NULL, created TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        ''')
        if database_url():
            columns = {row['name'] for row in db.execute("SELECT column_name AS name FROM information_schema.columns WHERE table_schema=current_schema() AND table_name='incidents'")}
        else:
            columns = {row['name'] for row in db.execute('PRAGMA table_info(incidents)')}
        if 'last_activity' not in columns:
            db.execute('ALTER TABLE incidents ADD COLUMN last_activity TEXT')
            # Recover known history dates without inventing dates for older requests.
            db.execute('UPDATE incidents SET last_activity=(SELECT MAX(created) FROM updates WHERE incident_id=incidents.id)')
        # Idempotently migrate structured labels from the original Spanish prototype.
        legacy_labels = {'Fontanería / goteras': 'Plumbing / leaks', 'Electricidad': 'Electrical', 'Techos y canoas': 'Roofing and gutters', 'Limpieza': 'Cleaning', 'Cerrajería': 'Locksmith', 'General / por definir': 'General / to be determined', 'Buscar proveedor': 'Find a provider', 'Esperar respuesta': 'Awaiting response', 'Coordinar visita': 'Schedule a visit', 'Reparación en curso': 'Repair in progress', 'Verificar reparación': 'Verify repair', 'Cerrado': 'Closed', 'Corta estancia': 'Short-term', 'Larga estancia': 'Long-term', 'Alta': 'High', 'Urgente': 'Urgent'}
        for old, new in legacy_labels.items():
            for column in ('status', 'specialty', 'rental_type', 'priority'):
                db.execute(f'UPDATE incidents SET {column}=? WHERE {column}=?', (new, old))
            db.execute('UPDATE providers SET specialty=? WHERE specialty=?', (new, old))

def rows(sql, args=()):
    with connect() as db:
        return [dict(row) for row in db.execute(sql, args).fetchall()]

def add_provider(name, specialty, zone, phone, notes):
    with connect() as db:
        db.execute('INSERT INTO providers (name,specialty,zone,phone,notes) VALUES (?,?,?,?,?)', (name,specialty,zone,phone,notes))

def add_incident(property_name, rental_type, description, specialty, priority, followup_note=''):
    with connect() as db:
        row = db.execute('INSERT INTO incidents (property,rental_type,description,specialty,priority,last_activity) VALUES (?,?,?,?,?,CURRENT_TIMESTAMP) RETURNING id', (property_name,rental_type,description,specialty,priority)).fetchone()
        if followup_note.strip():
            db.execute('INSERT INTO updates (incident_id,note) VALUES (?,?)', (row['id'], followup_note.strip()))
        return row['id']

def save_incident(id, status, provider_id, visit, cost, note):
    if status not in STATUSES or (cost is not None and cost < 0):
        raise ValueError('Invalid status or cost')
    with connect() as db:
        # Read and write under one transaction so the history matches the saved change.
        if not database_url():
            db.execute('BEGIN IMMEDIATE')
        lock = ' FOR UPDATE' if database_url() else ''
        previous = db.execute('SELECT status,provider_id,visit,cost FROM incidents WHERE id=?' + lock, (id,)).fetchone()
        if previous is None:
            raise ValueError('Maintenance request not found')
        events = []
        if previous['status'] != status:
            events.append(f"Status changed from {previous['status']} to {status}.")
        if previous['provider_id'] != provider_id:
            def provider_name(provider):
                if provider is None:
                    return 'Unassigned'
                row = db.execute('SELECT name FROM providers WHERE id=?', (provider,)).fetchone()
                if row is None:
                    raise ValueError('Service provider not found')
                return f"{row['name']} (#{provider})"
            events.append(f"Provider changed from {provider_name(previous['provider_id'])} to {provider_name(provider_id)}.")
        db.execute('UPDATE incidents SET status=?,provider_id=?,visit=?,cost=? WHERE id=?', (status,provider_id,visit,cost,id))
        if note.strip() or any(previous[field] != value for field, value in (
            ('status', status), ('provider_id', provider_id), ('visit', visit), ('cost', cost)
        )):
            db.execute('UPDATE incidents SET last_activity=CURRENT_TIMESTAMP WHERE id=?', (id,))
        for event in events:
            db.execute('INSERT INTO updates (incident_id,note) VALUES (?,?)', (id,event))
        if note.strip():
            db.execute('INSERT INTO updates (incident_id,note) VALUES (?,?)', (id,note.strip()))
