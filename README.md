# LocalBiz Manager

A responsive point-of-sale and inventory app for Nigerian small retailers. It supports business workspaces, staff roles, stock tracking, sales and split payments, customer credit, expenses, and profit reports.

## Requirements

- Python 3.10 or later
- VS Code with the Python extension
- For hosted deployments: a Supabase project and its PostgreSQL connection string

## Windows setup (VS Code)

1. Open this folder in VS Code and open **Terminal → New Terminal** (PowerShell).
2. Create and activate a virtual environment:

   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

   If PowerShell blocks activation, use `venv\Scripts\activate.bat` from Command Prompt, or run `.\venv\Scripts\python.exe` explicitly.

3. Install dependencies:

   ```powershell
   pip install -r requirements.txt
   ```

4. Create a local environment file and set a unique secret:

   ```powershell
   Copy-Item .env.example .env
   ```

   Edit `.env`; at minimum replace `JWT_SECRET` with a long random value. For example, generate one with:

   ```powershell
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```

   Local development uses SQLite automatically if `DATABASE_URL` is blank. `PORT` defaults to 5000.

5. Apply the schema and optionally create an administrator:

   ```powershell
   flask db upgrade
   python seed.py
   ```

   Set `ADMIN_EMAIL` and `ADMIN_PASSWORD` in `.env` to seed the administrator (password must be at least 12 characters). If those values are blank, the seed command safely does nothing. The admin account is an owner in its own business workspace.

6. Run the server:

   ```powershell
   flask run
   ```

   Browse to <http://127.0.0.1:5000>. Register a business from the sign-in screen or sign in with the seeded admin credentials.

## Supabase PostgreSQL

In Supabase, open **Project Settings → Database → Connection string** and copy the PostgreSQL URI (use the pooler/transaction connection for serverless hosting where appropriate). Set it as `DATABASE_URL` in `.env`, including the database password. Keep `SUPABASE_SERVICE_ROLE_KEY` private and never put either Supabase key in frontend code. The Flask app connects through SQLAlchemy/PostgreSQL; `SUPABASE_URL` and `SUPABASE_ANON_KEY` are available as server-side app configuration. The service-role key remains in the environment and is not loaded into Flask/Jinja config; current SQLAlchemy persistence does not require Supabase REST keys.

Before deploying:

- Set `APP_ENV=production`, `COOKIE_SECURE=true`, a strong `JWT_SECRET`, and `DATABASE_URL`.
- Configure a persistent `RATELIMIT_STORAGE_URI` (for example Redis) for multi-worker production. `memory://` is intended for local development only.
- Terminate HTTPS at the hosting proxy and configure proxy handling appropriately for that host.
- Use a dedicated PostgreSQL role with only the privileges the app needs. Never expose the service-role key to a browser.

Production startup refuses the development secret, SQLite, or insecure session cookies. Supabase environment values must be configured in the deployment secret store, not committed.

## Features

- **Authentication and tenancy:** business registration, bcrypt password hashes, session login, login rate limiting, CSRF protection, owner/manager/cashier roles, and business-scoped queries.
- **Inventory:** product search, categories, cost and selling prices, stock adjustments with a movement ledger, low-stock indicators, CSV import/export, and archive instead of destructive deletion.
- **POS:** sale cart, discount, cash/transfer/card split payment, customer credit, receipt number and printable receipt. Each checkout has an idempotency key; stock updates and sale records are committed together.
- **Customers:** customer accounts, credit-sale history, outstanding balance, and repayments.
- **Expenses and reporting:** daily expense entry, date-range sales/profit reports, payment totals, best sellers, stock valuation at cost, and CSV export.
- **Staff and business settings:** edit business details, add manager/cashier users, and activate/deactivate accounts.

All amounts are stored as `Numeric(10,2)`. Sale line items retain product name, sell price, and cost snapshots so historical margins do not change when product prices are edited later.

## Database changes

After modifying models, create and review a migration:

```powershell
flask db migrate -m "describe the change"
flask db upgrade
```

The initial migration creates the current SQLAlchemy metadata. Review every future generated migration before applying it to production.
