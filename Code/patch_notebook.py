import json, os

with open('Airbnb_Profit_Optimiser.ipynb') as f:
    nb = json.load(f)

def code_cell(src):
    return {'cell_type': 'code', 'execution_count': None, 'metadata': {},
            'outputs': [], 'source': src}

def md_cell(src):
    return {'cell_type': 'markdown', 'metadata': {}, 'source': src}

# Keep cells 0–33 (everything up to executive dashboard)
new_cells = nb['cells'][:34]

# Keep the booking strategy cell (was cell 37)
new_cells.append(md_cell('### 5.2 Minimum Nights & Availability Strategy'))
new_cells.append(nb['cells'][37])

# ── Section 6 header ──────────────────────────────────────────────────────────
new_cells.append(md_cell(
    '---\n'
    '## 6. Interactive Property P&L Analyser\n'
    '> **Fill in every field in cell 6.1, then run 6.1 → 6.2 → 6.3 in order.**  \n'
    '> The model will score your property, rank your optimisation opportunities,\n'
    '> build a full P&L, and show your net profit as both a £ value and % of costs.'
))

# ── 6.1: PROPERTY INPUT ───────────────────────────────────────────────────────
INPUT_CELL = """\
# ============================================================
#   FILL IN YOUR PROPERTY DETAILS — then run 6.2 and 6.3
# ============================================================

PROPERTY = {

    # ── Location ──────────────────────────────────────────────
    # Options: Ashley, Central, Clifton, Clifton Down, Cotham, Easton,
    # Eastville, Hotwells & Harbourside, Lawrence Hill, Southville,
    # Windmill Hill, Bishopston & Ashley Down, Bedminster, Redland
    'neighbourhood': 'Clifton',

    # ── Property type ─────────────────────────────────────────
    'property_type': 'Entire home',
    'is_entire_home': 1,          # 1 = entire home/apt, 0 = private/shared room

    # ── Size ──────────────────────────────────────────────────
    'bedrooms':     2,
    'beds':         2,
    'bathrooms':    1,
    'accommodates': 4,

    # ── Pricing & availability ────────────────────────────────
    'nightly_price':       110,   # £ current nightly price
    'minimum_nights':        2,   # minimum stay
    'days_available_year': 200,   # days per year calendar is open

    # ── Host profile ──────────────────────────────────────────
    'is_superhost':          0,   # 1 = yes, 0 = no
    'instant_bookable':      0,   # 1 = on, 0 = off
    'host_years_experience': 1.0,
    'host_listings_count':   1,
    # Options: 'within an hour', 'within a few hours', 'within a day', 'a few days or more'
    'host_response_time':   'within a few hours',
    'host_response_rate':    0.90,   # 0.0 – 1.0
    'host_acceptance_rate':  0.85,

    # ── Review scores (0–5) ───────────────────────────────────
    'review_scores_rating':        4.5,
    'review_scores_cleanliness':   4.4,
    'review_scores_checkin':       4.6,
    'review_scores_communication': 4.7,
    'review_scores_location':      4.6,
    'review_scores_value':         4.3,
    'reviews_per_month':           2.0,
    'number_of_reviews':          15,

    # ── Amenities: 1 = you have it, 0 = you don't ────────────
    'amen_hot_tub':             0,
    'amen_pool':                0,
    'amen_gym':                 0,
    'amen_ev_charger':          0,
    'amen_sauna':               0,
    'amen_fireplace':           0,
    'amen_dedicated_workspace': 0,
    'amen_netflix':             1,
    'amen_wifi':                1,
    'amen_free_parking':        0,
    'amen_air_conditioning':    0,
    'amen_breakfast':           0,
    'amen_self_check-in':       0,
    'amen_washer':              1,
    'amen_dryer':               0,
    'amen_dishwasher':          0,
    'amen_espresso_machine':    0,
    'amen_piano':               0,
    'amen_baby_monitor':        0,
    'amen_elevator':            0,
    'amen_waterfront':          0,
    'amen_garden':              0,
    'amen_balcony':             0,
    'amen_harbor_view':         0,

    # ── Costs ─────────────────────────────────────────────────
    'monthly_mortgage_or_rent': 1400,   # £/month
    'monthly_bills':             180,   # £/month (utilities, broadband, council tax extra)
    'monthly_insurance':          50,   # £/month (STL insurance)
    'cleaning_cost_per_stay':     50,   # £ per booking
    'consumables_per_stay':       15,   # £ per stay (toiletries, linens wear, coffee etc)
    'annual_maintenance':        400,   # £/year
    'initial_setup_cost':       1500,   # £ one-off (furniture, smart lock, photos etc)
    'avg_stay_length_nights':      3,   # average booking length
}

print('Property details loaded.')
print(f'  {PROPERTY[\"property_type\"]} in {PROPERTY[\"neighbourhood\"]}')
print(f'  {PROPERTY[\"bedrooms\"]}BD / {PROPERTY[\"bathrooms\"]}BA / sleeps {PROPERTY[\"accommodates\"]}')
print(f'  £{PROPERTY[\"nightly_price\"]}/night | {PROPERTY[\"days_available_year\"]} days open/yr')
print(f'  Superhost: {\"Yes\" if PROPERTY[\"is_superhost\"] else \"No\"} | Instant Book: {\"On\" if PROPERTY[\"instant_bookable\"] else \"Off\"}')
"""

new_cells.append(md_cell('### 6.1 — Enter Your Property Details'))
new_cells.append(code_cell(INPUT_CELL))

# ── 6.2: ANALYSIS ENGINE ─────────────────────────────────────────────────────
ANALYSIS_CELL = """\
# ── 1. Build model input row ─────────────────────────────────────────────
row = X.median().copy()

neigh_rev_rank_lookup = df.groupby('neighbourhood_cleansed')['estimated_revenue_l365d'].median().rank(pct=True)
row['neighbourhood_rank']        = neigh_rev_rank_lookup.get(PROPERTY['neighbourhood'], 0.5)
row['price']                     = PROPERTY['nightly_price']
row['accommodates']              = PROPERTY['accommodates']
row['bedrooms']                  = PROPERTY['bedrooms']
row['beds']                      = PROPERTY['beds']
row['bathrooms']                 = PROPERTY['bathrooms']
row['minimum_nights']            = PROPERTY['minimum_nights']
row['availability_365']          = PROPERTY['days_available_year']
row['is_entire_home']            = PROPERTY['is_entire_home']
row['host_is_superhost']         = PROPERTY['is_superhost']
row['instant_bookable']          = PROPERTY['instant_bookable']
row['host_years_experience']     = PROPERTY['host_years_experience']
row['host_listings_count']       = PROPERTY['host_listings_count']
row['review_scores_rating']      = PROPERTY['review_scores_rating']
row['review_scores_cleanliness'] = PROPERTY['review_scores_cleanliness']
row['review_scores_location']    = PROPERTY['review_scores_location']
row['review_scores_value']       = PROPERTY['review_scores_value']
row['reviews_per_month']         = PROPERTY['reviews_per_month']
row['host_response_rate']        = PROPERTY['host_response_rate']
row['host_acceptance_rate']      = PROPERTY['host_acceptance_rate']
row['demand_score']              = 1 - (PROPERTY['days_available_year'] / 365)

resp_map = {'within an hour': 1.0, 'within a few hours': 0.75,
            'within a day': 0.4, 'a few days or more': 0.1}
row['host_engagement'] = (
    PROPERTY['host_response_rate'] * 0.4 +
    PROPERTY['host_acceptance_rate'] * 0.3 +
    PROPERTY['is_superhost'] * 0.3
)

amenity_keys = [
    'amen_hot_tub','amen_pool','amen_gym','amen_ev_charger','amen_sauna',
    'amen_fireplace','amen_dedicated_workspace','amen_netflix','amen_wifi',
    'amen_free_parking','amen_air_conditioning','amen_breakfast','amen_self_check-in',
    'amen_washer','amen_dryer','amen_dishwasher','amen_espresso_machine',
    'amen_piano','amen_baby_monitor','amen_elevator','amen_waterfront',
    'amen_garden','amen_balcony','amen_harbor_view',
]
total_am = 0
for k in amenity_keys:
    val = PROPERTY.get(k, 0)
    if k in row.index:
        row[k] = val
    total_am += val
row['total_amenities'] = total_am

# ── 2. Predict current revenue ────────────────────────────────────────────
current_rev = gb.predict([row])[0]

# ── 3. Individual lever simulations ──────────────────────────────────────
LEVERS = {
    'Enable Instant Booking':        {'instant_bookable': 1},
    'Achieve Superhost Status':      {'host_is_superhost': 1, 'host_engagement': min(row['host_engagement']+0.3, 1.0)},
    'Optimise Nightly Price':        {'price': opt_price},
    'Respond Within 1 Hour':         {'host_engagement': min(row['host_engagement']+0.15, 1.0)},
    'Open 300+ Days/Year':           {'availability_365': 300, 'demand_score': 1-(300/365)},
    'Set Minimum 2-Night Stay':      {'minimum_nights': 2},
    'Add Dedicated Workspace':       {'amen_dedicated_workspace': 1, 'total_amenities': total_am+1},
    'Add Self Check-in (Smart Lock)':{'amen_self_check-in': 1, 'total_amenities': total_am+1},
    'Add Free Parking':              {'amen_free_parking': 1, 'total_amenities': total_am+1},
    'Add Washer':                    {'amen_washer': 1, 'total_amenities': total_am+1},
    'Add Air Conditioning':          {'amen_air_conditioning': 1, 'total_amenities': total_am+1},
    'Add Balcony / Outdoor Space':   {'amen_balcony': 1, 'total_amenities': total_am+1},
    'Add Breakfast':                 {'amen_breakfast': 1, 'total_amenities': total_am+1},
    'Improve Cleanliness to 4.9':    {'review_scores_cleanliness': 4.9},
    'Improve Overall Rating to 4.9': {'review_scores_rating': 4.9},
}

lever_results = []
for name, changes in LEVERS.items():
    test = row.copy()
    already_done = all(abs(test.get(c, 0) - v) < 0.01 for c, v in changes.items() if c in test.index)
    if already_done:
        continue
    for c, v in changes.items():
        if c in test.index:
            test[c] = v
    pred = gb.predict([test])[0]
    uplift_abs = pred - current_rev
    uplift_pct = uplift_abs / current_rev * 100 if current_rev > 0 else 0
    lever_results.append({'lever': name, 'predicted_revenue': pred,
                          'uplift_abs': uplift_abs, 'uplift_pct': uplift_pct})

levers_ranked = pd.DataFrame(lever_results).sort_values('uplift_pct', ascending=False)
levers_ranked = levers_ranked[levers_ranked['uplift_pct'] > 0.5]

# ── 4. Full optimisation scenario ────────────────────────────────────────
full_row = row.copy()
for changes in LEVERS.values():
    for c, v in changes.items():
        if c in full_row.index:
            full_row[c] = v
full_row['price'] = opt_price
full_row['host_is_superhost'] = 1
full_row['instant_bookable']  = 1
full_row['availability_365']  = min(PROPERTY['days_available_year'] + 100, 330)
full_row['review_scores_rating']      = max(PROPERTY['review_scores_rating'], 4.85)
full_row['review_scores_cleanliness'] = max(PROPERTY['review_scores_cleanliness'], 4.85)
full_row['total_amenities'] = min(total_am + 5, 20)
full_rev = gb.predict([full_row])[0]

# ── 5. P&L function ───────────────────────────────────────────────────────
AIRBNB_FEE_RATE = 0.03

def compute_pl(revenue, prop):
    bookings = revenue / (prop['nightly_price'] * prop['avg_stay_length_nights'])
    mortgage  = prop['monthly_mortgage_or_rent'] * 12
    bills     = prop['monthly_bills'] * 12
    insurance = prop['monthly_insurance'] * 12
    cleaning  = bookings * prop['cleaning_cost_per_stay']
    consumab  = bookings * prop['consumables_per_stay']
    maint     = prop['annual_maintenance']
    airbnb_f  = revenue * AIRBNB_FEE_RATE
    total_costs = mortgage + bills + insurance + cleaning + consumab + maint + airbnb_f
    net_profit  = revenue - total_costs
    margin_pct  = (net_profit / total_costs * 100) if total_costs > 0 else 0
    return dict(gross_revenue=revenue, airbnb_fee=airbnb_f,
                mortgage_rent=mortgage, bills=bills, insurance=insurance,
                cleaning=cleaning, consumables=consumab, maintenance=maint,
                total_costs=total_costs, net_profit=net_profit,
                profit_margin_pct=margin_pct, bookings_per_year=bookings)

pl_curr = compute_pl(current_rev, PROPERTY)
pl_opt  = compute_pl(full_rev,    PROPERTY)

# ── 6. Property score ─────────────────────────────────────────────────────
def score_property(prop, neigh_lookup):
    s = {}
    price_err = abs(prop['nightly_price'] - opt_price) / opt_price
    s['Pricing']     = max(0, int(20 * (1 - price_err * 2)))
    am_cnt = sum(prop.get(k, 0) for k in amenity_keys)
    s['Amenities']   = min(20, int(am_cnt / 24 * 20))
    resp_sc = {'within an hour':1.0,'within a few hours':0.75,'within a day':0.4,'a few days or more':0.1}
    hq = (prop['host_response_rate']*6 + prop['host_acceptance_rate']*4 +
          prop['is_superhost']*6 + resp_sc.get(prop['host_response_time'],0.5)*4)
    s['Host Quality'] = min(20, int(hq))
    bs = (8 if prop['instant_bookable'] else 0) + (6 if prop['minimum_nights']<=3 else 0) + (6 if prop['days_available_year']>=200 else 0)
    s['Booking Setup'] = min(20, bs)
    rv = (min(prop['review_scores_rating']/5,1)*8 +
          min(prop['review_scores_cleanliness']/5,1)*6 +
          min(prop['number_of_reviews']/30,1)*6)
    s['Reviews']    = min(20, int(rv))
    lq = min(20, int(am_cnt/12*10) + (5 if prop['is_entire_home'] else 0) + (5 if prop['bedrooms']>=2 else 2))
    s['Listing']    = min(20, lq)
    nr = neigh_lookup.get(prop['neighbourhood'], 0.5)
    s['Location']   = min(20, int(nr*14) + (6 if prop['days_available_year']>=250 else 3))
    return s

score_dict  = score_property(PROPERTY, neigh_rev_rank_lookup)
total_score = sum(score_dict.values())
category    = ('Underperforming' if total_score<=40 else 'Average' if total_score<=70 else
               'Good' if total_score<=100 else 'Strong' if total_score<=120 else 'Excellent')

print('Analysis complete.')
print(f'  Score: {total_score}/140 — {category}')
print(f'  Current revenue:   £{current_rev:,.0f}/yr   |  Net profit: £{pl_curr["net_profit"]:,.0f}  ({pl_curr["profit_margin_pct"]:.1f}% of costs)')
print(f'  Optimised revenue: £{full_rev:,.0f}/yr  |  Net profit: £{pl_opt["net_profit"]:,.0f}  ({pl_opt["profit_margin_pct"]:.1f}% of costs)')
print(f'  Opportunities found: {len(levers_ranked)}')
"""

new_cells.append(md_cell('### 6.2 — Run Analysis'))
new_cells.append(code_cell(ANALYSIS_CELL))

# ── 6.3: VISUALISATIONS ──────────────────────────────────────────────────────
VIZ_CELL = """\
import os; os.makedirs('group_outputs', exist_ok=True)

# ─── FIGURE 1: Optimisation opportunities ────────────────────────────────
fig1, ax1 = plt.subplots(figsize=(14, max(5, len(levers_ranked)*0.6 + 1.5)))
fig1.suptitle(f'Ranked Optimisation Opportunities — {PROPERTY[\"property_type\"]} in {PROPERTY[\"neighbourhood\"]}',
              fontsize=13, fontweight='bold')

cmap = plt.cm.RdYlGn
nv = (levers_ranked['uplift_pct'] - levers_ranked['uplift_pct'].min()) / (levers_ranked['uplift_pct'].max() - levers_ranked['uplift_pct'].min() + 1e-9)
bclrs = [cmap(v * 0.8 + 0.1) for v in nv]

bars_l = ax1.barh(levers_ranked['lever'], levers_ranked['uplift_pct'], color=bclrs, edgecolor='white', linewidth=0.5)
ax1.set_xlabel('Predicted Annual Revenue Uplift (%)', fontsize=11)
ax1.axvline(0, color='black', linewidth=0.8)
ax1.invert_yaxis()
ax1.grid(axis='x', alpha=0.35)

for bar, (_, r) in zip(bars_l, levers_ranked.iterrows()):
    ax1.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height()/2,
             f'+{r["uplift_pct"]:.1f}%   £{r["uplift_abs"]:,.0f}/yr',
             va='center', fontsize=9.5, color='#1a1a1a')

plt.tight_layout()
plt.savefig('group_outputs/property_opportunities.png', dpi=150, bbox_inches='tight')
plt.show()

# ─── FIGURE 2: Full P&L waterfall ────────────────────────────────────────
pl_labels = ['Gross\\nRevenue','Airbnb\\nFee','Mortgage\\n/Rent','Bills','Insurance',
             'Cleaning','Consumables','Maintenance','NET\\nPROFIT']

def pl_vals(pl):
    return [pl['gross_revenue'], -pl['airbnb_fee'], -pl['mortgage_rent'],
            -pl['bills'], -pl['insurance'], -pl['cleaning'],
            -pl['consumables'], -pl['maintenance'], pl['net_profit']]

cv, ov = pl_vals(pl_curr), pl_vals(pl_opt)

bar_c = ['#2563EB','#EF4444','#F97316','#F97316','#F97316','#EAB308','#EAB308','#EAB308',
         '#16A34A' if pl_curr['net_profit']>=0 else '#DC2626']
bar_o = ['#2563EB','#EF4444','#F97316','#F97316','#F97316','#EAB308','#EAB308','#EAB308',
         '#16A34A' if pl_opt['net_profit']>=0 else '#DC2626']

x = np.arange(len(pl_labels))
w = 0.36
fig2, ax2 = plt.subplots(figsize=(16, 7))
fig2.suptitle('Full Annual P&L — Current vs Fully Optimised', fontsize=13, fontweight='bold')

b1 = ax2.bar(x - w/2, cv, w, color=bar_c, alpha=0.92, edgecolor='white', label='Current')
b2 = ax2.bar(x + w/2, ov, w, color=bar_o, alpha=0.60, edgecolor='white', label='Optimised', linestyle='--')

for bar, v in zip(b1, cv):
    off = 200 if v>=0 else -700
    ax2.text(bar.get_x()+bar.get_width()/2, bar.get_height()+off, f'£{abs(v):,.0f}',
             ha='center', fontsize=8, color='#111')
for bar, v in zip(b2, ov):
    off = 200 if v>=0 else -700
    ax2.text(bar.get_x()+bar.get_width()/2, bar.get_height()+off, f'£{abs(v):,.0f}',
             ha='center', fontsize=8, color='#333', style='italic')

ax2.axhline(0, color='black', linewidth=0.8)
ax2.set_xticks(x); ax2.set_xticklabels(pl_labels, fontsize=10)
ax2.set_ylabel('£ per year', fontsize=11)
ax2.grid(axis='y', alpha=0.3)
ax2.legend(fontsize=11)
plt.tight_layout()
plt.savefig('group_outputs/property_pl.png', dpi=150, bbox_inches='tight')
plt.show()

# ─── FIGURE 3: Net Profit (£ + %) + Radar scorecard ─────────────────────
fig3 = plt.figure(figsize=(20, 7))
fig3.suptitle(f'Profit Summary & Scorecard — {PROPERTY["property_type"]} | {PROPERTY["neighbourhood"]} | {total_score}/140 ({category})',
              fontsize=12, fontweight='bold')

# Left: Net profit £
ax_np = fig3.add_subplot(1,3,1)
nps   = [pl_curr['net_profit'], pl_opt['net_profit']]
nc    = ['#2563EB' if v>=0 else '#EF4444' for v in nps]
brs   = ax_np.bar(['Current','Optimised'], nps, color=nc, width=0.45, edgecolor='white')
ax_np.axhline(0, color='black', linewidth=0.8)
for bar, val in zip(brs, nps):
    off = max(abs(val)*0.04, 150) * (1 if val>=0 else -1)
    ax_np.text(bar.get_x()+bar.get_width()/2, bar.get_height()+off,
               f'£{val:,.0f}', ha='center', fontsize=13, fontweight='bold', color='#111')
ax_np.set_title('Net Annual Profit (£)', fontsize=12)
ax_np.set_ylabel('£ / year')
ax_np.grid(axis='y', alpha=0.3)

# Middle: Net profit % of total costs
ax_mg = fig3.add_subplot(1,3,2)
mgs   = [pl_curr['profit_margin_pct'], pl_opt['profit_margin_pct']]
mc    = ['#16A34A' if m>=0 else '#EF4444' for m in mgs]
brs2  = ax_mg.bar(['Current','Optimised'], mgs, color=mc, width=0.45, edgecolor='white')
ax_mg.axhline(0, color='black', linewidth=0.8)
for bar, val in zip(brs2, mgs):
    off = max(abs(val)*0.04, 1) * (1 if val>=0 else -1)
    ax_mg.text(bar.get_x()+bar.get_width()/2, bar.get_height()+off,
               f'{val:.1f}%', ha='center', fontsize=13, fontweight='bold', color='#111')
for ref, lbl, clr in [(10,'Break-even zone','#F97316'),(30,'Healthy (30%)','#16A34A'),(60,'Excellent (60%)','#065F46')]:
    ax_mg.axhline(ref, color=clr, linewidth=1.2, linestyle='--', alpha=0.7)
    ax_mg.text(1.52, ref+0.8, lbl, fontsize=8, color=clr)
ax_mg.set_title('Net Profit as % of Total Costs', fontsize=12)
ax_mg.set_ylabel('Profit margin on costs (%)')
ax_mg.grid(axis='y', alpha=0.3)

# Right: Radar scorecard
dims  = list(score_dict.keys())
s_cur = list(score_dict.values())
s_opt = [min(20, v + (4 if d in ['Booking Setup','Host Quality','Pricing'] else 2)) for d, v in score_dict.items()]

N_r = len(dims)
angles = np.linspace(0, 2*np.pi, N_r, endpoint=False).tolist() + [0]
s_cur_p = s_cur + s_cur[:1]
s_opt_p = s_opt + s_opt[:1]

ax_r = fig3.add_subplot(1,3,3, polar=True)
ax_r.plot(angles, s_cur_p, 'o-', color='#EF4444', linewidth=2, label='Current')
ax_r.fill(angles, s_cur_p, alpha=0.12, color='#EF4444')
ax_r.plot(angles, s_opt_p, 'o-', color='#2563EB', linewidth=2.5, label='Optimised')
ax_r.fill(angles, s_opt_p, alpha=0.12, color='#2563EB')
ax_r.set_xticks(angles[:-1])
ax_r.set_xticklabels(dims, fontsize=9)
ax_r.set_ylim(0,20)
ax_r.set_yticks([5,10,15,20])
ax_r.set_yticklabels(['5','10','15','20'], fontsize=7, color='grey')
ax_r.set_title(f'Scorecard: {total_score}/140\\n{category}', fontsize=11, fontweight='bold', pad=15)
ax_r.legend(loc='upper right', bbox_to_anchor=(1.35, 1.1), fontsize=9)

plt.tight_layout()
plt.savefig('group_outputs/property_scorecard.png', dpi=150, bbox_inches='tight')
plt.show()

# ─── PRINTED SUMMARY ─────────────────────────────────────────────────────
D = '─'*62
print(f'\\n{"="*62}')
print(f'  PROPERTY ANALYSIS REPORT')
print(f'  {PROPERTY["property_type"]}  |  {PROPERTY["bedrooms"]}BD/{PROPERTY["bathrooms"]}BA  |  {PROPERTY["neighbourhood"]}')
print(f'{"="*62}')

print(f'\\n  PROPERTY SCORE: {total_score}/140 — {category}')
for dim, sc in score_dict.items():
    filled = chr(9608)*sc + chr(9617)*(20-sc)
    print(f'  {dim:<16} {filled}  {sc}/20')

print(f'\\n{D}')
print(f'  TOP OPTIMISATION OPPORTUNITIES')
print(f'{D}')
for i, (_, r) in enumerate(levers_ranked.head(10).iterrows(), 1):
    print(f'  {i:>2}. {r["lever"]:<40} +{r["uplift_pct"]:>5.1f}%  £{r["uplift_abs"]:>7,.0f}/yr')

print(f'\\n{D}')
print(f'  P&L SUMMARY                          Current       Optimised')
print(f'  {D}')
rows_pl = [
    ('Gross Revenue',        pl_curr['gross_revenue'],    pl_opt['gross_revenue']),
    ('  Airbnb Host Fee 3%', -pl_curr['airbnb_fee'],      -pl_opt['airbnb_fee']),
    ('  Mortgage / Rent',    -pl_curr['mortgage_rent'],   -pl_opt['mortgage_rent']),
    ('  Bills & Utilities',  -pl_curr['bills'],           -pl_opt['bills']),
    ('  Insurance',          -pl_curr['insurance'],       -pl_opt['insurance']),
    ('  Cleaning Costs',     -pl_curr['cleaning'],        -pl_opt['cleaning']),
    ('  Consumables',        -pl_curr['consumables'],     -pl_opt['consumables']),
    ('  Maintenance',        -pl_curr['maintenance'],     -pl_opt['maintenance']),
    ('TOTAL COSTS',          -pl_curr['total_costs'],     -pl_opt['total_costs']),
]
for lbl, cv2, ov2 in rows_pl:
    print(f'  {lbl:<32}  £{cv2:>9,.0f}      £{ov2:>9,.0f}')

print(f'  {"─"*58}')
print(f'  {"NET PROFIT":<32}  £{pl_curr["net_profit"]:>9,.0f}      £{pl_opt["net_profit"]:>9,.0f}')
print(f'  {"Profit as % of costs":<32}   {pl_curr["profit_margin_pct"]:>8.1f}%       {pl_opt["profit_margin_pct"]:>8.1f}%')
print(f'  {"Est. Bookings/year":<32}   {pl_curr["bookings_per_year"]:>9.0f}        {pl_opt["bookings_per_year"]:>9.0f}')

uplift_pct_np = ((pl_opt["net_profit"]-pl_curr["net_profit"])/abs(pl_curr["net_profit"])*100) if pl_curr["net_profit"] != 0 else 0
print(f'\\n  Net profit uplift from full optimisation: +{uplift_pct_np:.0f}%')
if PROPERTY['initial_setup_cost'] > 0 and pl_curr['net_profit'] > 0:
    pb = PROPERTY['initial_setup_cost'] / pl_curr['net_profit'] * 365
    print(f'  Setup cost payback: {pb:.0f} days ({pb/30:.1f} months)')
print(f'{"="*62}')
"""

new_cells.append(md_cell('### 6.3 — Visualise Results'))
new_cells.append(code_cell(VIZ_CELL))

# ── Summary markdown ─────────────────────────────────────────────────────────
new_cells.append(md_cell(
    '---\n'
    '## Summary of Key Takeaways\n\n'
    '| Lever | Typical Uplift | Effort |\n'
    '|-------|---------------|--------|\n'
    '| Enable Instant Booking | +15–25% | Zero |\n'
    '| Achieve Superhost status | +30–50% | Medium |\n'
    '| Optimal pricing (model-driven) | +10–20% | Low |\n'
    '| Professional photography | +10–15% bookings | Low |\n'
    '| Add dedicated workspace | +15–25% | Low cost |\n'
    '| Dynamic pricing (events) | +20–40% peak | Ongoing |\n'
    '| **Full optimisation (all levers)** | **+80–150%** | High |\n\n'
    '> **Best neighbourhoods:** Central, Clifton, Clifton Down, Hotwells & Harbourside  \n'
    '> **Best property type for ROI:** Entire 2–3 bed home in central Bristol  \n'
    '> **Best predictive model:** Gradient Boosting (R² ≈ 0.72+)'
))

nb['cells'] = new_cells
with open('Airbnb_Profit_Optimiser.ipynb', 'w') as f:
    json.dump(nb, f, indent=1)

print(f'Notebook patched. Total cells: {len(new_cells)}')
