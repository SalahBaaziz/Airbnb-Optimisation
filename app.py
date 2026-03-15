"""
AirbnbEdge — Local Flask Web App
Run: python app.py
Then open: http://localhost:5050
"""

from flask import Flask, render_template, request, jsonify
import pandas as pd
import numpy as np
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.cluster import KMeans
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import mean_absolute_error, r2_score
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import ast, os, json, warnings, io
warnings.filterwarnings("ignore")

app = Flask(__name__)

# ─── Global model state ───────────────────────────────────────────────────────
M = {}

AMENITY_KEYS = [
    "amen_hot_tub","amen_pool","amen_gym","amen_ev_charger","amen_sauna",
    "amen_fireplace","amen_dedicated_workspace","amen_netflix","amen_wifi",
    "amen_free_parking","amen_air_conditioning","amen_breakfast",
    "amen_self_check-in","amen_washer","amen_dryer","amen_dishwasher",
    "amen_espresso_machine","amen_piano","amen_baby_monitor","amen_elevator",
    "amen_waterfront","amen_garden","amen_balcony","amen_harbor_view",
]

HIGH_VALUE_AMENITIES = [
    "Hot tub","Pool","Gym","EV charger","Sauna","Fireplace",
    "Dedicated workspace","Netflix","Wifi","Free parking","Air conditioning",
    "Breakfast","Self check-in","Washer","Dryer","Dishwasher","Espresso machine",
    "Piano","Baby monitor","Elevator","Waterfront","Garden","Balcony","Harbor view",
]

FEATURES = [
    "price","accommodates","bedrooms","beds","bathrooms",
    "minimum_nights","availability_365","total_amenities",
    "host_engagement","host_years_experience","host_listings_count",
    "review_scores_rating","review_scores_cleanliness","review_scores_location",
    "review_scores_value","reviews_per_month","instant_bookable",
    "host_is_superhost","is_entire_home","neighbourhood_rank","demand_score",
] + AMENITY_KEYS

CITIES = {
    "bristol":    "dataset/bristol.csv",
    "london":     "dataset/london.csv",
    "edinburgh":  "dataset/edinburgh.csv",
    "manchester": "dataset/manchester.csv",
}

AIRBNB_FEE = 0.03

CHART_LAYOUT = dict(
    plot_bgcolor="white",
    paper_bgcolor="white",
    font=dict(family="Inter, sans-serif", size=11, color="#374151"),
    margin=dict(l=10, r=10, t=50, b=40),
)

PRIMARY_COLORS = ["#1E3A5F","#2563EB","#0D9488","#D97706","#EF4444","#16A34A",
                  "#7C3AED","#DB2777","#0891B2","#65A30D"]


# ─── Data & model training ────────────────────────────────────────────────────

def parse_amenities(amenity_str):
    try:
        lst = ast.literal_eval(amenity_str) if isinstance(amenity_str, str) else []
        return {f"amen_{kw.lower().replace(' ','_')}":
                int(any(kw.lower() in a.lower() for a in lst))
                for kw in HIGH_VALUE_AMENITIES}
    except Exception:
        return {f"amen_{kw.lower().replace(' ','_')}": 0 for kw in HIGH_VALUE_AMENITIES}


def load_city(city: str, csv_path: str = None) -> pd.DataFrame | None:
    if csv_path is None:
        path = os.path.join(os.path.dirname(__file__), CITIES.get(city, CITIES["bristol"]))
    else:
        path = csv_path
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path, low_memory=False)
    return _process_df(df)


def load_city_from_df(df: pd.DataFrame) -> pd.DataFrame | None:
    return _process_df(df.copy())


def _process_df(df: pd.DataFrame) -> pd.DataFrame:
    # Price cleaning
    if df["price"].dtype == object:
        df["price"] = df["price"].str.replace(r"[\$,]", "", regex=True).astype(float)
    for col in ["host_response_rate", "host_acceptance_rate"]:
        if col in df.columns and df[col].dtype == object:
            df[col] = df[col].str.replace("%", "").astype(float) / 100
    for col in ["host_is_superhost", "host_has_profile_pic", "host_identity_verified", "instant_bookable"]:
        if col in df.columns and df[col].dtype == object:
            df[col] = df[col].map({"t": 1, "f": 0})
    for col in ["host_since", "first_review", "last_review"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    if "host_since" in df.columns:
        df["host_years_experience"] = (pd.Timestamp("2025-06-24") - df["host_since"]).dt.days / 365
    else:
        df["host_years_experience"] = 1.0

    p1, p99 = df["price"].quantile([0.01, 0.99])
    df = df[(df["price"] >= p1) & (df["price"] <= p99)].dropna(
        subset=["price", "latitude", "longitude", "neighbourhood_cleansed"]
    ).copy()

    amenity_dummies = df["amenities"].apply(parse_amenities) if "amenities" in df.columns else pd.Series([{}]*len(df), index=df.index)
    amenity_df = pd.DataFrame(amenity_dummies.tolist(), index=df.index)
    amenity_df.columns = [f"amen_{kw.lower().replace(' ','_')}" for kw in HIGH_VALUE_AMENITIES]
    df = pd.concat([df, amenity_df], axis=1)
    df["total_amenities"] = amenity_df.sum(axis=1)

    # Estimate occupancy from availability if not provided (days booked = 365 - availability)
    if "estimated_occupancy_l365d" not in df.columns or df["estimated_occupancy_l365d"].fillna(0).eq(0).all():
        if "availability_365" in df.columns:
            df["estimated_occupancy_l365d"] = (365 - df["availability_365"].clip(0, 365)).clip(lower=0)
        else:
            df["estimated_occupancy_l365d"] = 182  # assume ~50% occupancy as fallback

    if "estimated_revenue_l365d" not in df.columns or df["estimated_revenue_l365d"].fillna(0).eq(0).all():
        df["estimated_revenue_l365d"] = (df["price"] * df["estimated_occupancy_l365d"]).clip(lower=0)

    df["occupancy_rate"]  = (df["estimated_occupancy_l365d"] / 365).clip(0, 1)
    df["revpar"]          = df["price"] * df["occupancy_rate"]
    df["demand_score"]    = 1 - (df["availability_365"] / 365) if "availability_365" in df.columns else 0.5

    hr = df["host_response_rate"].fillna(0) if "host_response_rate" in df.columns else 0
    ha = df["host_acceptance_rate"].fillna(0) if "host_acceptance_rate" in df.columns else 0
    hs = df["host_is_superhost"].fillna(0) if "host_is_superhost" in df.columns else 0
    df["host_engagement"] = hr * 0.4 + ha * 0.3 + hs * 0.3

    neigh_rank = df.groupby("neighbourhood_cleansed")["estimated_revenue_l365d"].median().rank(pct=True)
    df["neighbourhood_rank"] = df["neighbourhood_cleansed"].map(neigh_rank)
    df["is_entire_home"] = (df["room_type"] == "Entire home/apt").astype(int) if "room_type" in df.columns else 0

    for col in ["bedrooms","beds","bathrooms","accommodates","minimum_nights",
                "availability_365","host_listings_count","reviews_per_month",
                "review_scores_rating","review_scores_cleanliness","review_scores_location",
                "review_scores_value","review_scores_checkin","review_scores_communication"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def train_model(df: pd.DataFrame) -> dict:
    model_df = df[FEATURES + ["estimated_revenue_l365d"]].dropna()
    model_df = model_df[model_df["estimated_revenue_l365d"] > 0]
    X = model_df[FEATURES]
    y = model_df["estimated_revenue_l365d"]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # GBM
    gb = GradientBoostingRegressor(n_estimators=300, learning_rate=0.05,
                                    max_depth=5, subsample=0.8, random_state=42)
    gb.fit(X_train, y_train)

    # RF
    rf = RandomForestRegressor(n_estimators=100, max_depth=10, n_jobs=-1, random_state=42)
    rf.fit(X_train, y_train)

    # Linear Regression
    lr = LinearRegression()
    lr.fit(X_train, y_train)

    # Ridge
    ridge = Ridge(alpha=1.0)
    ridge.fit(X_train, y_train)

    # Model scores
    model_scores = {}
    for name, mdl in [("GBM", gb), ("RF", rf), ("LR", lr), ("Ridge", ridge)]:
        y_pred = mdl.predict(X_test)
        model_scores[name] = {
            "r2":  round(float(r2_score(y_test, y_pred)), 4),
            "mae": round(float(mean_absolute_error(y_test, y_pred)), 0),
        }

    # Cross-validation for GBM
    cv_raw = cross_val_score(gb, X, y, cv=5, scoring="r2")
    cv_scores = {"mean": round(float(cv_raw.mean()), 4), "std": round(float(cv_raw.std()), 4)}

    # KMeans clustering
    km_feats = ["price","estimated_revenue_l365d","availability_365","accommodates"]
    km_df = model_df[km_feats].dropna()
    km = KMeans(n_clusters=5, random_state=42, n_init=10)
    km.fit(km_df.values)

    # Optimal price simulation
    median_row = X.median().copy()
    median_row["is_entire_home"] = 1
    price_range = np.arange(30, 500, 5)
    best_price, best_rev = 100.0, 0.0
    for p in price_range:
        r = median_row.copy(); r["price"] = p
        rev = gb.predict([r])[0]
        if rev > best_rev:
            best_rev, best_price = rev, float(p)

    neigh_stats = df.groupby("neighbourhood_cleansed").agg(
        median_price=("price","median"),
        median_revenue=("estimated_revenue_l365d","median"),
        mean_occupancy=("estimated_occupancy_l365d","mean"),
        listing_count=("id","count") if "id" in df.columns else ("price","count"),
        mean_rating=("review_scores_rating","mean"),
        lat=("latitude","mean"),
        lng=("longitude","mean"),
    ).round(2).reset_index()

    neigh_rank = df.groupby("neighbourhood_cleansed")["estimated_revenue_l365d"].median().rank(pct=True)

    return {
        "gb": gb, "rf": rf, "lr": lr, "ridge": ridge,
        "km": km, "km_feats": km_feats,
        "X": X, "y": y, "X_test": X_test, "y_test": y_test,
        "df": df,
        "opt_price": best_price,
        "neigh_stats": neigh_stats,
        "neigh_rank": neigh_rank,
        "feature_names": FEATURES,
        "model_scores": model_scores,
        "cv_scores": cv_scores,
    }


def init_app():
    print("Loading Bristol data and training models...")
    df = load_city("bristol")
    if df is None:
        print("ERROR: dataset/bristol.csv not found")
        return
    artefacts = train_model(df)
    M["bristol"] = artefacts
    M["active"] = "bristol"
    print(f"Ready  |  {len(df)} listings  |  opt_price=£{artefacts['opt_price']:.0f}")


# ─── Analysis helpers ─────────────────────────────────────────────────────────

def build_input_row(prop: dict, artefacts: dict) -> pd.Series:
    base = artefacts["X"].median().copy()
    neigh_rank = artefacts["neigh_rank"]
    base["neighbourhood_rank"]        = neigh_rank.get(prop.get("neighbourhood",""), 0.5)
    base["price"]                     = float(prop.get("nightly_price", 100))
    base["accommodates"]              = float(prop.get("accommodates", 4))
    base["bedrooms"]                  = float(prop.get("bedrooms", 2))
    base["beds"]                      = float(prop.get("beds", 2))
    base["bathrooms"]                 = float(prop.get("bathrooms", 1))
    base["minimum_nights"]            = float(prop.get("minimum_nights", 2))
    base["availability_365"]          = float(prop.get("days_available_year", 200))
    base["is_entire_home"]            = float(prop.get("is_entire_home", 1))
    base["host_is_superhost"]         = float(prop.get("is_superhost", 0))
    base["instant_bookable"]          = float(prop.get("instant_bookable", 0))
    base["host_years_experience"]     = float(prop.get("host_years_experience", 1))
    base["host_listings_count"]       = float(prop.get("host_listings_count", 1))
    base["review_scores_rating"]      = float(prop.get("review_scores_rating", 4.5))
    base["review_scores_cleanliness"] = float(prop.get("review_scores_cleanliness", 4.5))
    base["review_scores_location"]    = float(prop.get("review_scores_location", 4.5))
    base["review_scores_value"]       = float(prop.get("review_scores_value", 4.3))
    base["reviews_per_month"]         = float(prop.get("reviews_per_month", 2.0))
    base["demand_score"]              = 1 - float(prop.get("days_available_year", 200)) / 365
    base["host_engagement"] = (
        float(prop.get("host_response_rate", 0.9)) * 0.4 +
        float(prop.get("host_acceptance_rate", 0.85)) * 0.3 +
        float(prop.get("is_superhost", 0)) * 0.3
    )
    total_am = 0
    for k in AMENITY_KEYS:
        v = float(prop.get(k, 0))
        if k in base.index:
            base[k] = v
        total_am += v
    base["total_amenities"] = total_am
    return base


def compute_pl(revenue: float, prop: dict) -> dict:
    bookings      = revenue / max(float(prop.get("nightly_price",100)) * float(prop.get("avg_stay_length_nights",3)), 1)
    mortgage      = float(prop.get("monthly_mortgage_or_rent", 0)) * 12
    bills         = float(prop.get("monthly_bills", 0)) * 12
    insurance     = float(prop.get("monthly_insurance", 0)) * 12
    cleaning      = bookings * float(prop.get("cleaning_cost_per_stay", 0))
    consumables   = bookings * float(prop.get("consumables_per_stay", 0))
    maintenance   = float(prop.get("annual_maintenance", 0))
    airbnb_f      = revenue * AIRBNB_FEE
    total_costs   = mortgage + bills + insurance + cleaning + consumables + maintenance + airbnb_f
    net_profit    = revenue - total_costs
    margin_pct    = (net_profit / total_costs * 100) if total_costs > 0 else 0
    return dict(
        gross_revenue=round(revenue, 0),
        airbnb_fee=round(airbnb_f, 0),
        mortgage_rent=round(mortgage, 0),
        bills=round(bills, 0),
        insurance=round(insurance, 0),
        cleaning=round(cleaning, 0),
        consumables=round(consumables, 0),
        maintenance=round(maintenance, 0),
        total_costs=round(total_costs, 0),
        net_profit=round(net_profit, 0),
        profit_margin_pct=round(margin_pct, 1),
        bookings_per_year=round(bookings, 0),
    )


def score_property(prop: dict, neigh_rank: pd.Series, opt_price: float) -> dict:
    price_err = abs(float(prop.get("nightly_price",100)) - opt_price) / max(opt_price, 1)
    am_cnt = sum(float(prop.get(k, 0)) for k in AMENITY_KEYS)
    resp_sc = {"within an hour":1.0,"within a few hours":0.75,
               "within a day":0.4,"a few days or more":0.1}
    hq = (float(prop.get("host_response_rate",0.9))*6 +
          float(prop.get("host_acceptance_rate",0.85))*4 +
          float(prop.get("is_superhost",0))*6 +
          resp_sc.get(prop.get("host_response_time","within a few hours"),0.5)*4)
    bs = (8 if prop.get("instant_bookable") else 0) + \
         (6 if float(prop.get("minimum_nights",2))<=3 else 0) + \
         (6 if float(prop.get("days_available_year",200))>=200 else 0)
    rv = (min(float(prop.get("review_scores_rating",4.5))/5,1)*8 +
          min(float(prop.get("review_scores_cleanliness",4.5))/5,1)*6 +
          min(float(prop.get("number_of_reviews",0))/30,1)*6)
    lq = min(20, int(am_cnt/12*10) + (5 if prop.get("is_entire_home") else 0) +
             (5 if float(prop.get("bedrooms",2))>=2 else 2))
    nr = neigh_rank.get(prop.get("neighbourhood",""), 0.5)
    loc = int(nr*14) + (6 if float(prop.get("days_available_year",200))>=250 else 3)
    scores = {
        "Pricing":      max(0, int(20*(1-price_err*2))),
        "Amenities":    min(20, int(am_cnt/24*20)),
        "Host Quality": min(20, int(hq)),
        "Booking Setup":min(20, bs),
        "Reviews":      min(20, int(rv)),
        "Listing":      min(20, lq),
        "Location":     min(20, loc),
    }
    total = sum(scores.values())
    cat = ("Underperforming" if total<=40 else "Average" if total<=70 else
           "Good" if total<=100 else "Strong" if total<=120 else "Excellent")
    return {"scores": scores, "total": total, "category": cat}


def compute_opportunities(row: pd.Series, current_rev: float,
                           artefacts: dict, prop: dict) -> list:
    gb   = artefacts["gb"]
    opt  = artefacts["opt_price"]
    am_tot = float(row["total_amenities"])
    LEVERS = {
        "Enable Instant Booking":         {"instant_bookable": 1},
        "Achieve Superhost Status":        {"host_is_superhost": 1, "host_engagement": min(float(row["host_engagement"])+0.3,1)},
        "Optimise Nightly Price":          {"price": opt},
        "Respond Within 1 Hour":           {"host_engagement": min(float(row["host_engagement"])+0.15,1)},
        "Open 300+ Days/Year":             {"availability_365": 300, "demand_score": 1-300/365},
        "Set 2-Night Minimum Stay":        {"minimum_nights": 2},
        "Add Dedicated Workspace":         {"amen_dedicated_workspace": 1, "total_amenities": am_tot+1},
        "Add Self Check-in / Smart Lock":  {"amen_self_check-in": 1, "total_amenities": am_tot+1},
        "Add Free Parking":                {"amen_free_parking": 1, "total_amenities": am_tot+1},
        "Add Air Conditioning":            {"amen_air_conditioning": 1, "total_amenities": am_tot+1},
        "Add Washer":                      {"amen_washer": 1, "total_amenities": am_tot+1},
        "Add Balcony / Garden":            {"amen_balcony": 1, "total_amenities": am_tot+1},
        "Add Breakfast":                   {"amen_breakfast": 1, "total_amenities": am_tot+1},
        "Improve Cleanliness to 4.9":     {"review_scores_cleanliness": 4.9},
        "Improve Overall Rating to 4.9":  {"review_scores_rating": 4.9},
    }
    results = []
    for name, changes in LEVERS.items():
        test = row.copy()
        already = all(abs(float(test.get(c, 0)) - v) < 0.01 for c, v in changes.items() if c in test.index)
        if already:
            continue
        for c, v in changes.items():
            if c in test.index:
                test[c] = v
        pred = gb.predict([test[FEATURES]])[0]
        uplift_abs = pred - current_rev
        uplift_pct = uplift_abs / current_rev * 100 if current_rev > 0 else 0
        if uplift_pct > 0.5:
            results.append({"lever": name, "revenue": round(pred,0),
                             "uplift_abs": round(uplift_abs,0),
                             "uplift_pct": round(uplift_pct,1)})
    results.sort(key=lambda x: x["uplift_pct"], reverse=True)
    return results


# ─── Chart helpers ────────────────────────────────────────────────────────────

BLUE   = "#2563EB"
TEAL   = "#0D9488"
NAVY   = "#1E3A5F"
AMBER  = "#D97706"
RED    = "#EF4444"
GREEN  = "#16A34A"
GREY   = "#9CA3AF"
PALETTE = [NAVY, BLUE, TEAL, AMBER, RED, GREEN, "#7C3AED", "#DB2777"]


def _S(fig, height=380, l=64, r=32, t=52, b=52):
    """Apply consistent chart style."""
    fig.update_layout(
        plot_bgcolor="white", paper_bgcolor="white",
        font=dict(family="Inter, sans-serif", size=13, color="#374151"),
        margin=dict(l=l, r=r, t=t, b=b),
        height=height,
        hoverlabel=dict(bgcolor="white", bordercolor="#E5E7EB", font_size=13,
                        font_family="Inter, sans-serif"),
    )
    fig.update_xaxes(gridcolor="#F3F4F6", linecolor="#E5E7EB",
                     zerolinecolor="#E5E7EB", automargin=True, tickfont_size=12)
    fig.update_yaxes(gridcolor="#F3F4F6", linecolor="#E5E7EB",
                     zerolinecolor="#E5E7EB", automargin=True, tickfont_size=12)
    return fig

# keep old name as alias so no other code breaks
def _apply_style(fig, height=380):
    return _S(fig, height)


# ─── Market Chart Builders ────────────────────────────────────────────────────

def chart_neighbourhood_revenue(artefacts: dict) -> dict:
    ns = artefacts["neigh_stats"]
    ns = ns[ns["listing_count"] >= 10].sort_values("median_revenue", ascending=True).tail(20)
    # Colour bars by value (light→dark blue)
    norm = (ns["median_revenue"] - ns["median_revenue"].min()) / (ns["median_revenue"].max() - ns["median_revenue"].min() + 1)
    bar_colors = [f"rgba(37,99,235,{0.35 + 0.65*v:.2f})" for v in norm]
    fig = go.Figure(go.Bar(
        x=ns["median_revenue"], y=ns["neighbourhood_cleansed"],
        orientation="h",
        marker_color=bar_colors,
        customdata=ns["listing_count"].values,
        hovertemplate="<b>%{y}</b><br>Median Revenue: <b>£%{x:,.0f}</b><br>Listings: %{customdata}<extra></extra>",
    ))
    fig.update_layout(title="Top Neighbourhoods by Median Annual Revenue",
                      xaxis_title="Median Annual Revenue (£/yr)")
    _S(fig, 540, l=180, r=20, t=52, b=48)
    fig.update_xaxes(tickprefix="£", tickformat=",")
    return json.loads(fig.to_json())


def chart_neighbourhood_scatter(artefacts: dict) -> dict:
    ns = artefacts["neigh_stats"]
    ns = ns[ns["listing_count"] >= 5].copy()
    fig = go.Figure(go.Scatter(
        x=ns["median_price"], y=ns["median_revenue"],
        mode="markers",
        marker=dict(
            size=np.sqrt(ns["listing_count"]).clip(10, 45),
            color=ns["mean_rating"], colorscale="RdYlGn",
            cmin=4.0, cmax=5.0, showscale=True,
            colorbar=dict(title="Rating", thickness=14, len=0.75),
            line=dict(color="white", width=1.5), opacity=0.85,
        ),
        text=ns["neighbourhood_cleansed"],
        hovertemplate="<b>%{text}</b><br>Price: £%{x:.0f}/night<br>Revenue: £%{y:,.0f}/yr<extra></extra>",
    ))
    fig.update_layout(title="Price vs Revenue by Neighbourhood",
                      xaxis_title="Median Nightly Price (£)",
                      yaxis_title="Median Annual Revenue (£)")
    _S(fig, 460, l=80, r=100, t=52, b=56)
    fig.update_xaxes(tickprefix="£")
    fig.update_yaxes(tickprefix="£", tickformat=",")
    return json.loads(fig.to_json())


def chart_price_dist(artefacts: dict) -> dict:
    df = artefacts["df"]
    fig = go.Figure()
    colors = {"Entire home/apt": BLUE, "Private room": TEAL,
              "Hotel room": AMBER, "Shared room": RED}
    for rt, clr in colors.items():
        sub = df[df["room_type"] == rt]["price"] if "room_type" in df.columns else pd.Series(dtype=float)
        if len(sub) < 5:
            continue
        fig.add_trace(go.Histogram(
            x=sub, name=rt, nbinsx=40, opacity=0.7,
            marker_color=clr,
            hovertemplate=f"<b>{rt}</b><br>£%{{x:.0f}}<br>%{{y}} listings<extra></extra>",
        ))
    med = df["price"].median()
    fig.add_vline(x=med, line_color=NAVY, line_width=2, line_dash="dash",
                  annotation_text=f"  Median £{med:.0f}", annotation_position="top right",
                  annotation_font_color=NAVY)
    fig.update_layout(title="Nightly Price Distribution by Room Type",
                      xaxis_title="Nightly Price (£)", yaxis_title="Number of Listings",
                      barmode="overlay",
                      legend=dict(x=0.65, y=0.95, bgcolor="rgba(255,255,255,0.8)",
                                  bordercolor="#E5E7EB", borderwidth=1),
                      xaxis_range=[0, 500])
    _S(fig, 380)
    return json.loads(fig.to_json())


def chart_revenue_dist(artefacts: dict) -> dict:
    df = artefacts["df"]
    rev = df["estimated_revenue_l365d"].dropna()
    rev = rev[rev > 0]
    # cap at 99th pct for cleaner display
    cap = rev.quantile(0.99)
    rev_disp = rev[rev <= cap]
    fig = go.Figure(go.Histogram(
        x=rev_disp, nbinsx=50,
        marker_color=BLUE, marker_line_color="white", marker_line_width=0.5,
        opacity=0.85,
        hovertemplate="£%{x:,.0f}<br>%{y} listings<extra></extra>",
    ))
    pctiles = [(25, AMBER, "Q1"), (50, TEAL, "Median"), (75, RED, "Q3"), (90, NAVY, "P90")]
    for pct, clr, lbl in pctiles:
        val = rev.quantile(pct / 100)
        fig.add_vline(x=val, line_color=clr, line_width=1.8, line_dash="dash",
                      annotation_text=f"  {lbl} £{val:,.0f}",
                      annotation_position="top right",
                      annotation_font_color=clr, annotation_font_size=11)
    fig.update_layout(title="Annual Revenue Distribution",
                      xaxis_title="Estimated Annual Revenue (£)",
                      yaxis_title="Listings", showlegend=False)
    _S(fig, 380)
    fig.update_xaxes(tickprefix="£", tickformat=",")
    return json.loads(fig.to_json())


def chart_property_type_revenue(artefacts: dict) -> dict:
    df = artefacts["df"]
    if "property_type" not in df.columns:
        return {}
    pt = df.groupby("property_type")["estimated_revenue_l365d"].agg(["median", "count"]).reset_index()
    pt.columns = ["property_type", "median_revenue", "count"]
    pt = pt[pt["count"] >= 5].sort_values("median_revenue").tail(12)
    norm = (pt["median_revenue"] - pt["median_revenue"].min()) / (pt["median_revenue"].max() - pt["median_revenue"].min() + 1)
    bar_colors = [f"rgba(13,148,136,{0.3 + 0.7*v:.2f})" for v in norm]
    fig = go.Figure(go.Bar(
        x=pt["median_revenue"], y=pt["property_type"],
        orientation="h",
        marker_color=bar_colors,
        customdata=pt["count"].values,
        hovertemplate="<b>%{y}</b><br>Median Revenue: <b>£%{x:,.0f}</b><br>Listings: %{customdata}<extra></extra>",
    ))
    fig.update_layout(title="Median Revenue by Property Type",
                      xaxis_title="Median Annual Revenue (£)")
    _S(fig, 420, l=200, r=20, t=52, b=48)
    fig.update_xaxes(tickprefix="£", tickformat=",")
    return json.loads(fig.to_json())


def chart_room_type_breakdown(artefacts: dict) -> dict:
    df = artefacts["df"]
    if "room_type" not in df.columns:
        return {}
    rt_count = df["room_type"].value_counts().reset_index()
    rt_count.columns = ["room_type", "count"]
    rt_rev = df.groupby("room_type")["estimated_revenue_l365d"].median().reset_index()
    rt_rev.columns = ["room_type", "median_revenue"]
    colors = [BLUE, TEAL, AMBER, RED]
    fig = make_subplots(rows=1, cols=2,
                        subplot_titles=("Share of Listings", "Median Annual Revenue"),
                        specs=[[{"type": "pie"}, {"type": "bar"}]])
    fig.add_trace(go.Pie(
        labels=rt_count["room_type"], values=rt_count["count"],
        marker_colors=colors, hole=0.4,
        textfont_size=12,
        hovertemplate="<b>%{label}</b><br>%{value} listings (%{percent})<extra></extra>",
    ), row=1, col=1)
    fig.add_trace(go.Bar(
        x=rt_rev["room_type"], y=rt_rev["median_revenue"],
        marker_color=colors[:len(rt_rev)],
        hovertemplate="<b>%{x}</b><br>Median Revenue: £%{y:,.0f}<extra></extra>",
        showlegend=False,
    ), row=1, col=2)
    fig.update_yaxes(gridcolor="#F3F4F6", tickprefix="£", tickformat=",",
                     title_text="Median Revenue (£/yr)", row=1, col=2)
    fig.update_layout(title="Room Type Breakdown",
                      legend=dict(x=0.28, y=0.5, font_size=11))
    _S(fig, 380)
    return json.loads(fig.to_json())


def chart_occupancy_dist(artefacts: dict) -> dict:
    df = artefacts["df"]
    occ = df["estimated_occupancy_l365d"].dropna()
    occ = occ[occ > 0]
    mean_occ = occ.mean()
    med_occ  = occ.median()
    fig = go.Figure(go.Histogram(
        x=occ, nbinsx=45, marker_color=TEAL,
        marker_line_color="white", marker_line_width=0.5, opacity=0.85,
        hovertemplate="%{x:.0f} days booked<br>%{y} listings<extra></extra>",
    ))
    fig.add_vline(x=mean_occ, line_color=NAVY, line_width=2, line_dash="dash",
                  annotation_text=f"  Mean {mean_occ:.0f}d",
                  annotation_position="top right", annotation_font_color=NAVY)
    fig.add_vline(x=med_occ, line_color=AMBER, line_width=2, line_dash="dot",
                  annotation_text=f"  Median {med_occ:.0f}d",
                  annotation_position="top left", annotation_font_color=AMBER)
    fig.update_layout(title="Occupancy Distribution (Booked Days/Year)",
                      xaxis_title="Booked Days per Year", yaxis_title="Listings",
                      showlegend=False)
    _S(fig, 360)
    return json.loads(fig.to_json())


def chart_superhost_impact(artefacts: dict) -> dict:
    df = artefacts["df"]
    fig = make_subplots(rows=1, cols=2,
                        subplot_titles=("Superhost vs Regular", "Instant vs Request to Book"))
    if "host_is_superhost" in df.columns:
        sh = df.groupby("host_is_superhost")["estimated_revenue_l365d"].median().reset_index()
        sh["label"] = sh["host_is_superhost"].map({0: "Regular", 1: "Superhost"})
        fig.add_trace(go.Bar(
            x=sh["label"], y=sh["estimated_revenue_l365d"],
            marker_color=[GREY, BLUE],
            hovertemplate="<b>%{x}</b><br>£%{y:,.0f}/yr<extra></extra>",
            showlegend=False,
        ), row=1, col=1)
    if "instant_bookable" in df.columns:
        ib = df.groupby("instant_bookable")["estimated_revenue_l365d"].median().reset_index()
        ib["label"] = ib["instant_bookable"].map({0: "Request", 1: "Instant Book"})
        fig.add_trace(go.Bar(
            x=ib["label"], y=ib["estimated_revenue_l365d"],
            marker_color=[GREY, TEAL],
            hovertemplate="<b>%{x}</b><br>£%{y:,.0f}/yr<extra></extra>",
            showlegend=False,
        ), row=1, col=2)
    fig.update_yaxes(gridcolor="#F3F4F6", tickprefix="£", tickformat=",",
                     title_text="Median Annual Revenue", row=1, col=1)
    fig.update_yaxes(gridcolor="#F3F4F6", tickprefix="£", tickformat=",", row=1, col=2)
    _S(fig, 360)
    return json.loads(fig.to_json())


def chart_review_heatmap(artefacts: dict) -> dict:
    df = artefacts["df"]
    cols = ["review_scores_rating", "review_scores_cleanliness", "review_scores_checkin",
            "review_scores_communication", "review_scores_location", "review_scores_value",
            "price", "estimated_revenue_l365d"]
    available = [c for c in cols if c in df.columns]
    sub = df[available].dropna()
    if len(sub) < 10:
        return {}
    corr = sub.corr().round(2)
    labels = [c.replace("review_scores_", "").replace("estimated_", "").replace("_l365d", "")
               .replace("_", " ").title() for c in corr.columns]
    fig = go.Figure(go.Heatmap(
        z=corr.values, x=labels, y=labels,
        colorscale="RdBu", zmid=0, zmin=-1, zmax=1,
        text=corr.values.round(2), texttemplate="%{text}",
        textfont=dict(size=11),
        hovertemplate="<b>%{y} × %{x}</b><br>r = %{z:.2f}<extra></extra>",
        colorbar=dict(title="r", thickness=14, len=0.8),
    ))
    fig.update_layout(title="Review Scores & Revenue Correlation")
    _S(fig, 440, l=110, r=80, t=52, b=110)
    return json.loads(fig.to_json())


def chart_amenity_impact(artefacts: dict) -> dict:
    df = artefacts["df"]
    impacts = []
    amenity_labels = dict(zip(AMENITY_KEYS, HIGH_VALUE_AMENITIES))
    for key in AMENITY_KEYS:
        if key not in df.columns:
            continue
        with_am = df[df[key] == 1]["estimated_revenue_l365d"].median()
        without = df[df[key] == 0]["estimated_revenue_l365d"].median()
        count_with = int((df[key] == 1).sum())
        if count_with < 20 or pd.isna(with_am) or pd.isna(without) or without == 0:
            continue
        uplift = (with_am - without) / without * 100
        impacts.append({"amenity": amenity_labels.get(key, key), "uplift": round(uplift, 1),
                        "count": count_with, "with": with_am, "without": without})
    impacts.sort(key=lambda x: x["uplift"], reverse=True)
    top = impacts[:15]
    if not top:
        return {}
    uplifts = [t["uplift"] for t in top]
    norm = [(v - min(uplifts)) / (max(uplifts) - min(uplifts) + 0.01) for v in uplifts]
    bar_colors = [f"rgba(13,148,136,{0.3 + 0.7*v:.2f})" for v in reversed(norm)]
    fig = go.Figure(go.Bar(
        x=uplifts,
        y=[t["amenity"] for t in top],
        orientation="h",
        marker_color=bar_colors,
        customdata=[[t["count"], t["with"], t["without"]] for t in top],
        hovertemplate="<b>%{y}</b><br>Revenue uplift: <b>+%{x:.1f}%</b><br>"
                      "With: £%{customdata[1]:,.0f} · Without: £%{customdata[2]:,.0f}<br>"
                      "%{customdata[0]} listings with this amenity<extra></extra>",
    ))
    fig.update_layout(title="Amenity Revenue Uplift vs Listings Without",
                      xaxis_title="Revenue Uplift (%)", yaxis_autorange="reversed")
    _S(fig, 480, l=160, r=20, t=52, b=48)
    return json.loads(fig.to_json())


def chart_price_by_bedrooms(artefacts: dict) -> dict:
    df = artefacts["df"].copy()
    df["bed_bucket"] = df["bedrooms"].clip(0, 6).fillna(0).astype(int)
    grp = df.groupby("bed_bucket").agg(price=("price", "median"), count=("price", "count")).reset_index()
    fig = go.Figure(go.Bar(
        x=grp["bed_bucket"], y=grp["price"],
        marker_color=BLUE, marker_line_color="white", marker_line_width=0.5,
        customdata=grp["count"].values,
        hovertemplate="<b>%{x} bedrooms</b><br>Median Price: £%{y:.0f}/night<br>%{customdata} listings<extra></extra>",
    ))
    fig.update_layout(title="Nightly Price by Bedroom Count",
                      xaxis_title="Bedrooms", yaxis_title="Median Price (£/night)",
                      xaxis=dict(tickmode="array", tickvals=list(range(7))))
    _S(fig, 350)
    fig.update_yaxes(tickprefix="£")
    return json.loads(fig.to_json())


def chart_revenue_by_bedrooms(artefacts: dict) -> dict:
    df = artefacts["df"].copy()
    df["bed_bucket"] = df["bedrooms"].clip(0, 6).fillna(0).astype(int)
    grp = df.groupby("bed_bucket").agg(
        rev=("estimated_revenue_l365d", "median"),
        count=("estimated_revenue_l365d", "count")
    ).reset_index()
    fig = go.Figure(go.Bar(
        x=grp["bed_bucket"], y=grp["rev"],
        marker_color=TEAL, marker_line_color="white", marker_line_width=0.5,
        customdata=grp["count"].values,
        hovertemplate="<b>%{x} bedrooms</b><br>Median Revenue: £%{y:,.0f}/yr<br>%{customdata} listings<extra></extra>",
    ))
    fig.update_layout(title="Annual Revenue by Bedroom Count",
                      xaxis_title="Bedrooms", yaxis_title="Median Revenue (£/yr)",
                      xaxis=dict(tickmode="array", tickvals=list(range(7))))
    _S(fig, 350)
    fig.update_yaxes(tickprefix="£", tickformat=",")
    return json.loads(fig.to_json())


def chart_min_nights_revenue(artefacts: dict) -> dict:
    df = artefacts["df"].copy()

    def bucket_min(x):
        if x <= 1: return "1 night"
        if x <= 3: return "2–3 nights"
        if x <= 7: return "4–7 nights"
        return "8+ nights"

    df["min_bucket"] = df["minimum_nights"].apply(bucket_min)
    order = ["1 night", "2–3 nights", "4–7 nights", "8+ nights"]
    grp = df.groupby("min_bucket")["estimated_revenue_l365d"].median().reindex(order).reset_index()
    fig = go.Figure(go.Bar(
        x=grp["min_bucket"], y=grp["estimated_revenue_l365d"],
        marker_color=[NAVY, BLUE, TEAL, AMBER],
        hovertemplate="<b>%{x}</b><br>Median Revenue: £%{y:,.0f}/yr<extra></extra>",
    ))
    fig.update_layout(title="Revenue by Minimum Nights Policy",
                      xaxis_title="Minimum Nights Setting",
                      yaxis_title="Median Annual Revenue (£)")
    _S(fig, 350)
    fig.update_yaxes(tickprefix="£", tickformat=",")
    return json.loads(fig.to_json())


def chart_availability_revenue(artefacts: dict) -> dict:
    df = artefacts["df"].copy()
    bins   = [0, 60, 120, 200, 280, 365]
    labels = ["0–60", "61–120", "121–200", "201–280", "281–365"]
    df["avail_bucket"] = pd.cut(df["availability_365"], bins=bins, labels=labels, include_lowest=True)
    grp = df.groupby("avail_bucket", observed=True)["estimated_revenue_l365d"].median().reset_index()
    fig = go.Figure(go.Bar(
        x=grp["avail_bucket"].astype(str), y=grp["estimated_revenue_l365d"],
        marker_color=[NAVY, BLUE, TEAL, AMBER, RED],
        hovertemplate="<b>%{x} days available</b><br>Median Revenue: £%{y:,.0f}/yr<extra></extra>",
    ))
    fig.update_layout(title="Revenue by Annual Availability Bucket",
                      xaxis_title="Availability (days/yr)",
                      yaxis_title="Median Annual Revenue (£)")
    _S(fig, 350)
    fig.update_yaxes(tickprefix="£", tickformat=",")
    return json.loads(fig.to_json())


def chart_host_experience_revenue(artefacts: dict) -> dict:
    df = artefacts["df"]
    sub = df[["host_years_experience", "estimated_revenue_l365d"]].dropna()
    sub = sub[sub["estimated_revenue_l365d"] > 0].sample(min(800, len(sub)), random_state=42)
    fig = go.Figure(go.Scatter(
        x=sub["host_years_experience"], y=sub["estimated_revenue_l365d"],
        mode="markers",
        marker=dict(color=BLUE, opacity=0.3, size=5),
        hovertemplate="Experience: %{x:.1f} yrs<br>Revenue: £%{y:,.0f}<extra></extra>",
        showlegend=False,
    ))
    if len(sub) > 10:
        xs = sub["host_years_experience"].values
        ys = sub["estimated_revenue_l365d"].values
        trend_x = np.linspace(xs.min(), xs.max(), 100)
        coefs = np.polyfit(xs, ys, 1)
        fig.add_trace(go.Scatter(
            x=trend_x, y=np.polyval(coefs, trend_x), mode="lines",
            line=dict(color=RED, width=2.5),
            name="Trend", showlegend=False,
        ))
    fig.update_layout(title="Host Experience vs Annual Revenue",
                      xaxis_title="Host Years on Platform",
                      yaxis_title="Annual Revenue (£)")
    _S(fig, 380)
    fig.update_yaxes(tickprefix="£", tickformat=",")
    return json.loads(fig.to_json())


def chart_response_time_revenue(artefacts: dict) -> dict:
    df = artefacts["df"]
    if "host_response_time" not in df.columns:
        return {}
    grp = df.groupby("host_response_time")["estimated_revenue_l365d"].median().reset_index()
    order_map = {"within an hour": 0, "within a few hours": 1, "within a day": 2, "a few days or more": 3}
    grp["order"] = grp["host_response_time"].map(order_map).fillna(4)
    grp = grp.sort_values("order")
    clrs = [GREEN, BLUE, AMBER, RED]
    fig = go.Figure(go.Bar(
        x=grp["host_response_time"], y=grp["estimated_revenue_l365d"],
        marker_color=clrs[:len(grp)],
        hovertemplate="<b>%{x}</b><br>Median Revenue: £%{y:,.0f}/yr<extra></extra>",
    ))
    fig.update_layout(title="Revenue by Host Response Time",
                      xaxis_title="Response Time",
                      yaxis_title="Median Annual Revenue (£)")
    _S(fig, 360)
    fig.update_yaxes(tickprefix="£", tickformat=",")
    return json.loads(fig.to_json())


def chart_rating_revenue(artefacts: dict) -> dict:
    df = artefacts["df"].copy()

    def bucket_rating(x):
        if pd.isna(x): return None
        if x < 4.0: return "<4.0 ★"
        if x < 4.5: return "4.0–4.5 ★"
        if x < 4.8: return "4.5–4.8 ★"
        return "4.8–5.0 ★"

    df["rating_bucket"] = df["review_scores_rating"].apply(bucket_rating)
    df = df.dropna(subset=["rating_bucket"])
    order = ["<4.0 ★", "4.0–4.5 ★", "4.5–4.8 ★", "4.8–5.0 ★"]
    grp = df.groupby("rating_bucket")["estimated_revenue_l365d"].median().reindex(order).reset_index()
    fig = go.Figure(go.Bar(
        x=grp["rating_bucket"], y=grp["estimated_revenue_l365d"],
        marker_color=[RED, AMBER, BLUE, GREEN],
        hovertemplate="<b>%{x}</b><br>Median Revenue: £%{y:,.0f}/yr<extra></extra>",
    ))
    fig.update_layout(title="Revenue by Review Rating Bracket",
                      xaxis_title="Rating Range",
                      yaxis_title="Median Annual Revenue (£)")
    _S(fig, 360)
    fig.update_yaxes(tickprefix="£", tickformat=",")
    return json.loads(fig.to_json())


# ─── Existing analyser chart builders ────────────────────────────────────────

def chart_opportunities(opportunities: list) -> dict:
    if not opportunities:
        return {}
    levers = [o["lever"] for o in opportunities]
    pcts   = [o["uplift_pct"] for o in opportunities]
    abss   = [o["uplift_abs"] for o in opportunities]
    norm   = [(v - min(pcts)) / (max(pcts) - min(pcts) + 0.01) for v in pcts]
    bar_colors = [f"rgba(22,163,74,{0.35 + 0.65*v:.2f})" for v in norm]
    fig = go.Figure(go.Bar(
        x=pcts, y=levers, orientation="h",
        marker_color=bar_colors,
        customdata=abss,
        hovertemplate="<b>%{y}</b><br>+%{x:.1f}% uplift<br>+£%{customdata:,.0f}/yr<extra></extra>",
    ))
    fig.update_layout(
        title="Ranked Optimisation Opportunities",
        xaxis_title="Revenue Uplift (%)", yaxis_autorange="reversed",
        height=max(380, len(levers) * 44 + 80),
    )
    _S(fig, max(380, len(levers) * 44 + 80), l=200, r=20, t=52, b=48)
    return json.loads(fig.to_json())


def chart_pl_waterfall(pl_curr: dict, pl_opt: dict) -> dict:
    labels = ["Gross Revenue", "Airbnb Fee", "Mortgage/Rent", "Bills",
              "Insurance", "Cleaning", "Consumables", "Maintenance", "NET PROFIT"]
    curr_v = [pl_curr["gross_revenue"], -pl_curr["airbnb_fee"], -pl_curr["mortgage_rent"],
              -pl_curr["bills"], -pl_curr["insurance"], -pl_curr["cleaning"],
              -pl_curr["consumables"], -pl_curr["maintenance"], pl_curr["net_profit"]]
    opt_v  = [pl_opt["gross_revenue"], -pl_opt["airbnb_fee"], -pl_opt["mortgage_rent"],
              -pl_opt["bills"], -pl_opt["insurance"], -pl_opt["cleaning"],
              -pl_opt["consumables"], -pl_opt["maintenance"], pl_opt["net_profit"]]
    clrs = [BLUE, RED, AMBER, AMBER, AMBER, "#EAB308", "#EAB308", "#EAB308",
            GREEN if pl_curr["net_profit"] >= 0 else RED]
    fig = go.Figure()
    fig.add_trace(go.Bar(name="Current", x=labels, y=curr_v, marker_color=clrs, opacity=0.9,
                         hovertemplate="<b>%{x}</b><br>Current: £%{y:,.0f}<extra></extra>"))
    fig.add_trace(go.Bar(name="Optimised", x=labels, y=opt_v, marker_color=clrs, opacity=0.45,
                         hovertemplate="<b>%{x}</b><br>Optimised: £%{y:,.0f}<extra></extra>"))
    fig.add_hline(y=0, line_color="#374151", line_width=1)
    fig.update_layout(
        title="Annual P&L — Current vs Optimised", barmode="group",
        yaxis_title="£ / year",
        legend=dict(orientation="h", x=0.4, y=1.1),
        xaxis=dict(gridcolor="#F3F4F6"), yaxis=dict(gridcolor="#F3F4F6", tickprefix="£", tickformat=","),
    )
    _S(fig, 420, l=80, r=20, t=60, b=48)
    return json.loads(fig.to_json())


def chart_profit_summary(pl_curr: dict, pl_opt: dict) -> dict:
    fig = make_subplots(rows=1, cols=2,
                        subplot_titles=("Net Annual Profit", "Net Profit Margin"))
    clr_curr = BLUE if pl_curr["net_profit"] >= 0 else RED
    clr_opt  = GREEN if pl_opt["net_profit"] >= 0 else RED
    fig.add_trace(go.Bar(
        x=["Current", "Optimised"], y=[pl_curr["net_profit"], pl_opt["net_profit"]],
        marker_color=[clr_curr, clr_opt],
        hovertemplate="<b>%{x}</b><br>£%{y:,.0f}<extra></extra>",
        showlegend=False,
    ), row=1, col=1)
    fig.add_trace(go.Bar(
        x=["Current", "Optimised"], y=[pl_curr["profit_margin_pct"], pl_opt["profit_margin_pct"]],
        marker_color=[clr_curr, clr_opt],
        hovertemplate="<b>%{x}</b><br>%{y:.1f}%<extra></extra>",
        showlegend=False,
    ), row=1, col=2)
    for ref, lbl, clr in [(10, "Break-even 10%", AMBER), (30, "Healthy 30%", GREEN), (60, "Excellent 60%", NAVY)]:
        fig.add_hline(y=ref, line_color=clr, line_width=1.5, line_dash="dash",
                      annotation_text=lbl, annotation_position="right",
                      annotation_font_color=clr, annotation_font_size=10, row=1, col=2)
    fig.add_hline(y=0, line_color="#374151", line_width=1, row=1, col=1)
    fig.add_hline(y=0, line_color="#374151", line_width=1, row=1, col=2)
    fig.update_yaxes(gridcolor="#F3F4F6", tickprefix="£", tickformat=",", row=1, col=1)
    fig.update_yaxes(gridcolor="#F3F4F6", ticksuffix="%", row=1, col=2)
    _S(fig, 380)
    return json.loads(fig.to_json())


def chart_scorecard(score_data: dict, score_data_opt: dict = None) -> dict:
    dims = list(score_data["scores"].keys())
    vals = list(score_data["scores"].values())
    max_v = [20] * len(dims)
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=vals + [vals[0]], theta=dims + [dims[0]],
        fill="toself", name="Current",
        line_color=RED, fillcolor="rgba(239,68,68,0.12)",
    ))
    if score_data_opt:
        opt_vals = list(score_data_opt["scores"].values())
        fig.add_trace(go.Scatterpolar(
            r=opt_vals + [opt_vals[0]], theta=dims + [dims[0]],
            fill="toself", name="Optimised",
            line_color=BLUE, fillcolor="rgba(37,99,235,0.12)",
        ))
    fig.add_trace(go.Scatterpolar(
        r=max_v + [max_v[0]], theta=dims + [dims[0]],
        fill=None, name="Max",
        line=dict(color="#D1D5DB", dash="dot", width=1), showlegend=False,
    ))
    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 20], gridcolor="#E5E7EB",
                            tickfont=dict(size=10, color="#9CA3AF")),
            angularaxis=dict(gridcolor="#E5E7EB"),
            bgcolor="white",
        ),
        title=f"Scorecard: {score_data['total']}/140 — {score_data['category']}",
        height=380, margin=dict(l=40, r=40, t=60, b=40),
        paper_bgcolor="white",
        font=dict(family="Inter, sans-serif", size=12, color="#374151"),
        legend=dict(x=0.82, y=1.1),
        showlegend=True,
    )
    return json.loads(fig.to_json())


# ─── Complex Analysis Chart Builders ─────────────────────────────────────────

def chart_gbm_importance(artefacts: dict) -> dict:
    gb = artefacts["gb"]
    feats = artefacts["feature_names"]
    imp = pd.Series(gb.feature_importances_, index=feats).sort_values().tail(20)
    norm = (imp.values - imp.values.min()) / (imp.values.max() - imp.values.min() + 1e-9)
    bar_colors = [f"rgba(37,99,235,{0.3 + 0.7*v:.2f})" for v in norm]
    fig = go.Figure(go.Bar(
        x=imp.values, y=imp.index, orientation="h",
        marker_color=bar_colors,
        hovertemplate="<b>%{y}</b><br>Importance: %{x:.4f}<extra></extra>",
    ))
    fig.update_layout(title="GBM — Top 20 Feature Importances",
                      xaxis_title="Feature Importance (Gain)")
    _S(fig, 520, l=180, r=20, t=52, b=48)
    return json.loads(fig.to_json())


def chart_rf_importance(artefacts: dict) -> dict:
    rf = artefacts["rf"]
    feats = artefacts["feature_names"]
    imp = pd.Series(rf.feature_importances_, index=feats).sort_values().tail(20)
    norm = (imp.values - imp.values.min()) / (imp.values.max() - imp.values.min() + 1e-9)
    bar_colors = [f"rgba(13,148,136,{0.3 + 0.7*v:.2f})" for v in norm]
    fig = go.Figure(go.Bar(
        x=imp.values, y=imp.index, orientation="h",
        marker_color=bar_colors,
        hovertemplate="<b>%{y}</b><br>Importance: %{x:.4f}<extra></extra>",
    ))
    fig.update_layout(title="Random Forest — Top 20 Feature Importances",
                      xaxis_title="Feature Importance (Mean Decrease Impurity)")
    _S(fig, 520, l=180, r=20, t=52, b=48)
    return json.loads(fig.to_json())


def chart_model_comparison(artefacts: dict) -> dict:
    ms = artefacts["model_scores"]
    models = list(ms.keys())
    r2s  = [ms[m]["r2"] for m in models]
    maes = [ms[m]["mae"] for m in models]
    model_colors = [NAVY, BLUE, TEAL, AMBER]
    fig = make_subplots(rows=1, cols=2, subplot_titles=("R² Score (↑ better)", "MAE — £/yr (↓ better)"))
    fig.add_trace(go.Bar(
        x=models, y=r2s, marker_color=model_colors,
        hovertemplate="<b>%{x}</b><br>R² = %{y:.4f}<extra></extra>",
        showlegend=False,
    ), row=1, col=1)
    fig.add_trace(go.Bar(
        x=models, y=maes, marker_color=model_colors,
        hovertemplate="<b>%{x}</b><br>MAE: £%{y:,.0f}<extra></extra>",
        showlegend=False,
    ), row=1, col=2)
    fig.update_yaxes(gridcolor="#F3F4F6", row=1, col=1)
    fig.update_yaxes(gridcolor="#F3F4F6", tickprefix="£", tickformat=",", row=1, col=2)
    _S(fig, 360)
    return json.loads(fig.to_json())


def chart_pricing_curve(artefacts: dict) -> dict:
    gb = artefacts["gb"]
    X  = artefacts["X"]
    opt_price = artefacts["opt_price"]
    median_row = X.median().copy()
    median_row["is_entire_home"] = 1
    prices = list(range(30, 505, 5))
    revenues = []
    for p in prices:
        r = median_row.copy(); r["price"] = p
        revenues.append(float(gb.predict([r])[0]))
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=prices, y=revenues, mode="lines",
        line=dict(color=BLUE, width=2.5),
        fill="tozeroy", fillcolor="rgba(37,99,235,0.08)",
        hovertemplate="Price: £%{x}/night<br>Predicted Revenue: £%{y:,.0f}/yr<extra></extra>",
        name="Predicted Revenue",
        showlegend=False,
    ))
    fig.add_vline(x=opt_price, line_color=RED, line_width=2, line_dash="dash",
                  annotation_text=f"  Optimal £{opt_price:.0f}",
                  annotation_position="top right", annotation_font_color=RED)
    fig.update_layout(title="Pricing Curve — Nightly Price vs Predicted Annual Revenue",
                      xaxis_title="Nightly Price (£)", yaxis_title="Predicted Revenue (£/yr)")
    _S(fig, 400)
    fig.update_xaxes(tickprefix="£")
    fig.update_yaxes(tickprefix="£", tickformat=",")
    return json.loads(fig.to_json())


def chart_cluster_revenue(artefacts: dict) -> dict:
    df   = artefacts["df"]
    km   = artefacts["km"]
    feats = artefacts["km_feats"]
    all_cols = list(dict.fromkeys(feats + ["estimated_revenue_l365d"]))
    km_df = df[all_cols].dropna()
    labels = km.predict(km_df[feats].values)
    km_df = km_df.copy()
    km_df["cluster"] = labels
    grp = km_df.groupby("cluster").agg(
        median_revenue=("estimated_revenue_l365d", "median"),
        count=("estimated_revenue_l365d", "count"),
    ).reset_index()
    grp["label"] = grp.apply(lambda r: f"Seg {r['cluster']+1}", axis=1)
    grp = grp.sort_values("median_revenue")
    colors = [NAVY, BLUE, TEAL, AMBER, RED]
    fig = go.Figure(go.Bar(
        x=grp["label"], y=grp["median_revenue"],
        marker_color=[colors[i % len(colors)] for i in range(len(grp))],
        customdata=grp["count"].values,
        hovertemplate="<b>%{x}</b><br>Median Revenue: £%{y:,.0f}/yr<br>%{customdata} listings<extra></extra>",
    ))
    fig.update_layout(title="Median Revenue per Market Segment",
                      xaxis_title="Segment (K-Means)", yaxis_title="Median Annual Revenue (£)")
    _S(fig, 380)
    fig.update_yaxes(tickprefix="£", tickformat=",")
    return json.loads(fig.to_json())


def chart_cluster_scatter(artefacts: dict) -> dict:
    df    = artefacts["df"]
    km    = artefacts["km"]
    feats = artefacts["km_feats"]
    all_cols = list(dict.fromkeys(feats + ["estimated_revenue_l365d"]))
    km_df = df[all_cols].dropna()
    labels = km.predict(km_df[feats].values)
    km_df = km_df.copy()
    km_df["cluster"] = labels.astype(str)
    sample = km_df.sample(min(1000, len(km_df)), random_state=42)
    colors = [NAVY, BLUE, TEAL, AMBER, RED]
    fig = go.Figure()
    for cl in sorted(sample["cluster"].unique()):
        sub = sample[sample["cluster"] == cl]
        fig.add_trace(go.Scatter(
            x=sub["price"], y=sub["estimated_revenue_l365d"],
            mode="markers",
            marker=dict(color=colors[int(cl) % len(colors)], opacity=0.4, size=5),
            name=f"Seg {int(cl)+1}",
            hovertemplate="£%{x}/night → £%{y:,.0f}/yr<extra></extra>",
        ))
    fig.update_layout(title="Price vs Revenue by Market Segment",
                      xaxis_title="Nightly Price (£)", yaxis_title="Annual Revenue (£)",
                      legend=dict(x=0.02, y=0.97, bgcolor="rgba(255,255,255,0.8)",
                                  bordercolor="#E5E7EB", borderwidth=1))
    _S(fig, 420)
    fig.update_xaxes(tickprefix="£")
    fig.update_yaxes(tickprefix="£", tickformat=",")
    return json.loads(fig.to_json())


def chart_corr_heatmap_complex(artefacts: dict) -> dict:
    df = artefacts["df"]
    target = "estimated_revenue_l365d"
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if target not in numeric_cols:
        return {}
    corr_series = df[numeric_cols].corr()[target].drop(target).abs().sort_values(ascending=False)
    top_cols = corr_series.head(14).index.tolist() + [target]
    sub = df[top_cols].dropna()
    if len(sub) < 10:
        return {}
    corr = sub.corr().round(2)
    labels = [c.replace("_l365d", "").replace("_", " ").replace("estimated", "est.").title()
              for c in corr.columns]
    fig = go.Figure(go.Heatmap(
        z=corr.values, x=labels, y=labels,
        colorscale="RdBu", zmid=0, zmin=-1, zmax=1,
        text=corr.values.round(2), texttemplate="%{text}",
        textfont=dict(size=10),
        colorbar=dict(title="r", thickness=14, len=0.8),
        hovertemplate="<b>%{y} × %{x}</b><br>r = %{z:.2f}<extra></extra>",
    ))
    fig.update_layout(title="Feature Correlation Heatmap (vs Revenue)")
    _S(fig, 500, l=120, r=80, t=52, b=120)
    return json.loads(fig.to_json())


def chart_pdp_accommodates(artefacts: dict) -> dict:
    gb = artefacts["gb"]
    X  = artefacts["X"]
    median_row = X.median().copy()
    acc_vals = list(range(1, 13))
    revenues = []
    for a in acc_vals:
        r = median_row.copy(); r["accommodates"] = a
        revenues.append(float(gb.predict([r])[0]))
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=acc_vals, y=revenues, mode="lines+markers",
        line=dict(color=TEAL, width=2.5),
        marker=dict(size=9, color=TEAL, line=dict(color="white", width=1.5)),
        fill="tozeroy", fillcolor="rgba(13,148,136,0.07)",
        hovertemplate="Guests: %{x}<br>Predicted Revenue: £%{y:,.0f}/yr<extra></extra>",
        showlegend=False,
    ))
    fig.update_layout(title="PDP — Guest Capacity vs Predicted Revenue",
                      xaxis_title="Accommodates (guests)",
                      yaxis_title="Predicted Revenue (£/yr)",
                      xaxis=dict(tickmode="array", tickvals=acc_vals))
    _S(fig, 360)
    fig.update_yaxes(tickprefix="£", tickformat=",")
    return json.loads(fig.to_json())


def chart_pdp_amenities(artefacts: dict) -> dict:
    gb = artefacts["gb"]
    X  = artefacts["X"]
    median_row = X.median().copy()
    am_vals = list(range(0, 21))
    revenues = []
    for a in am_vals:
        r = median_row.copy(); r["total_amenities"] = a
        revenues.append(float(gb.predict([r])[0]))
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=am_vals, y=revenues, mode="lines+markers",
        line=dict(color=AMBER, width=2.5),
        marker=dict(size=9, color=AMBER, line=dict(color="white", width=1.5)),
        fill="tozeroy", fillcolor="rgba(217,119,6,0.07)",
        hovertemplate="Amenities: %{x}<br>Predicted Revenue: £%{y:,.0f}/yr<extra></extra>",
        showlegend=False,
    ))
    fig.update_layout(title="PDP — Amenity Count vs Predicted Revenue",
                      xaxis_title="Total Amenities",
                      yaxis_title="Predicted Revenue (£/yr)")
    _S(fig, 360)
    fig.update_yaxes(tickprefix="£", tickformat=",")
    return json.loads(fig.to_json())


def chart_revpar_neighbourhood(artefacts: dict) -> dict:
    df = artefacts["df"].copy()
    df["revpar"] = df["price"] * df["occupancy_rate"]
    grp = df.groupby("neighbourhood_cleansed").agg(
        revpar=("revpar", "median"),
        count=("price", "count"),
    ).reset_index()
    grp = grp[grp["count"] >= 10].sort_values("revpar").tail(15)
    norm = (grp["revpar"] - grp["revpar"].min()) / (grp["revpar"].max() - grp["revpar"].min() + 1)
    bar_colors = [f"rgba(124,58,237,{0.3 + 0.7*v:.2f})" for v in norm]
    fig = go.Figure(go.Bar(
        x=grp["revpar"], y=grp["neighbourhood_cleansed"],
        orientation="h", marker_color=bar_colors,
        hovertemplate="<b>%{y}</b><br>Median RevPAR: £%{x:.1f}/night<extra></extra>",
    ))
    fig.update_layout(title="Top Neighbourhoods by RevPAR",
                      xaxis_title="Median RevPAR (£/available night)")
    _S(fig, 480, l=180, r=20, t=52, b=48)
    fig.update_xaxes(tickprefix="£")
    return json.loads(fig.to_json())


# ─── KPI helpers ──────────────────────────────────────────────────────────────

def build_kpis(df: pd.DataFrame, artefacts: dict) -> dict:
    top_neigh = ""
    if "neighbourhood_cleansed" in df.columns and "estimated_revenue_l365d" in df.columns:
        neigh_rev = df.groupby("neighbourhood_cleansed")["estimated_revenue_l365d"].median()
        if len(neigh_rev) > 0:
            top_neigh = str(neigh_rev.idxmax())

    median_revpar = float(df["revpar"].median()) if "revpar" in df.columns else 0.0
    avg_min_nights = float(df["minimum_nights"].mean()) if "minimum_nights" in df.columns else 0.0
    mean_occ = float(df["estimated_occupancy_l365d"].mean()) if "estimated_occupancy_l365d" in df.columns else 0.0

    return {
        "total_listings":   int(len(df)),
        "median_price":     float(df["price"].median()),
        "median_revenue":   float(df["estimated_revenue_l365d"].median()),
        "mean_occupancy":   round(mean_occ, 1),
        "superhost_pct":    round(float(df["host_is_superhost"].mean())*100, 1) if "host_is_superhost" in df.columns else 0,
        "instant_book_pct": round(float(df["instant_bookable"].mean())*100, 1) if "instant_bookable" in df.columns else 0,
        "avg_rating":       round(float(df["review_scores_rating"].mean()), 2) if "review_scores_rating" in df.columns else 0,
        "top_neighbourhood":top_neigh,
        "opt_price":        float(artefacts["opt_price"]),
        "entire_home_pct":  round(float(df["is_entire_home"].mean())*100, 1) if "is_entire_home" in df.columns else 0,
        "median_revpar":    round(median_revpar, 2),
        "avg_min_nights":   round(avg_min_nights, 1),
    }


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/cities")
def api_cities():
    cities = [c for c in ["bristol","london","edinburgh","manchester","custom"] if c in M]
    return jsonify(cities)


@app.route("/api/market")
def market_data():
    city = request.args.get("city", "bristol").lower()
    if city not in M:
        # Lazy-load other cities on demand
        if city in CITIES:
            print(f"Loading {city}...")
            df = load_city(city)
            if df is None:
                return jsonify({"error": f"Could not load {city} dataset"}), 503
            M[city] = train_model(df)
        else:
            return jsonify({"error": f"City '{city}' not available"}), 404

    a  = M[city]
    df = a["df"]

    kpis = build_kpis(df, a)

    charts = {
        "neighbourhood_revenue":   chart_neighbourhood_revenue(a),
        "neighbourhood_scatter":   chart_neighbourhood_scatter(a),
        "price_dist":              chart_price_dist(a),
        "revenue_dist":            chart_revenue_dist(a),
        "property_type_revenue":   chart_property_type_revenue(a),
        "room_type_breakdown":     chart_room_type_breakdown(a),
        "occupancy_dist":          chart_occupancy_dist(a),
        "superhost_impact":        chart_superhost_impact(a),
        "review_heatmap":          chart_review_heatmap(a),
        "amenity_impact":          chart_amenity_impact(a),
        "price_by_bedrooms":       chart_price_by_bedrooms(a),
        "revenue_by_bedrooms":     chart_revenue_by_bedrooms(a),
        "min_nights_revenue":      chart_min_nights_revenue(a),
        "availability_revenue":    chart_availability_revenue(a),
        "host_experience_revenue": chart_host_experience_revenue(a),
        "response_time_revenue":   chart_response_time_revenue(a),
        "rating_revenue":          chart_rating_revenue(a),
    }
    return jsonify({"kpis": kpis, "charts": charts})


@app.route("/api/complex")
def complex_data():
    city = request.args.get("city", "bristol").lower()
    if city not in M:
        if city in CITIES:
            print(f"Loading {city}...")
            df = load_city(city)
            if df is None:
                return jsonify({"error": f"Could not load {city} dataset"}), 503
            M[city] = train_model(df)
        else:
            return jsonify({"error": f"City '{city}' not available"}), 404

    a = M[city]

    charts = {
        "gbm_importance":   chart_gbm_importance(a),
        "rf_importance":    chart_rf_importance(a),
        "model_comparison": chart_model_comparison(a),
        "pricing_curve":    chart_pricing_curve(a),
        "cluster_revenue":  chart_cluster_revenue(a),
        "cluster_scatter":  chart_cluster_scatter(a),
        "corr_heatmap":     chart_corr_heatmap_complex(a),
        "pdp_accommodates": chart_pdp_accommodates(a),
        "pdp_amenities":    chart_pdp_amenities(a),
        "revpar_neighbourhood": chart_revpar_neighbourhood(a),
    }
    return jsonify({
        "model_scores": a["model_scores"],
        "cv_scores":    a["cv_scores"],
        "charts":       charts,
    })


@app.route("/api/analyse", methods=["POST"])
def analyse():
    city = request.args.get("city", "bristol").lower()
    if city not in M:
        city = "bristol"
    if city not in M:
        return jsonify({"error": "Model not loaded"}), 503

    prop = request.get_json()
    a    = M[city]
    gb   = a["gb"]

    row         = build_input_row(prop, a)
    current_rev = float(gb.predict([row[FEATURES]])[0])

    full = row.copy()
    full["host_is_superhost"]         = 1
    full["instant_bookable"]          = 1
    full["price"]                     = a["opt_price"]
    full["availability_365"]          = min(float(prop.get("days_available_year",200))+100, 330)
    full["demand_score"]              = 1 - full["availability_365"]/365
    full["review_scores_rating"]      = max(float(prop.get("review_scores_rating",4.5)), 4.85)
    full["review_scores_cleanliness"] = max(float(prop.get("review_scores_cleanliness",4.5)), 4.85)
    full["total_amenities"]           = min(float(row["total_amenities"])+5, 20)
    full["host_engagement"]           = 0.95
    full_rev = float(gb.predict([full[FEATURES]])[0])

    pl_curr = compute_pl(current_rev, prop)
    pl_opt  = compute_pl(full_rev,    prop)
    score   = score_property(prop, a["neigh_rank"], a["opt_price"])

    prop_opt = dict(prop)
    prop_opt.update({"is_superhost":1,"instant_bookable":1,"nightly_price":a["opt_price"],
                     "review_scores_rating":4.85,"review_scores_cleanliness":4.85})
    score_opt = score_property(prop_opt, a["neigh_rank"], a["opt_price"])

    opportunities = compute_opportunities(row, current_rev, a, prop)

    charts = {
        "opportunities":  chart_opportunities(opportunities),
        "pl_waterfall":   chart_pl_waterfall(pl_curr, pl_opt),
        "profit_summary": chart_profit_summary(pl_curr, pl_opt),
        "scorecard":      chart_scorecard(score, score_opt),
    }

    return jsonify({
        "current_revenue":    round(current_rev, 0),
        "optimised_revenue":  round(full_rev, 0),
        "pl_current":         pl_curr,
        "pl_optimised":       pl_opt,
        "score":              score,
        "score_optimised":    score_opt,
        "opportunities":      opportunities[:12],
        "opt_price":          a["opt_price"],
        "charts":             charts,
    })


@app.route("/api/scrape", methods=["POST"])
def scrape():
    data = request.get_json()
    url  = data.get("url", "").strip()
    if not url:
        return jsonify({"error": "No URL provided"}), 400
    try:
        from listing_scraper import scrape_listing
        result = scrape_listing(url, verbose=False)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    f = request.files["file"]
    if not f.filename.endswith(".csv"):
        return jsonify({"error": "File must be a CSV"}), 400
    try:
        content = f.read()
        df_raw = pd.read_csv(io.BytesIO(content), low_memory=False)
        required = ["price", "latitude", "longitude", "neighbourhood_cleansed"]
        missing = [c for c in required if c not in df_raw.columns]
        if missing:
            return jsonify({"error": f"Missing required columns: {missing}"}), 400

        df = load_city_from_df(df_raw)
        if df is None or len(df) < 10:
            return jsonify({"error": "Dataset too small or could not be processed"}), 400

        artefacts = train_model(df)
        M["custom"] = artefacts

        top_hoods = (df.groupby("neighbourhood_cleansed")["estimated_revenue_l365d"]
                     .median().sort_values(ascending=False).head(5).index.tolist())

        return jsonify({
            "city":                "custom",
            "total_listings":      int(len(df)),
            "columns_found":       list(df_raw.columns[:20]),
            "status":              "ok",
            "sample_neighbourhoods": top_hoods,
            "median_price":        float(df["price"].median()),
            "median_revenue":      float(df["estimated_revenue_l365d"].median()),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/neighbourhoods")
def neighbourhoods():
    city = request.args.get("city", "bristol").lower()
    if city not in M:
        city = "bristol"
    if city not in M:
        return jsonify([])
    hoods = sorted(M[city]["df"]["neighbourhood_cleansed"].dropna().unique().tolist())
    return jsonify(hoods)


# ─── Boot ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    init_app()
    app.run(debug=False, port=5050, threaded=True)
