# RELIEF360 — PostgreSQL edition

This project connects the EOC webpages to your **existing PostgreSQL server** and **relief360 database** through a Python backend. pgAdmin and the webpage use the same PostgreSQL tables. There is no SQLite database or separate copy of your operational records.

## Windows: first setup

You have already created the empty `relief360` database in pgAdmin, owned by `postgres`.

1. Extract this ZIP into a new folder. Use this PostgreSQL edition rather than the earlier SQLite ZIP.
2. Open the extracted `RELIEF360` folder.
3. Double-click **SETUP_WINDOWS.bat**. It installs the Python PostgreSQL driver and starts database setup. Internet is needed for this first dependency installation.
4. At each prompt, press Enter to accept these defaults unless your PostgreSQL server uses different settings:

| Setting | Default |
|---|---|
| Host | localhost |
| Port | 5432 |
| Database | relief360 |
| PostgreSQL user | postgres |

5. Type your PostgreSQL server password at the password prompt and press Enter. **No characters appear while you type; that is normal.** This is the password you chose when installing PostgreSQL, not your web login password.
6. Wait for `Connected successfully. Tables and demonstration accounts are ready.`
7. In pgAdmin, expand **Databases → relief360 → Schemas → public**. Right-click **Tables → Refresh**. You should see 24 tables: the 23 submitted relations plus the normalized distribution-source relation.

The setup keeps the existing database and creates missing project tables. It seeds clearly labeled demonstration records/accounts only when the account table is empty. Re-running setup does not clear your records. `CREATE TABLE IF NOT EXISTS` is not a migration tool for incompatible existing tables; this package targets your newly created empty database.

## Start the webpage

1. Double-click **START_WINDOWS.bat**.
2. Enter your PostgreSQL password when prompted. Keep this terminal open.
3. Open **http://localhost:8000/login.html** in your browser.
4. Sign in with:

**Email:** `admin@relief360.local`  
**Initial web password:** `Relief360!2026`

Use Change password after signing in. PostgreSQL's password and the website account password are separate.

If double-click launch does not work, open a terminal in this folder:

```bat
py -m pip install -r requirements.txt
py setup_database.py
py server.py
```

On macOS/Linux use `python3` instead of `py`. Python 3.10+ is recommended. If port 8000 is occupied, run `py server.py --port 8001` and open localhost:8001.

Do not open the HTML directly or through VS Code Live Server: the Python backend must be running.

## Verify both directions

### Webpage → PostgreSQL

1. Sign in as admin.
2. Open Disasters and add a disaster, then Camps and add a camp belonging to it.
3. In pgAdmin, select **relief360**, open Query Tool and execute:

```sql
select * from public.disaster order by disaster_id desc;
select * from public.camp order by camp_id desc;
```

The webpage records should appear in these query results. Re-execute SELECT after each webpage change; an already displayed pgAdmin result grid does not automatically refresh.

### PostgreSQL → webpage

Find the camp ID returned by the query above. Replace `YOUR_CAMP_ID` with that number:

```sql
update public.camp
set camp_name = 'Updated through pgAdmin'
where camp_id = YOUR_CAMP_ID;
```

Commit if pgAdmin auto-commit is off. The Camps webpage checks for changes every 15 seconds when no form/search is active. Press browser Refresh for immediate display. Dashboard/reports update when refreshed. No cached mock dataset is used.

Safe direct edits include names, descriptions, contact details and stock balances. Database constraints still apply. For distributions/transfers, use the webpage workflows: those perform the multi-table stock operations. Inserting raw distribution rows in pgAdmin requires a complete source/recipient/item transaction and does not by itself run the application's stock-movement service.

## Features and permissions

The application supports disaster/camp registration, victim registration and camp-stay history, transfer/release, missing-person matching/reunification, volunteer assignment history, monetary donations with receipts, camp inventory/reorder reports, multi-item distributions, medical cases/treatment, vehicle allocation/returns, internal alerts, live dashboard counts, search, reports and CSV export.

| Initial account | Role | Writes allowed |
|---|---|---|
| admin@relief360.local | Admin | All modules; user creation |
| ngo@relief360.local | NGO | Camps, victims, missing reports, volunteers, donations, stock, distributions, vehicles |
| medical@relief360.local | Medical | Medical cases; assigned/unassigned treatment updates |
| volunteer@relief360.local | Volunteer | Victims and missing reports |

All four initial web passwords are `Relief360!2026`. Admin can create more accounts through User accounts in the header. All signed-in accounts can read operational listings/reports in this local demonstration; access is not scoped to an individual camp or NGO.

The server binds to 127.0.0.1 for local project use. This package does not claim production hosting, fine-grained privacy controls, SMS/email delivery, warehouse management or material-donation receipts. External map/Chart.js resources need Internet; core forms/reports have local offline styling.

## Database integrity

The schema uses PostgreSQL identity keys, real date/timestamp columns, foreign keys, check constraints, partial unique indexes, case-insensitive account-email uniqueness and PL/pgSQL relationship guards. Deferred constraint triggers require exactly one source, exactly one recipient and at least one line per distribution at COMMIT—even for pgAdmin writes. Application stock operations are atomic and serialized; insufficient balances roll back the entire distribution.

Balances are per camp. A camp transfer debits the source and credits the destination. A victim distribution debits the source. Amounts are stored as integer paise and displayed as decimal rupees. Occupancy/status reports and dashboard totals are derived from saved rows.

See `database/SCHEMA_NOTES.md` for changes from the submitted design. The original ER figure still needs those corrections.

## Password/configuration

`db_config.json` stores only host, port, database and username. Passwords are prompted locally and remain in the running process only. If you already use PostgreSQL environment variables, PGHOST/PGPORT/PGDATABASE/PGUSER/PGPASSWORD override the file. Do not share files containing credentials.

Sessions expire after eight hours and end when the server restarts. Web passwords are salted PBKDF2 hashes; writes require session/CSRF validation and server-side role checks.

## Troubleshooting

- `password authentication failed`: enter the PostgreSQL server password. It is not `Relief360!2026` unless you intentionally chose that password for PostgreSQL too.
- `connection refused`: start PostgreSQL and check host/port against the server connection properties in pgAdmin.
- `database relief360 does not exist`: check the spelling and that pgAdmin and the backend refer to the same server/port.
- `No module named psycopg`: run `py -m pip install -r requirements.txt` using the same Python launcher you use for the server.
- Tables not visible: right-click Tables → Refresh under relief360 → Schemas → public.
- SQL changes not visible: commit the transaction and refresh the webpage; verify you edited relief360 rather than another database.
- Startup remains necessary for webpage use. pgAdmin need not stay open, but the PostgreSQL service must be running.

## Backup

Use pgAdmin: right-click **relief360 → Backup**. Alternatively, `py backup.py` uses your installed PostgreSQL pg_dump and writes a consistent SQL backup to backups/. No database dump is included in this package.

## Tests

`node test_frontend.cjs` checks module rendering/field mappings/HTML escaping with stubs; it is not a visual browser test.

`test_project.py` is a reusable HTTP integration suite. It writes records and must run only against a separate disposable database whose name ends in `_test`, with `RELIEF360_TEST_DATABASE=1` set. Do not run it against relief360. Configure PGDATABASE/PGUSER/PGPORT/PGHOST/PGPASSWORD for the test server first. It never drops your database or tables.

See VALIDATION.txt for the actual checks performed on this edition. A connection to your computer cannot be verified from this workspace; local setup performs that check.
