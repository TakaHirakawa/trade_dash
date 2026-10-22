import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="PH Trade Explorer", page_icon="🚢", layout="wide")

@st.cache_data
def load():
    df = pd.read_parquet("trade_agg.parquet")
    labels = pd.read_parquet("headings.parquet")["HEADING LABEL"].to_dict()
    df["DATE"] = pd.to_datetime(dict(year=df.YEAR, month=df.MONTH, day=1))
    df["HEADING NAME"] = df["HEADING"].astype(str).map(labels).fillna("") 
    df["HEADING NAME"] = df["HEADING"].astype(str) + " · " + df["HEADING NAME"]
    return df

df = load()

# ---------- Sidebar ----------
st.sidebar.title("Filters")
ymin, ymax = int(df.YEAR.min()), int(df.YEAR.max())
years = st.sidebar.slider("Year range", ymin, ymax, (ymin, ymax))
chapters = st.sidebar.multiselect("Chapter", sorted(df.CHAPTER.unique()))
sub = df[df.CHAPTER.isin(chapters)] if chapters else df
headings = st.sidebar.multiselect("Commodity (heading)", sorted(sub["HEADING NAME"].unique()))
countries = st.sidebar.multiselect("Country", sorted(df.COUNTRY.unique()))
top_n = st.sidebar.slider("Top N in rankings", 5, 30, 15)

f = df[df.YEAR.between(*years)]
if chapters:  f = f[f.CHAPTER.isin(chapters)]
if headings:  f = f[f["HEADING NAME"].isin(headings)]
if countries: f = f[f.COUNTRY.isin(countries)]

st.title("Philippine Export Explorer")
st.caption("Slice exports by country, chapter and commodity")

if f.empty:
    st.warning("No data for these filters.")
    st.stop()

# ---------- KPIs ----------
total = f.VALUE.sum()
last_y = f.YEAR.max()
cur = f[f.YEAR == last_y].VALUE.sum()
prev = f[f.YEAR == last_y - 1].VALUE.sum()
yoy = (cur / prev - 1) * 100 if prev else None

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total value", f"{total:,.0f}")
c2.metric(f"{last_y} value", f"{cur:,.0f}", f"{yoy:+.1f}% YoY" if yoy is not None else None)
c3.metric("Destination countries", f.COUNTRY.nunique())
c4.metric("Commodity headings", f.HEADING.nunique())

tab1, tab2, tab3, tab4 = st.tabs(["Trend", "Countries", "Commodities", "Data"])

# ---------- Trend ----------
with tab1:
    split = st.radio("Break down by", ["None", "Chapter", "Country"], horizontal=True)
    if split == "None":
        ts = f.groupby("DATE", as_index=False).VALUE.sum()
        fig = px.line(ts, x="DATE", y="VALUE")
    else:
        col = split.upper()
        top = f.groupby(col, observed=True).VALUE.sum().nlargest(8).index
        ts = (f[f[col].isin(top)].groupby(["DATE", col], observed=True, as_index=False).VALUE.sum())
        fig = px.line(ts, x="DATE", y="VALUE", color=col)
    st.plotly_chart(fig, use_container_width=True)

    yr = f.groupby("YEAR", as_index=False).VALUE.sum()
    st.plotly_chart(px.bar(yr, x="YEAR", y="VALUE", title="Annual total"), use_container_width=True)

# ---------- Countries ----------
with tab2:
    by_c = f.groupby("COUNTRY", observed=True, as_index=False).VALUE.sum()
    left, right = st.columns(2)
    left.plotly_chart(
        px.choropleth(by_c, locations="COUNTRY", locationmode="country names",
                      color="VALUE", color_continuous_scale="Blues", title="Exports by destination"),
        use_container_width=True)
    t = by_c.nlargest(top_n, "VALUE")
    right.plotly_chart(
        px.bar(t, x="VALUE", y="COUNTRY", orientation="h", title=f"Top {top_n} destinations")
          .update_yaxes(autorange="reversed"), use_container_width=True)

# ---------- Commodities ----------
with tab3:
    by_h = f.groupby(["CHAPTER", "HEADING NAME"], observed=True, as_index=False).VALUE.sum()
    by_h = by_h[by_h.VALUE > 0]
    st.plotly_chart(px.treemap(by_h, path=["CHAPTER", "HEADING NAME"], values="VALUE",
                               title="Chapter → heading"), use_container_width=True)
    t = by_h.nlargest(top_n, "VALUE")
    st.plotly_chart(px.bar(t, x="VALUE", y="HEADING NAME", orientation="h",
                           title=f"Top {top_n} headings").update_yaxes(autorange="reversed"),
                    use_container_width=True)

# ---------- Data ----------
with tab4:
    out = f.groupby(["YEAR", "CHAPTER", "HEADING NAME", "COUNTRY"], observed=True, as_index=False).VALUE.sum()
    st.dataframe(out, use_container_width=True, hide_index=True)
    st.download_button("Download filtered data (CSV)", out.to_csv(index=False), "filtered_exports.csv")
