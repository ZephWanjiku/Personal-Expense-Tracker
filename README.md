# Personal Expense Tracker

A full-stack Streamlit app for tracking income and expenses, visualizing spending
patterns, and setting budget alerts. Built to match the "Personal Expense Tracker"
project brief: Python + SQLite/PostgreSQL + Pandas + Plotly + Streamlit.

## Features

- **User accounts** — sign up, log in, and log out; every user's data (transactions,
  categories, budgets) is private to their account
- **Income & expense tracking** with categories and descriptions
- **Data validation** on every transaction (positive amounts, no future dates) and
  on signup (username rules, password strength)
- **Monthly reports** — income, expense, and net savings by month
- **Spending charts** — category pie chart, income vs. expense bar chart, spending trend line
- **Budget limits & alerts** — set a monthly limit per category and get warned at 80% and over-budget
- **Spending trend insights** — auto-generated sentences like *"Your Food spending
  increased 23.4% compared to last month."*
- **Full CRUD** — add, edit, and delete transactions and categories

## Tech Stack

| Layer         | Tool                  |
|---------------|-----------------------|
| Language      | Python                |
| Database      | SQLite (swap-in PostgreSQL notes below) |
| Data analysis | Pandas                |
| Charts        | Plotly                |
| UI            | Streamlit             |

## Project Structure

```
expense_tracker/
├── app.py              # Streamlit UI — login/signup gate + all pages (Add, Transactions, Dashboard, Budgets, Categories)
├── database.py         # SQLite schema (users, categories, transactions, budgets) + all CRUD, scoped per user
├── analytics.py        # Pandas-based reports, trends, budget status, insight generation
├── auth.py             # Password hashing (PBKDF2-HMAC-SHA256) + username/password validation
├── seed_demo_data.py   # Optional: creates a demo account and populates 3 months of sample data
└── requirements.txt
```

## Setup

```bash
cd expense_tracker
pip install -r requirements.txt

# optional: creates a demo account (username: demo, password: Demo1234)
# and loads a few months of sample data so charts aren't empty on first run
python seed_demo_data.py

streamlit run app.py
```

Then open the local URL Streamlit prints (usually `http://localhost:8501`), and
either log in with the demo account above or sign up for a new one.

## How it works

```
User → Add Transaction → Validate Data → Database
                                             ↓
                                         Analytics (Pandas)
                                             ↓
                                    Charts + Insights (Plotly / Streamlit)
```

- `database.py` owns the schema (`users`, `categories`, `transactions`, `budgets`)
  and every read/write operation. Every category, transaction, and budget carries
  a `user_id`, and every query is scoped to it — one user can never see another's
  data. Amounts are validated (`> 0`) at the DB layer as well as in the UI.
- `auth.py` hashes passwords with PBKDF2-HMAC-SHA256 (stdlib only, no extra
  dependency) and validates usernames/passwords before an account is created.
- `analytics.py` turns raw transaction rows into a Pandas DataFrame and derives
  monthly summaries, category breakdowns, month-over-month trend data, and the
  plain-English insight strings used on the Dashboard.
- `app.py` starts with a login/signup gate (`st.session_state.user`), then shows
  five pages (Add Transaction, Transactions, Dashboard, Budgets, Categories) that
  call into `database.py` and `analytics.py`, always passing the current user's id.

## Switching to PostgreSQL

`database.py` is intentionally isolated so the storage layer can be swapped without
touching `analytics.py` or `app.py`. Replace `sqlite3.connect(...)` in
`get_connection()` with a `psycopg2.connect(...)` call using your connection string,
and change `AUTOINCREMENT` → `SERIAL` and `?` placeholders → `%s` in the SQL. Row
access via `dict(row)` works the same with `psycopg2.extras.RealDictCursor`.

## What you'll learn / practice by extending this

- CRUD design and SQL schema modeling
- Data analysis and aggregation with Pandas
- Data visualization with Plotly
- User input validation
- Dashboard / small full-stack app development

## Ideas for extending it further

- Recurring transactions (subscriptions, rent)
- CSV import/export
- Currency conversion for multi-currency tracking
- Email/SMS budget alerts instead of in-app only
- Password reset flow, "remember me" sessions, or OAuth login
