"""
analytics.py
Pandas-based analytics for the Personal Expense Tracker: monthly reports,
category breakdowns, spending trends, budget-vs-actual, and plain-English
insights (e.g. "Your food spending increased 23% compared to last month.").
"""

import pandas as pd


def transactions_to_df(transactions: list) -> pd.DataFrame:
    """Convert a list of transaction dicts into a typed DataFrame."""
    if not transactions:
        return pd.DataFrame(
            columns=["id", "date", "type", "amount", "currency", "description", "category", "category_id"]
        )
    df = pd.DataFrame(transactions)
    df["date"] = pd.to_datetime(df["date"])
    df["month"] = df["date"].dt.to_period("M").astype(str)
    return df


def monthly_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Total income, expense, and net savings per month."""
    if df.empty:
        return pd.DataFrame(columns=["month", "income", "expense", "net"])
    pivot = df.pivot_table(index="month", columns="type", values="amount", aggfunc="sum", fill_value=0)
    for col in ("income", "expense"):
        if col not in pivot.columns:
            pivot[col] = 0
    pivot["net"] = pivot["income"] - pivot["expense"]
    return pivot.reset_index().sort_values("month")


def category_breakdown(df: pd.DataFrame, type_: str = "expense", month: str = None) -> pd.DataFrame:
    """Sum of amounts per category, optionally filtered to a single month."""
    filtered = df[df["type"] == type_]
    if month:
        filtered = filtered[filtered["month"] == month]
    if filtered.empty:
        return pd.DataFrame(columns=["category", "amount"])
    result = filtered.groupby("category", as_index=False)["amount"].sum()
    return result.sort_values("amount", ascending=False)


def spending_trend(df: pd.DataFrame, category: str = None) -> pd.DataFrame:
    """Monthly expense totals over time, optionally for one category."""
    expenses = df[df["type"] == "expense"]
    if category:
        expenses = expenses[expenses["category"] == category]
    if expenses.empty:
        return pd.DataFrame(columns=["month", "amount"])
    trend = expenses.groupby("month", as_index=False)["amount"].sum()
    return trend.sort_values("month")


def month_over_month_change(df: pd.DataFrame, category: str = None):
    """
    Returns (current_month, previous_month, current_total, previous_total, pct_change)
    for expenses, optionally scoped to a category. pct_change is None if there's
    no previous month to compare against.
    """
    trend = spending_trend(df, category=category)
    if len(trend) < 2:
        return None
    current = trend.iloc[-1]
    previous = trend.iloc[-2]
    if previous["amount"] == 0:
        pct_change = None
    else:
        pct_change = ((current["amount"] - previous["amount"]) / previous["amount"]) * 100
    return {
        "current_month": current["month"],
        "previous_month": previous["month"],
        "current_total": current["amount"],
        "previous_total": previous["amount"],
        "pct_change": pct_change,
    }


def generate_insights(df: pd.DataFrame, top_n: int = 3) -> list:
    """
    Produce plain-English insight strings, e.g.:
    'Your Food spending increased 23.4% compared to last month.'
    Ranks categories by absolute month-over-month change and returns the top N.
    """
    expenses = df[df["type"] == "expense"]
    if expenses.empty:
        return []

    months = sorted(expenses["month"].unique())
    if len(months) < 2:
        return ["Add another month of data to start seeing spending trend insights."]

    current_month, previous_month = months[-1], months[-2]
    cur = expenses[expenses["month"] == current_month].groupby("category")["amount"].sum()
    prev = expenses[expenses["month"] == previous_month].groupby("category")["amount"].sum()

    changes = []
    for category in set(cur.index) | set(prev.index):
        cur_amt = cur.get(category, 0)
        prev_amt = prev.get(category, 0)
        if prev_amt == 0:
            continue
        pct = ((cur_amt - prev_amt) / prev_amt) * 100
        changes.append((category, pct, cur_amt, prev_amt))

    changes.sort(key=lambda x: abs(x[1]), reverse=True)

    insights = []
    for category, pct, cur_amt, prev_amt in changes[:top_n]:
        direction = "increased" if pct > 0 else "decreased"
        insights.append(
            f"Your {category} spending {direction} {abs(pct):.1f}% compared to last month "
            f"(${cur_amt:,.2f} vs ${prev_amt:,.2f})."
        )
    return insights


def budget_status(df: pd.DataFrame, budgets: list, month: str) -> pd.DataFrame:
    """
    Compare actual spending vs budget limits for a given month.
    budgets: list of dicts with keys category, limit_amount.
    Returns a DataFrame with spent, limit, remaining, pct_used, over_budget.
    """
    if not budgets:
        return pd.DataFrame(
            columns=["category", "spent", "limit_amount", "remaining", "pct_used", "over_budget"]
        )

    budget_df = pd.DataFrame(budgets)[["category", "limit_amount"]]
    actual = category_breakdown(df, type_="expense", month=month)
    merged = budget_df.merge(actual, on="category", how="left").fillna({"amount": 0})
    merged.rename(columns={"amount": "spent"}, inplace=True)
    merged["remaining"] = merged["limit_amount"] - merged["spent"]
    merged["pct_used"] = (merged["spent"] / merged["limit_amount"] * 100).round(1)
    merged["over_budget"] = merged["spent"] > merged["limit_amount"]
    return merged.sort_values("pct_used", ascending=False)
