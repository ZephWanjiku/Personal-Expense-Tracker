"""
app.py
Personal Expense Tracker — Streamlit dashboard with multi-user accounts.

Run with:
    streamlit run app.py
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date, datetime

import database as db
import analytics as an
import auth

st.set_page_config(page_title="Personal Expense Tracker", page_icon="💰", layout="wide")

db.init_db()

if "user" not in st.session_state:
    st.session_state.user = None


# ---------------------------------------------------------------------------
# Login / Signup gate
# ---------------------------------------------------------------------------
def login_signup_screen():
    st.title("💰 Personal Expense Tracker")
    st.caption("Sign in or create an account to start tracking your income and expenses.")

    login_tab, signup_tab = st.tabs(["Log In", "Sign Up"])

    with login_tab:
        with st.form("login_form"):
            username = st.text_input("Username", key="login_username")
            password = st.text_input("Password", type="password", key="login_password")
            submitted = st.form_submit_button("Log In", use_container_width=True)

            if submitted:
                if not username or not password:
                    st.error("Enter both a username and password.")
                else:
                    user = db.authenticate_user(username, password)
                    if user:
                        st.session_state.user = {"id": user["id"], "username": user["username"]}
                        st.rerun()
                    else:
                        st.error("Invalid username or password.")

    with signup_tab:
        with st.form("signup_form"):
            new_username = st.text_input("Choose a username", key="signup_username")
            new_password = st.text_input("Choose a password", type="password", key="signup_password")
            confirm_password = st.text_input("Confirm password", type="password", key="signup_confirm")
            submitted = st.form_submit_button("Create Account", use_container_width=True)

            if submitted:
                username_error = auth.validate_username(new_username)
                password_error = auth.validate_password(new_password)

                if username_error:
                    st.error(username_error)
                elif password_error:
                    st.error(password_error)
                elif new_password != confirm_password:
                    st.error("Passwords do not match.")
                else:
                    try:
                        user_id = db.create_user(new_username, new_password)
                        st.session_state.user = {"id": user_id, "username": new_username.strip()}
                        st.success("Account created! Redirecting…")
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))


if st.session_state.user is None:
    login_signup_screen()
    st.stop()

# ---------------------------------------------------------------------------
# Authenticated app
# ---------------------------------------------------------------------------
user_id = st.session_state.user["id"]
username = st.session_state.user["username"]

st.sidebar.title("💰 Expense Tracker")
st.sidebar.caption(f"Logged in as **{username}**")
if st.sidebar.button("Log Out", use_container_width=True):
    st.session_state.user = None
    st.rerun()

st.sidebar.markdown("---")
page = st.sidebar.radio(
    "Navigate",
    ["Add Transaction", "Transactions", "Dashboard", "Budgets", "Categories"],
)

st.sidebar.markdown("---")
st.sidebar.caption("Built with Streamlit · SQLite · Pandas · Plotly")


def load_df():
    return an.transactions_to_df(db.get_transactions(user_id))


# ---------------------------------------------------------------------------
# Page: Add Transaction
# ---------------------------------------------------------------------------
if page == "Add Transaction":
    st.title("➕ Add a Transaction")

    txn_type = st.radio("Type", ["expense", "income"], horizontal=True)
    categories = db.get_categories(user_id, type_=txn_type)

    if not categories:
        st.warning(f"No {txn_type} categories yet. Add one on the Categories page first.")
    else:
        with st.form("add_transaction_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                txn_date = st.date_input("Date", value=date.today())
                amount = st.number_input("Amount", min_value=0.0, step=1.0, format="%.2f")
            with col2:
                category_name = st.selectbox("Category", [c["name"] for c in categories])
                currency = st.selectbox("Currency", ["USD", "KES"], format_func=lambda value: {
                    "USD": "US Dollar (USD)",
                    "KES": "Kenyan Shilling (KES)",
                }[value])
                description = st.text_input("Description (optional)")

            submitted = st.form_submit_button("Add Transaction", use_container_width=True)

            if submitted:
                # --- Validate Data ---
                errors = []
                if amount is None or amount <= 0:
                    errors.append("Amount must be greater than zero.")
                if txn_date > date.today():
                    errors.append("Date cannot be in the future.")

                if errors:
                    for e in errors:
                        st.error(e)
                else:
                    category_id = next(c["id"] for c in categories if c["name"] == category_name)
                    db.add_transaction(
                        user_id=user_id,
                        date_=txn_date.isoformat(),
                        type_=txn_type,
                        category_id=category_id,
                        amount=float(amount),
                        description=description,
                        currency=currency,
                    )
                    symbol = "$" if currency == "USD" else "KSh "
                    st.success(f"Added {txn_type}: {symbol}{amount:,.2f} in {category_name}")
                    st.rerun()

# ---------------------------------------------------------------------------
# Page: Transactions (view / edit / delete)
# ---------------------------------------------------------------------------
elif page == "Transactions":
    st.title("📋 Transactions")

    df = load_df()
    if df.empty:
        st.info("No transactions yet. Add one from the 'Add Transaction' page.")
    else:
        col1, col2, col3 = st.columns(3)
        with col1:
            type_filter = st.selectbox("Filter by type", ["All", "income", "expense"])
        with col2:
            month_options = ["All"] + sorted(df["month"].unique().tolist(), reverse=True)
            month_filter = st.selectbox("Filter by month", month_options)
        with col3:
            cat_options = ["All"] + sorted(df["category"].unique().tolist())
            cat_filter = st.selectbox("Filter by category", cat_options)

        view = df.copy()
        if type_filter != "All":
            view = view[view["type"] == type_filter]
        if month_filter != "All":
            view = view[view["month"] == month_filter]
        if cat_filter != "All":
            view = view[view["category"] == cat_filter]

        st.dataframe(
            view[["id", "date", "type", "category", "amount", "currency", "description"]]
            .assign(date=lambda d: d["date"].dt.strftime("%Y-%m-%d"))
            .rename(columns={"id": "ID", "date": "Date", "type": "Type",
                              "category": "Category", "amount": "Amount", "currency": "Currency",
                              "description": "Description"}),
            use_container_width=True,
            hide_index=True,
        )

        st.markdown("---")
        st.subheader("Edit or Delete a Transaction")
        txn_id = st.number_input("Transaction ID", min_value=0, step=1)

        if txn_id > 0:
            match = df[df["id"] == txn_id]
            if match.empty:
                st.warning("No transaction with that ID.")
            else:
                row = match.iloc[0]
                categories = db.get_categories(user_id, type_=row["type"])
                cat_names = [c["name"] for c in categories]

                with st.form("edit_form"):
                    col1, col2 = st.columns(2)
                    with col1:
                        new_date = st.date_input("Date", value=row["date"].date())
                        new_amount = st.number_input("Amount", min_value=0.0, value=float(row["amount"]), format="%.2f")
                    with col2:
                        default_idx = cat_names.index(row["category"]) if row["category"] in cat_names else 0
                        new_category = st.selectbox("Category", cat_names, index=default_idx)
                        new_currency = st.selectbox(
                            "Currency", ["USD", "KES"],
                            index=0 if row.get("currency", "USD") == "USD" else 1,
                            format_func=lambda value: {
                                "USD": "US Dollar (USD)",
                                "KES": "Kenyan Shilling (KES)",
                            }[value],
                        )
                        new_desc = st.text_input("Description", value=row["description"] or "")

                    b1, b2 = st.columns(2)
                    update_clicked = b1.form_submit_button("Update", use_container_width=True)
                    delete_clicked = b2.form_submit_button("Delete", use_container_width=True)

                    if update_clicked:
                        if new_amount <= 0:
                            st.error("Amount must be greater than zero.")
                        else:
                            category_id = next(c["id"] for c in categories if c["name"] == new_category)
                            db.update_transaction(
                                user_id, int(txn_id), new_date.isoformat(), row["type"], category_id,
                                float(new_amount), new_desc, new_currency,
                            )
                            st.success("Transaction updated.")
                            st.rerun()

                    if delete_clicked:
                        db.delete_transaction(user_id, int(txn_id))
                        st.success("Transaction deleted.")
                        st.rerun()

# ---------------------------------------------------------------------------
# Page: Dashboard (charts + insights)
# ---------------------------------------------------------------------------
elif page == "Dashboard":
    st.title("📊 Dashboard")

    df = load_df()
    if df.empty:
        st.info("Add some transactions to see your dashboard.")
    else:
        summary = an.monthly_summary(df)
        latest = summary.iloc[-1]

        c1, c2, c3 = st.columns(3)
        c1.metric("This Month Income", f"${latest['income']:,.2f}")
        c2.metric("This Month Expense", f"${latest['expense']:,.2f}")
        c3.metric("This Month Net", f"${latest['net']:,.2f}")

        st.markdown("### 🔎 Insights")
        for insight in an.generate_insights(df):
            st.info(insight)

        st.markdown("---")
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Spending by Category")
            latest_month = df["month"].max()
            pie_data = an.category_breakdown(df, type_="expense", month=latest_month)
            if not pie_data.empty:
                fig = px.pie(pie_data, names="category", values="amount", hole=0.4)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.caption("No expenses recorded for the latest month.")

        with col2:
            st.subheader("Income vs Expense by Month")
            fig2 = px.bar(
                summary, x="month", y=["income", "expense"], barmode="group",
                labels={"value": "Amount", "month": "Month", "variable": "Type"},
            )
            st.plotly_chart(fig2, use_container_width=True)

        st.subheader("Spending Trend Over Time")
        trend = an.spending_trend(df)
        fig3 = px.line(trend, x="month", y="amount", markers=True, labels={"amount": "Total Expense"})
        st.plotly_chart(fig3, use_container_width=True)

# ---------------------------------------------------------------------------
# Page: Budgets
# ---------------------------------------------------------------------------
elif page == "Budgets":
    st.title("🎯 Budgets")

    df = load_df()
    current_month = datetime.today().strftime("%Y-%m")
    months_available = sorted(set(df["month"].tolist()) | {current_month}, reverse=True) if not df.empty else [current_month]
    selected_month = st.selectbox("Month", months_available, index=0)

    st.subheader("Set a Budget Limit")
    expense_categories = db.get_categories(user_id, type_="expense")
    with st.form("budget_form"):
        col1, col2 = st.columns(2)
        with col1:
            cat_name = st.selectbox("Category", [c["name"] for c in expense_categories])
        with col2:
            limit = st.number_input("Monthly limit", min_value=0.0, step=10.0, format="%.2f")
        submitted = st.form_submit_button("Save Budget")

        if submitted:
            if limit <= 0:
                st.error("Budget limit must be greater than zero.")
            else:
                category_id = next(c["id"] for c in expense_categories if c["name"] == cat_name)
                db.set_budget(user_id, category_id, selected_month, float(limit))
                st.success(f"Budget for {cat_name} in {selected_month} set to ${limit:,.2f}")
                st.rerun()

    st.markdown("---")
    st.subheader(f"Budget Status — {selected_month}")
    budgets = db.get_budgets(user_id, month=selected_month)

    if not budgets:
        st.info("No budgets set for this month yet.")
    else:
        status = an.budget_status(df, budgets, selected_month)
        for _, row in status.iterrows():
            pct = min(row["pct_used"], 100)
            label = f"{row['category']}: ${row['spent']:,.2f} / ${row['limit_amount']:,.2f} ({row['pct_used']:.0f}%)"
            st.progress(int(pct) / 100 if pct <= 100 else 1.0, text=label)
            if row["over_budget"]:
                st.error(f"⚠️ Budget alert: {row['category']} is over budget by ${row['spent'] - row['limit_amount']:,.2f}!")
            elif row["pct_used"] >= 80:
                st.warning(f"⚠️ {row['category']} is at {row['pct_used']:.0f}% of its budget.")

# ---------------------------------------------------------------------------
# Page: Categories
# ---------------------------------------------------------------------------
elif page == "Categories":
    st.title("🏷️ Categories")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Income Categories")
        for c in db.get_categories(user_id, type_="income"):
            st.write(f"• {c['name']}")
    with col2:
        st.subheader("Expense Categories")
        for c in db.get_categories(user_id, type_="expense"):
            st.write(f"• {c['name']}")

    st.markdown("---")
    st.subheader("Add a New Category")
    with st.form("add_category_form", clear_on_submit=True):
        name = st.text_input("Category name")
        type_ = st.radio("Type", ["expense", "income"], horizontal=True)
        submitted = st.form_submit_button("Add Category")

        if submitted:
            if not name.strip():
                st.error("Category name cannot be empty.")
            else:
                try:
                    db.add_category(user_id, name, type_)
                    st.success(f"Added category: {name}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Could not add category: {e}")
