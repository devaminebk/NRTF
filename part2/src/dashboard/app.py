"""app.py — Streamlit dashboard for the Re·Tech Fusion energy pipeline.

Run from the project root:
    streamlit run src/dashboard/app.py
"""
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ---------------------------------------------------------------------------
# Path setup so we can import from src.* whether run via streamlit run or python
# ---------------------------------------------------------------------------
import sys
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.utils.config import PROCESSED_DATA_DIR  # noqa: E402

# ---------------------------------------------------------------------------
# Page config + custom theme
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Re·Tech Fusion — Energy Pipeline",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Industrial / technical aesthetic — dark canvas, neon accents.
# Green = OK / energy, amber = gas, red = anomalies, cyan = info.
CSS = """
<style>
:root {
    --bg-deep:   #0a0e14;
    --bg-panel:  #11161f;
    --bg-card:   #161c27;
    --border:    #1f2a3a;
    --text:      #e6edf3;
    --text-dim:  #7d8a9c;
    --accent-1:  #00d4aa;   /* electric green   */
    --accent-2:  #ffb000;   /* amber (gas)      */
    --accent-3:  #ff4757;   /* red (anomaly)    */
    --accent-4:  #00b8d4;   /* cyan (info)      */
}
.stApp {
    background: radial-gradient(1200px 600px at 10% -10%, #0e1622 0%, var(--bg-deep) 60%) fixed;
    color: var(--text);
}
header[data-testid="stHeader"] { background: transparent; }
.block-container { padding-top: 2rem; padding-bottom: 4rem; max-width: 1400px; }

/* Hero title */
h1.retech-title {
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    font-weight: 700;
    font-size: 2.4rem;
    letter-spacing: -0.02em;
    color: var(--text);
    margin: 0 0 .25rem 0;
}
h1.retech-title .accent { color: var(--accent-1); }
.retech-sub {
    color: var(--text-dim);
    font-family: 'JetBrains Mono', monospace;
    font-size: .85rem;
    letter-spacing: .12em;
    text-transform: uppercase;
    margin-bottom: 2rem;
}

/* KPI cards */
.kpi-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; margin-bottom: 2rem; }
.kpi-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 1.4rem 1.2rem;
    position: relative;
    overflow: hidden;
}
.kpi-card::before {
    content: '';
    position: absolute; top: 0; left: 0; right: 0; height: 2px;
    background: var(--accent-1);
}
.kpi-card.gas::before { background: var(--accent-2); }
.kpi-card.co2::before { background: var(--accent-3); }
.kpi-card.anomaly::before { background: var(--accent-3); }
.kpi-card.points::before { background: var(--accent-4); }
.kpi-label {
    color: var(--text-dim);
    font-family: 'JetBrains Mono', monospace;
    font-size: .72rem;
    letter-spacing: .15em;
    text-transform: uppercase;
    margin-bottom: .6rem;
}
.kpi-value {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.9rem;
    font-weight: 700;
    color: var(--text);
    line-height: 1.1;
}
.kpi-unit {
    color: var(--text-dim);
    font-family: 'JetBrains Mono', monospace;
    font-size: .85rem;
    margin-left: .35rem;
}

/* Section headers */
h2.section {
    font-family: 'JetBrains Mono', monospace;
    font-size: .9rem;
    letter-spacing: .15em;
    text-transform: uppercase;
    color: var(--text-dim);
    border-left: 3px solid var(--accent-1);
    padding-left: .8rem;
    margin: 2.5rem 0 1rem 0;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background: var(--bg-panel);
    border-right: 1px solid var(--border);
}
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 {
    font-family: 'JetBrains Mono', monospace;
    color: var(--accent-1);
    font-size: .85rem;
    letter-spacing: .15em;
    text-transform: uppercase;
}

/* Streamlit dataframes */
[data-testid="stDataFrame"] {
    border: 1px solid var(--border);
    border-radius: 8px;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] { gap: 4px; }
.stTabs [data-baseweb="tab"] {
    background: var(--bg-card);
    color: var(--text-dim);
    border: 1px solid var(--border);
    border-radius: 6px 6px 0 0;
    font-family: 'JetBrains Mono', monospace;
    font-size: .8rem;
    letter-spacing: .1em;
    text-transform: uppercase;
}
.stTabs [aria-selected="true"] { color: var(--accent-1); border-bottom-color: var(--accent-1); }

/* Footer */
.retech-footer {
    margin-top: 4rem;
    padding-top: 1rem;
    border-top: 1px solid var(--border);
    color: var(--text-dim);
    font-family: 'JetBrains Mono', monospace;
    font-size: .7rem;
    letter-spacing: .12em;
    text-transform: uppercase;
    text-align: center;
}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# Plotly theme to match
PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="JetBrains Mono, monospace", color="#e6edf3", size=12),
    xaxis=dict(gridcolor="#1f2a3a", linecolor="#1f2a3a", zerolinecolor="#1f2a3a"),
    yaxis=dict(gridcolor="#1f2a3a", linecolor="#1f2a3a", zerolinecolor="#1f2a3a"),
    margin=dict(l=10, r=10, t=40, b=10),
    legend=dict(font=dict(size=11), bgcolor="rgba(0,0,0,0)"),
)

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_data() -> pd.DataFrame:
    path = Path(PROCESSED_DATA_DIR) / "energy_consolidated.csv"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path, parse_dates=["timestamp"], low_memory=False)
    return df


# ---------------------------------------------------------------------------
# File processing
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# File processing
# ---------------------------------------------------------------------------
def process_uploaded_files(excel_files, pdf_files, image_files):
    """Process uploaded files and add them to the dataset."""
    import tempfile
    import shutil
    import time
    import os
    from pathlib import Path

    # Create progress bar
    progress_bar = st.progress(0)
    status_text = st.empty()

    total_files = len(excel_files or []) + len(pdf_files or []) + len(image_files or [])
    processed = 0

    # Create persistent temp directory (don't use context manager to avoid premature cleanup)
    temp_dir = tempfile.mkdtemp(prefix="retech_upload_")
    temp_path = Path(temp_dir)

    try:
        # Save uploaded files to temp directory with proper file handling
        all_files = []

        if excel_files:
            excel_dir = temp_path / "excel"
            excel_dir.mkdir(exist_ok=True)
            for file in excel_files:
                file_path = excel_dir / file.name
                try:
                    with open(file_path, "wb") as f:
                        f.write(file.getbuffer())
                        f.flush()  # Ensure data is written to disk
                        os.fsync(f.fileno())  # Force write to disk
                    # Verify file was written correctly
                    if file_path.stat().st_size > 0:
                        all_files.append(("excel", file_path))
                    else:
                        st.error(f"❌ Failed to write {file.name}: file is empty")
                except Exception as e:
                    st.error(f"❌ Failed to save {file.name}: {str(e)}")

        if pdf_files:
            pdf_dir = temp_path / "pdfs"
            pdf_dir.mkdir(exist_ok=True)
            for file in pdf_files:
                file_path = pdf_dir / file.name
                try:
                    with open(file_path, "wb") as f:
                        f.write(file.getbuffer())
                        f.flush()
                        os.fsync(f.fileno())
                    if file_path.stat().st_size > 0:
                        all_files.append(("pdf", file_path))
                    else:
                        st.error(f"❌ Failed to write {file.name}: file is empty")
                except Exception as e:
                    st.error(f"❌ Failed to save {file.name}: {str(e)}")

        if image_files:
            image_dir = temp_path / "images"
            image_dir.mkdir(exist_ok=True)
            for file in image_files:
                file_path = image_dir / file.name
                try:
                    with open(file_path, "wb") as f:
                        f.write(file.getbuffer())
                        f.flush()
                        os.fsync(f.fileno())
                    if file_path.stat().st_size > 0:
                        all_files.append(("image", file_path))
                    else:
                        st.error(f"❌ Failed to write {file.name}: file is empty")
                except Exception as e:
                    st.error(f"❌ Failed to save {file.name}: {str(e)}")

        # Small delay to ensure all files are fully written and accessible
        time.sleep(0.5)

        # Process files using the extraction pipeline
        dfs = []

        # Import extraction functions
        from src.extraction.extract_excel import extract_all_excels
        from src.extraction.extract_pdf import extract_all_pdfs
        from src.extraction.extract_image import extract_all_images

        # Process each file type
        for file_type, file_path in all_files:
            try:
                # Double-check file is accessible before processing
                if not file_path.exists():
                    st.error(f"❌ File no longer exists: {file_path.name}")
                    continue

                if not os.access(file_path, os.R_OK):
                    st.error(f"❌ Cannot read file: {file_path.name}")
                    continue

                status_text.text(f"Processing {file_type}: {file_path.name}")

                if file_type == "excel":
                    df = extract_all_excels(file_path.parent)
                elif file_type == "pdf":
                    df = extract_all_pdfs(file_path.parent)
                elif file_type == "image":
                    df = extract_all_images(file_path.parent)

                if not df.empty:
                    dfs.append(df)
                    st.success(f"✅ {file_path.name}: {len(df)} data points extracted")
                else:
                    st.warning(f"⚠️ {file_path.name}: No data extracted")

            except Exception as e:
                st.error(f"❌ Error processing {file_path.name}: {str(e)}")

            processed += 1
            progress_bar.progress(processed / total_files)

        # Combine all extracted data
        if dfs:
            new_data = pd.concat(dfs, ignore_index=True)

            # Load existing data
            existing_path = Path(PROCESSED_DATA_DIR) / "energy_consolidated.csv"
            if existing_path.exists():
                existing_data = pd.read_csv(existing_path, parse_dates=["timestamp"], low_memory=False)
                combined_data = pd.concat([existing_data, new_data], ignore_index=True)
            else:
                combined_data = new_data

            # Apply normalization and processing pipeline
            status_text.text("Applying data processing pipeline...")

            from src.normalization.normalize import normalize_to_kwh
            from src.emissions.co2 import add_co2_emissions, cumulative_to_delta

            combined_data = normalize_to_kwh(combined_data)
            combined_data = cumulative_to_delta(combined_data, group_cols=("source", "measure"))

            df_for_co2 = combined_data.copy()
            df_for_co2["value_kwh"] = df_for_co2["delta_kwh"]
            df_with_co2 = add_co2_emissions(df_for_co2)
            combined_data["co2_kg"] = df_with_co2["co2_kg"]
            combined_data["co2_source"] = df_with_co2["co2_source"]
            combined_data["co2_factor"] = df_with_co2["co2_factor"]

            # Anomaly detection
            try:
                from src.anomalies.detect import detect_anomalies
                combined_data = detect_anomalies(combined_data)
            except Exception as e:
                st.warning(f"Anomaly detection skipped: {e}")

            # Save updated dataset
            existing_path.parent.mkdir(parents=True, exist_ok=True)
            combined_data.to_csv(existing_path, index=False)

            st.success(f"🎉 Successfully added {len(new_data):,} new data points!")
            st.success(f"📊 Total dataset now contains {len(combined_data):,} data points")

            # Clear cache and rerun
            load_data.clear()
            st.rerun()

        else:
            st.error("No data could be extracted from the uploaded files.")

    except Exception as e:
        st.error(f"Processing failed: {str(e)}")

    finally:
        # Clean up temp directory
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception as e:
            st.warning(f"Warning: Could not clean up temporary files: {str(e)}")

        progress_bar.empty()
        status_text.empty()


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown(
    """
    <h1 class='retech-title'>Re·Tech <span class='accent'>Fusion</span></h1>
    <div class='retech-sub'>// Energy Data Pipeline · INSAT Hackathon</div>
    """,
    unsafe_allow_html=True,
)

df = load_data()

if df.empty:
    st.error(
        "No processed data available. Run the pipeline first:\n\n"
        "```bash\npython main.py\n```"
    )
    st.stop()

# ---------------------------------------------------------------------------
# Sidebar filters
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### Filters")

    sources = sorted(df["source"].dropna().unique())
    selected_sources = st.multiselect("Source files", sources, default=sources)

    quantity_types = sorted(df["quantity_type"].dropna().unique())
    selected_qt = st.multiselect("Measurement types", quantity_types, default=quantity_types)

    # Date range
    valid_ts = df["timestamp"].dropna()
    if not valid_ts.empty:
        min_d, max_d = valid_ts.min().date(), valid_ts.max().date()
        date_range = st.date_input("Date range", (min_d, max_d),
                                   min_value=min_d, max_value=max_d)
    else:
        date_range = None

    st.markdown("---")
    st.caption("CO₂ factors")
    st.caption(f"• Grid (Tunisia): 0.468 kg/kWh")
    st.caption(f"• Natural gas: 0.202 kg/kWh")
    st.caption(f"• Reactive: 0.000 kg/kWh")

# Apply filters
mask = (
    df["source"].isin(selected_sources)
    & df["quantity_type"].isin(selected_qt)
)
if date_range and len(date_range) == 2:
    start, end = date_range
    mask &= (df["timestamp"].dt.date >= start) & (df["timestamp"].dt.date <= end)
fdf = df[mask].copy()

if fdf.empty:
    st.warning("No data matches the current filters.")
    st.stop()

# ---------------------------------------------------------------------------
# KPI row
# ---------------------------------------------------------------------------
energy_rows = fdf[fdf["quantity_type"] == "energy"]
total_kwh = energy_rows["delta_kwh"].sum()
total_co2 = energy_rows["co2_kg"].sum()
gas_kwh = energy_rows.loc[energy_rows["co2_source"] == "natural_gas", "delta_kwh"].sum()
n_points = len(fdf)
n_anomalies = int(fdf.get("is_anomaly", pd.Series(dtype=bool)).fillna(False).sum())


def fmt_si(value: float, unit: str) -> tuple[str, str]:
    """Return (formatted_number, unit_label) — auto-pick k/M/G prefix."""
    if pd.isna(value):
        return ("—", unit)
    abs_v = abs(value)
    if abs_v >= 1e9:  return (f"{value/1e9:,.2f}", f"G{unit}")
    if abs_v >= 1e6:  return (f"{value/1e6:,.2f}", f"M{unit}")
    if abs_v >= 1e3:  return (f"{value/1e3:,.2f}", f"k{unit}")
    return (f"{value:,.0f}", unit)


kwh_v, kwh_u = fmt_si(total_kwh, "Wh")
co2_v, co2_u = fmt_si(total_co2, "g CO₂")
gas_v, gas_u = fmt_si(gas_kwh, "Wh")
ano_pct = (100 * n_anomalies / n_points) if n_points else 0

st.markdown(
    f"""
    <div class='kpi-grid'>
      <div class='kpi-card'>
        <div class='kpi-label'>Total Energy</div>
        <div class='kpi-value'>{kwh_v}<span class='kpi-unit'>{kwh_u}</span></div>
      </div>
      <div class='kpi-card gas'>
        <div class='kpi-label'>Natural Gas</div>
        <div class='kpi-value'>{gas_v}<span class='kpi-unit'>{gas_u}</span></div>
      </div>
      <div class='kpi-card co2'>
        <div class='kpi-label'>CO₂ Emissions</div>
        <div class='kpi-value'>{co2_v}<span class='kpi-unit'>{co2_u}</span></div>
      </div>
      <div class='kpi-card anomaly'>
        <div class='kpi-label'>Anomalies</div>
        <div class='kpi-value'>{n_anomalies:,}<span class='kpi-unit'>· {ano_pct:.1f}%</span></div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Tabs: Overview / Time series / Anomalies / By source / Raw data / Data Sources
# ---------------------------------------------------------------------------
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "Overview", "Time series", "Anomalies", "By source", "Raw data", "Data Sources"
])

with tab1:
    st.markdown("<h2 class='section'>Energy mix</h2>", unsafe_allow_html=True)

    col1, col2 = st.columns([2, 3])

    with col1:
        # Donut: kWh by source category
        mix = (
            energy_rows.groupby("co2_source")["delta_kwh"].sum().reset_index()
            .rename(columns={"co2_source": "Source", "delta_kwh": "Energy (kWh)"})
        )
        if not mix.empty and mix["Energy (kWh)"].sum() > 0:
            color_map = {
                "grid_electricity": "#00d4aa",
                "natural_gas": "#ffb000",
                "reactive": "#7d8a9c",
                "default": "#00b8d4",
            }
            fig = px.pie(
                mix, values="Energy (kWh)", names="Source", hole=0.6,
                color="Source", color_discrete_map=color_map,
            )
            fig.update_traces(textposition="outside", textinfo="percent+label")
            fig.update_layout(**PLOTLY_LAYOUT, showlegend=False, height=380)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No energy data in the selected range.")

    with col2:
        # Quantity-type breakdown bar
        qt_counts = (
            fdf.groupby("quantity_type").size().reset_index(name="count")
            .sort_values("count", ascending=True)
        )
        fig = px.bar(
            qt_counts, x="count", y="quantity_type", orientation="h",
            color_discrete_sequence=["#00d4aa"],
        )
        fig.update_layout(
            **PLOTLY_LAYOUT, height=380,
            xaxis_title="Data points", yaxis_title="",
        )
        st.plotly_chart(fig, use_container_width=True)


with tab2:
    st.markdown("<h2 class='section'>Consumption over time</h2>", unsafe_allow_html=True)

    energy_measures = sorted(energy_rows["measure"].dropna().unique())
    if not energy_measures:
        st.info("No energy measurements available.")
    else:
        chosen = st.selectbox("Measure", energy_measures, index=0)
        ts_df = (
            energy_rows[energy_rows["measure"] == chosen]
            .sort_values("timestamp")
        )
        if ts_df.empty:
            st.info("No data for this measure in the current filters.")
        else:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=ts_df["timestamp"], y=ts_df["value_kwh"],
                mode="lines", name="Cumulative index (kWh)",
                line=dict(color="#00d4aa", width=2),
            ))
            fig.add_trace(go.Scatter(
                x=ts_df["timestamp"], y=ts_df["delta_kwh"],
                mode="lines", name="Per-period delta (kWh)",
                line=dict(color="#ffb000", width=1.2, dash="dot"),
                yaxis="y2",
            ))
            # Highlight anomalies on the delta axis
            if "is_anomaly" in ts_df.columns:
                anom_df = ts_df[ts_df["is_anomaly"].fillna(False)]
                if not anom_df.empty:
                    fig.add_trace(go.Scatter(
                        x=anom_df["timestamp"], y=anom_df["delta_kwh"],
                        mode="markers", name="Anomalies",
                        marker=dict(color="#ff4757", size=10, symbol="x"),
                        yaxis="y2",
                        hovertext=anom_df["anomaly_reason"],
                    ))
            fig.update_layout(
                **{
                    **PLOTLY_LAYOUT,
                    "height": 480,
                    "yaxis": {**PLOTLY_LAYOUT["yaxis"], "title": "Cumulative (kWh)"},
                    "yaxis2": dict(
                        title="Delta (kWh)",
                        overlaying="y",
                        side="right",
                        showgrid=False,
                    ),
                    "hovermode": "x unified",
                },
            )
            st.plotly_chart(fig, use_container_width=True)


with tab3:
    st.markdown("<h2 class='section'>Detected anomalies</h2>", unsafe_allow_html=True)

    if "is_anomaly" not in fdf.columns:
        st.info("Anomaly detection results not available in the data. "
                "Re-run `python main.py` to regenerate the consolidated CSV.")
    else:
        ano_df = fdf[fdf["is_anomaly"].fillna(False)].copy()
        if ano_df.empty:
            st.success("✓ No anomalies detected with the current filters.")
        else:
            # Summary KPIs
            c1, c2, c3 = st.columns(3)
            c1.metric("Z-score outliers", int(ano_df["anomaly_zscore"].sum()))
            c2.metric("ML outliers (IsolationForest)", int(ano_df["anomaly_iforest"].sum()))
            c3.metric("Impossible jumps", int(ano_df["anomaly_jump"].sum()))

            st.markdown("##### Anomalies per measure")
            per_meas = (
                ano_df.groupby("measure")
                .size()
                .reset_index(name="count")
                .sort_values("count", ascending=False)
                .head(15)
            )
            fig = px.bar(
                per_meas, x="count", y="measure", orientation="h",
                color_discrete_sequence=["#ff4757"],
            )
            fig.update_layout(
                **{
                    **PLOTLY_LAYOUT,
                    "height": 420,
                    "xaxis_title": "Anomalies detected",
                    "yaxis_title": "",
                    "yaxis": {**PLOTLY_LAYOUT["yaxis"], "autorange": "reversed"},
                },
            )
            st.plotly_chart(fig, use_container_width=True)

            st.markdown("##### Anomaly details")
            show_cols = [
                "timestamp", "source", "measure", "value", "unit",
                "delta_kwh", "anomaly_reason",
            ]
            show_cols = [c for c in show_cols if c in ano_df.columns]
            st.dataframe(
                ano_df[show_cols].sort_values("timestamp"),
                use_container_width=True, hide_index=True,
            )


with tab4:
    st.markdown("<h2 class='section'>Per-file breakdown</h2>", unsafe_allow_html=True)

    summary = (
        fdf.groupby("source")
        .agg(
            data_points=("value", "size"),
            energy_rows=("quantity_type", lambda s: (s == "energy").sum()),
            total_kwh=("delta_kwh", "sum"),
            total_co2_kg=("co2_kg", "sum"),
            anomalies=("is_anomaly", lambda s: int(s.fillna(False).sum())) if "is_anomaly" in fdf.columns else ("value", "size"),
            first_ts=("timestamp", "min"),
            last_ts=("timestamp", "max"),
        )
        .round(1)
        .reset_index()
    )
    st.dataframe(summary, use_container_width=True, hide_index=True)


with tab5:
    st.markdown("<h2 class='section'>Filtered data</h2>", unsafe_allow_html=True)

    show_cols = [
        "source", "timestamp", "category", "measure",
        "value", "unit", "quantity_type", "value_kwh", "delta_kwh",
        "co2_source", "co2_kg", "is_anomaly", "anomaly_reason",
    ]
    show_cols = [c for c in show_cols if c in fdf.columns]
    st.dataframe(fdf[show_cols].head(2000), use_container_width=True, hide_index=True)
    st.caption(f"Showing first 2 000 of {len(fdf):,} rows.")

    csv = fdf.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download filtered data (CSV)", csv, "retech_fusion_filtered.csv", "text/csv"
    )

with tab6:
    st.markdown("<h2 class='section'>Add Data Sources</h2>", unsafe_allow_html=True)

    st.markdown("""
    Upload new data sources to expand your energy dataset. Supported formats:
    - **Excel files** (.xlsx, .xls): Structured energy reports
    - **PDF files** (.pdf): Scanned or digital utility bills
    - **Images** (.jpg, .jpeg, .png): Photos of utility documents
    """)

    # File upload sections
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("### 📊 Excel Files")
        excel_files = st.file_uploader(
            "Upload Excel files",
            type=["xlsx", "xls"],
            accept_multiple_files=True,
            key="excel_upload"
        )
        if excel_files:
            st.success(f"📎 {len(excel_files)} Excel file(s) ready to process")

    with col2:
        st.markdown("### 📄 PDF Files")
        pdf_files = st.file_uploader(
            "Upload PDF files",
            type=["pdf"],
            accept_multiple_files=True,
            key="pdf_upload"
        )
        if pdf_files:
            st.success(f"📎 {len(pdf_files)} PDF file(s) ready to process")

    with col3:
        st.markdown("### 📷 Images")
        image_files = st.file_uploader(
            "Upload images",
            type=["jpg", "jpeg", "png"],
            accept_multiple_files=True,
            key="image_upload"
        )
        if image_files:
            st.success(f"📎 {len(image_files)} image file(s) ready to process")

    # Process button
    total_files = len(excel_files or []) + len(pdf_files or []) + len(image_files or [])
    if total_files > 0:
        if st.button("🚀 Process & Add to Dataset", type="primary", use_container_width=True):
            process_uploaded_files(excel_files, pdf_files, image_files)

    # Current data sources summary
    st.markdown("---")
    st.markdown("<h2 class='section'>Current Data Sources</h2>", unsafe_allow_html=True)

    if not df.empty:
        source_summary = (
            df.groupby("source")
            .agg(
                data_points=("value", "size"),
                file_type=("source", lambda x: Path(x.iloc[0]).suffix if x.iloc[0] else "unknown"),
                first_date=("timestamp", "min"),
                last_date=("timestamp", "max"),
            )
            .reset_index()
            .sort_values("data_points", ascending=False)
        )

        # Add file type icons
        def get_file_icon(ext):
            icons = {
                ".xlsx": "📊",
                ".xls": "📊",
                ".pdf": "📄",
                ".jpg": "📷",
                ".jpeg": "📷",
                ".png": "📷",
            }
            return icons.get(ext.lower(), "📄")

        source_summary["icon"] = source_summary["file_type"].apply(get_file_icon)
        source_summary["display_name"] = source_summary["icon"] + " " + source_summary["source"]

        st.dataframe(
            source_summary[["display_name", "data_points", "first_date", "last_date"]],
            column_config={
                "display_name": st.column_config.TextColumn("Source", width="large"),
                "data_points": st.column_config.NumberColumn("Data Points", width="medium"),
                "first_date": st.column_config.DatetimeColumn("From", width="medium"),
                "last_date": st.column_config.DatetimeColumn("To", width="medium"),
            },
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No data sources loaded yet. Upload files above to get started!")

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.markdown(
    "<div class='retech-footer'>"
    "Re·Tech Fusion · INSAT Hackathon · "
    f"{len(df):,} points consolidated"
    "</div>",
    unsafe_allow_html=True,
)