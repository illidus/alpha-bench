"""Streamlit dashboard for alpha-bench.

Multi-page interactive dashboard for visualizing benchmark results,
model performance, and trading decisions.

Usage:
    streamlit run alpha_bench/dashboard/app.py
"""

import logging
import sys
from pathlib import Path

import streamlit as st

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from alpha_bench.config import Config
from alpha_bench.dashboard.queries import DashboardQueries

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(
    page_title="alpha-bench Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown(
    """
    <style>
    .main > div {
        padding-top: 2rem;
    }
    .stMetric {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def main():
    """Main dashboard application."""

    # Initialize config and queries
    try:
        config = Config.load()
        queries = DashboardQueries(config)
    except Exception as e:
        st.error(f"Failed to load configuration: {e}")
        return

    # Sidebar
    st.sidebar.title("📊 alpha-bench")
    st.sidebar.markdown("---")

    # Page selection
    page = st.sidebar.radio(
        "Navigation",
        [
            "🏠 Overview",
            "📈 Model Performance",
            "📊 Leaderboard",
            "💼 Trading History",
            "⚙️ System Status",
        ],
    )

    st.sidebar.markdown("---")
    st.sidebar.info(
        "**alpha-bench** is an automated LLM trading evaluation framework. "
        "This dashboard visualizes benchmark results across models and time."
    )

    # Route to appropriate page
    if page == "🏠 Overview":
        show_overview(queries)
    elif page == "📈 Model Performance":
        show_model_performance(queries)
    elif page == "📊 Leaderboard":
        show_leaderboard(queries)
    elif page == "💼 Trading History":
        show_trading_history(queries)
    elif page == "⚙️ System Status":
        show_system_status(queries, config)


def show_overview(queries: DashboardQueries):
    """Show overview page with key metrics."""

    st.title("📊 Alpha-Bench Overview")

    # Load benchmarks data
    benchmarks = queries.get_all_benchmarks()

    if benchmarks.empty:
        st.warning(
            "No benchmark data available yet. Run a benchmark to see results here."
        )
        st.code(
            "python scripts/run_benchmark.py --model claude-code-numeric --lookback 72h"
        )
        return

    # Key metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Total Runs",
            len(benchmarks),
            help="Total number of benchmark runs across all models",
        )

    with col2:
        avg_return = benchmarks["total_return_pct"].mean()
        st.metric(
            "Avg Return",
            f"{avg_return:.2f}%",
            help="Average return across all benchmark runs",
        )

    with col3:
        avg_sharpe = benchmarks["sharpe_ratio"].mean()
        st.metric(
            "Avg Sharpe",
            f"{avg_sharpe:.2f}",
            help="Average Sharpe ratio across all benchmark runs",
        )

    with col4:
        num_models = benchmarks["model_id"].nunique()
        st.metric(
            "Active Models",
            num_models,
            help="Number of unique models evaluated",
        )

    st.markdown("---")

    # Recent runs table
    st.subheader("Recent Benchmark Runs")

    recent = benchmarks.sort_values("timestamp", ascending=False).head(10)
    display_cols = [
        "timestamp",
        "model_id",
        "total_return_pct",
        "sharpe_ratio",
        "max_drawdown",
        "num_trades",
    ]

    st.dataframe(
        recent[display_cols].style.format(
            {
                "total_return_pct": "{:.2f}%",
                "sharpe_ratio": "{:.2f}",
                "max_drawdown": "{:.2%}",
            }
        ),
        use_container_width=True,
    )

    # Performance over time chart
    st.subheader("Returns Over Time")

    import plotly.express as px

    fig = px.line(
        benchmarks.sort_values("timestamp"),
        x="timestamp",
        y="total_return_pct",
        color="model_id",
        title="Model Returns Over Time",
        labels={"total_return_pct": "Return (%)", "timestamp": "Date"},
    )
    st.plotly_chart(fig, use_container_width=True)


def show_model_performance(queries: DashboardQueries):
    """Show detailed model performance page."""

    st.title("📈 Model Performance")

    benchmarks = queries.get_all_benchmarks()

    if benchmarks.empty:
        st.warning("No benchmark data available.")
        return

    # Model selector
    models = sorted(benchmarks["model_id"].unique())
    selected_model = st.selectbox("Select Model", models)

    if not selected_model:
        return

    # Get model summary
    model_data = benchmarks[benchmarks["model_id"] == selected_model]

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Runs", len(model_data))

    with col2:
        avg_return = model_data["total_return_pct"].mean()
        std_return = model_data["total_return_pct"].std()
        st.metric("Avg Return", f"{avg_return:.2f}%", f"±{std_return:.2f}%")

    with col3:
        avg_sharpe = model_data["sharpe_ratio"].mean()
        st.metric("Avg Sharpe", f"{avg_sharpe:.2f}")

    with col4:
        win_rate = (model_data["total_return"] > 0).sum() / len(model_data)
        st.metric("Win Rate", f"{win_rate:.1%}")

    st.markdown("---")

    # Performance metrics over time
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Returns Distribution")
        import plotly.express as px

        fig = px.histogram(
            model_data,
            x="total_return_pct",
            nbins=20,
            title="Distribution of Returns",
            labels={"total_return_pct": "Return (%)"},
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Sharpe Ratio Over Time")
        fig = px.line(
            model_data.sort_values("timestamp"),
            x="timestamp",
            y="sharpe_ratio",
            title="Sharpe Ratio Trend",
            labels={"sharpe_ratio": "Sharpe Ratio"},
        )
        st.plotly_chart(fig, use_container_width=True)

    # Detailed statistics
    st.subheader("Detailed Statistics")

    stats = model_data[
        [
            "total_return_pct",
            "sharpe_ratio",
            "sortino_ratio",
            "max_drawdown",
            "num_trades",
        ]
    ].describe()

    st.dataframe(
        stats.style.format("{:.2f}"),
        use_container_width=True,
    )


def show_leaderboard(queries: DashboardQueries):
    """Show leaderboard page."""

    st.title("🏆 Model Leaderboard")

    benchmarks = queries.get_all_benchmarks()

    if benchmarks.empty:
        st.warning("No benchmark data available.")
        return

    # Metric selector
    metric = st.selectbox(
        "Rank By",
        ["sharpe_ratio", "total_return_pct", "sortino_ratio", "win_rate"],
        format_func=lambda x: x.replace("_", " ").title(),
    )

    # Calculate win rate if selected
    if metric == "win_rate":
        model_stats = benchmarks.groupby("model_id").agg(
            {
                "total_return": lambda x: (x > 0).sum() / len(x),
                "run_id": "count",
            }
        )
        model_stats.columns = ["win_rate", "num_runs"]
        model_stats = model_stats.sort_values("win_rate", ascending=False)
        metric_col = "win_rate"
    else:
        model_stats = benchmarks.groupby("model_id")[metric].agg(["mean", "std", "count"])
        model_stats = model_stats.sort_values("mean", ascending=False)
        metric_col = "mean"

    # Display leaderboard
    st.subheader(f"Top Models by {metric.replace('_', ' ').title()}")

    for rank, (model_id, row) in enumerate(model_stats.iterrows(), 1):
        with st.container():
            col1, col2, col3 = st.columns([1, 4, 2])

            with col1:
                if rank == 1:
                    st.markdown("🥇")
                elif rank == 2:
                    st.markdown("🥈")
                elif rank == 3:
                    st.markdown("🥉")
                else:
                    st.markdown(f"**#{rank}**")

            with col2:
                st.markdown(f"**{model_id}**")

            with col3:
                if metric == "win_rate":
                    st.metric("Win Rate", f"{row[metric_col]:.1%}")
                else:
                    st.metric(
                        metric.replace("_", " ").title(),
                        f"{row[metric_col]:.2f}",
                        f"±{row['std']:.2f}" if "std" in row else "",
                    )

            st.markdown("---")


def show_trading_history(queries: DashboardQueries):
    """Show trading history page."""

    st.title("💼 Trading History")

    st.info("Trading history details coming soon. This will show individual trades and decisions.")


def show_system_status(queries: DashboardQueries, config: Config):
    """Show system status page."""

    st.title("⚙️ System Status")

    # Configuration status
    st.subheader("Configuration")

    errors = config.validate()
    if errors:
        st.error("Configuration has errors:")
        for error in errors:
            st.write(f"- {error}")
    else:
        st.success("Configuration is valid")

    # Enabled models
    st.subheader("Enabled Models")

    models = config.get_models(enabled_only=True)
    for model in models:
        with st.expander(f"📋 {model.id}"):
            st.write(f"**Provider:** {model.provider}")
            st.write(f"**Description:** {model.description}")
            st.write(f"**Features:** {', '.join(model.features)}")
            st.write(f"**Risk Cap:** {model.risk_cap:.2%}")
            st.write(f"**Schedule:** {model.schedule}")

    # Cache status
    st.subheader("Cache Status")

    from alpha_bench.data.cache import DataCache

    cache = DataCache()
    stats = cache.get_stats()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Cached Files", stats["count"])
    with col2:
        st.metric("Cache Size", f"{stats['size_mb']:.2f} MB")
    with col3:
        st.metric("Expired Files", stats["expired_count"])


if __name__ == "__main__":
    main()
