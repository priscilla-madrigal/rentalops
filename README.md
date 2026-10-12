# RentalOps

A maintenance coordination assistant for short-term and long-term rental properties, inspired by a property owner's workflow in Costa Rica: receive a tenant's report, find an available service provider, coordinate access, and verify the repair.

## Business problem

Maintenance coordination is scattered across WhatsApp conversations. Owners need to know which repairs are unresolved, who has been contacted, and whose confirmation is pending. RentalOps brings that follow-up into one place and builds a reusable provider directory.

## Run locally

Requires Python 3.12. From this repository's directory:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/streamlit run app.py
```

Open the address Streamlit prints on your computer. Press Ctrl+C to stop the app.

Google sign-in must be configured before you can access the application. Follow [Google sign-in setup](GOOGLE_SIGN_IN.md). For local development, use `http://localhost:8501/oauth2callback` as the redirect URI in both Google and `.streamlit/secrets.toml`. There is no public-access bypass.

## Try the workflow

1. In **Service providers**, add a fictional contact with the **Roofing and gutters** specialty.
2. In **Maintenance requests**, report a leak at a demo property.
3. In **Details and follow-up**, record the contacts you approached and their replies in follow-up notes.
4. Assign a provider and record a visit time confirmed with the tenant.
5. Record the cost and repair verification, then click **Close repair**. This saves the form, closes the request, and records a closure note.

Status changes and provider assignments, reassignments, and removals are recorded automatically in **Follow-up history**, with UTC timestamps. Saving unchanged values does not create duplicate change events. Your manual notes are recorded separately. Automatic history starts with new changes; it does not reconstruct earlier actions.

After a successful save, the follow-up note box clears while the saved note remains in history. **Last activity (UTC)** shows request creation or the latest saved change or note. Saving unchanged values does not refresh this date. Older requests use their latest recorded history date when available; otherwise they show **Not recorded**.

The WhatsApp button opens a draft for you to review and send manually. It does not confirm delivery or receive replies. Use your own or fictional numbers when testing.

## Code structure

- `app.py`: Streamlit screens, forms, and WhatsApp links.
- `access.py`: Google sign-in gate and verified-email authorization.
- `ai_intake.py`: OpenAI structured extraction and response validation, without database writes.
- `intake_screen.py`: editable AI draft and explicit owner approval before saving.
- `storage.py`: parameterized SQL queries and SQLite transactions.
- `data/rentals.db`: local records, excluded from Git. Set `RENTAL_DB_PATH` to use another location.
- `tests/test_workflow.py`: persistence, validation, and interface workflow tests.
- `tests/test_postgres.py`: integration tests against a dedicated disposable PostgreSQL database. Never point `TEST_DATABASE_URL` at business data: these tests clear their tables.

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Records survive restarts if the SQLite file is retained. Note timestamps use UTC; visit times are free-form text agreed by the people involved. Existing Spanish category and status labels are migrated automatically; user-written descriptions and notes are preserved.

## Persistent storage with Neon

RentalOps uses PostgreSQL when `DATABASE_URL` is configured; otherwise it uses local SQLite. An invalid PostgreSQL connection does not silently fall back to SQLite. The sidebar shows which storage is active. External PostgreSQL keeps records outside Streamlit's temporary filesystem, but backups and retention depend on your database provider and plan.

1. Create an account at https://neon.tech and a PostgreSQL project for the demo. Review the current plan limits and pricing before selecting a plan.
2. In Neon's connection dialog, copy the Python/libpq PostgreSQL connection string. Keep its supplied TLS settings (including `sslmode=require` and `channel_binding=require` when provided). Do not paste it into chat, source code, or GitHub.
3. In your Streamlit Community Cloud app settings, open **Secrets** and add the following entry, replacing the placeholder privately:

   ```toml
   DATABASE_URL = "YOUR_NEON_CONNECTION_STRING"
   ```

4. Save and let the app restart. The sidebar should show **Storage: PostgreSQL (external database)**. RentalOps creates its tables automatically.
5. Create a fictional request and note. Reboot the app using Streamlit's app controls, then check that both still exist. This is the hosted persistence acceptance check; it must be completed after configuring Neon.

For local use, set `DATABASE_URL` as an environment variable or put the entry in `.streamlit/secrets.toml` (ignored by Git). The SQLite tests continue to run with a temporary database; the PostgreSQL integration test is skipped locally unless `TEST_DATABASE_URL` is set. GitHub Actions supplies a disposable PostgreSQL service so that test runs in CI.

Switching storage does not import existing SQLite records or delete the old file. The new database starts empty. If you need to retain old records, export them before switching and plan a separate migration. Continue using fictional data: database persistence does not add authentication or restrict access to the public app.

## Automated checks in GitHub

The workflow in `.github/workflows/tests.yml` runs on every push and pull request. It installs Python 3.12 and the dependencies, then runs the persistence, validation, and Streamlit interface tests with temporary SQLite databases and a disposable PostgreSQL service. No business records or external service credentials are needed.

To see a result, open the repository's **Actions** tab, select **Python tests**, and open the run for your commit. A green check means that run passed; a red cross means a step failed. Open **Python 3.12 tests → Run workflow and interface tests** to read the test output. You can also start a run using **Run workflow**.

These checks report failures but do not block Streamlit deployment from `main`. To gate future releases, use pull requests and configure a branch rule requiring **Python 3.12 tests** to pass before merging. Branch protection has not been configured yet. Automated tests also do not replace checking the deployed application in a browser.

## Current scope

The prototype records requests, contacts, notes, visits, and costs. **AI intake** prepares editable maintenance drafts from text reports when an OpenAI API key is configured. Follow the [AI pilot and setup guide](docs/AI_INTAKE.md) for configuration, limitations, and evaluation. Generating a draft does not save a request or contact a provider. It does not store videos, receive WhatsApp messages, or automate notifications. Dashboard counters reflect recorded state rather than automated monitoring.

The owner has deployed the prototype to Streamlit Community Cloud and verified repair closure and Neon persistence after a reboot. Google sign-in and a verified-email allowlist protect application access once configured; without configuration, records remain blocked. The real Google login flow still requires hosted browser validation. All approved users share the same records. Continue using fictional data until data protection, backups, and access configuration have been verified. Operational monitoring is not implemented yet.

## Roadmap

1. Continue validating maintenance workflows with the property owner.
2. Add persistent storage and access control for business use.
3. Make automated checks required before merging release changes.
4. Add operational metrics and alerts.
5. Integrate the official WhatsApp API.
6. Evaluate AI-assisted extraction of structured maintenance requests.

The portfolio will document the problem, implementation decisions, deployment, and measured outcomes as those stages are completed.
