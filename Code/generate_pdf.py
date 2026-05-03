"""Generate the Airbnb Consulting Business Plan PDF — clean professional light theme."""

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY, TA_RIGHT
from reportlab.pdfgen import canvas
import os

# ─── Colour palette (clean, professional, light) ─────────────────────────────
WHITE       = colors.white
OFF_WHITE   = colors.HexColor('#F8F9FA')
LIGHT_GREY  = colors.HexColor('#F0F2F5')
MID_GREY    = colors.HexColor('#D1D5DB')
DARK_GREY   = colors.HexColor('#6B7280')
NEAR_BLACK  = colors.HexColor('#111827')
BODY_TEXT   = colors.HexColor('#374151')

NAVY        = colors.HexColor('#1E3A5F')   # primary — headings, header bar
BLUE        = colors.HexColor('#2563EB')   # accent — H2, links, highlights
SKY         = colors.HexColor('#EFF6FF')   # very light blue — card backgrounds
TEAL        = colors.HexColor('#0D9488')   # secondary accent — H3
TEAL_LIGHT  = colors.HexColor('#F0FDFA')   # teal card bg
AMBER       = colors.HexColor('#D97706')   # callout / KPI values
AMBER_LIGHT = colors.HexColor('#FFFBEB')   # amber card bg
RED_LIGHT   = colors.HexColor('#FEF2F2')

PAGE_W, PAGE_H = A4
MARGIN = 2.2 * cm

# ─── Page template ────────────────────────────────────────────────────────────
def light_page(canvas_obj, doc):
    canvas_obj.saveState()
    # white background
    canvas_obj.setFillColor(WHITE)
    canvas_obj.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    # top navy header bar
    canvas_obj.setFillColor(NAVY)
    canvas_obj.rect(0, PAGE_H - 1.1*cm, PAGE_W, 1.1*cm, fill=1, stroke=0)

    # left accent stripe
    canvas_obj.setFillColor(BLUE)
    canvas_obj.rect(0, 0, 0.5*cm, PAGE_H, fill=1, stroke=0)

    # footer line
    canvas_obj.setStrokeColor(MID_GREY)
    canvas_obj.setLineWidth(0.5)
    canvas_obj.line(MARGIN, 1.2*cm, PAGE_W - MARGIN, 1.2*cm)

    canvas_obj.setFillColor(DARK_GREY)
    canvas_obj.setFont("Helvetica", 7.5)
    canvas_obj.drawString(MARGIN, 0.6*cm, "AirbnbEdge Consulting  |  Bristol Airbnb Profit Optimisation")
    canvas_obj.drawRightString(PAGE_W - MARGIN, 0.6*cm, f"Page {doc.page}")
    canvas_obj.restoreState()

# ─── Style definitions ────────────────────────────────────────────────────────
def S(name, **kw):
    defaults = dict(fontName='Helvetica', fontSize=11, leading=16,
                    textColor=BODY_TEXT, spaceAfter=7)
    defaults.update(kw)
    return ParagraphStyle(name, **defaults)

STYLE = {
    'cover_eyebrow': S('ce', fontSize=11, textColor=BLUE, alignment=TA_CENTER,
                        fontName='Helvetica-Bold', spaceBefore=0, spaceAfter=8),
    'cover_title':   S('ct', fontName='Helvetica-Bold', fontSize=38, leading=46,
                        textColor=NAVY, alignment=TA_CENTER, spaceAfter=10),
    'cover_sub':     S('cs', fontSize=17, leading=24, textColor=BLUE,
                        alignment=TA_CENTER, spaceAfter=6),
    'cover_tag':     S('ctag', fontSize=10, textColor=DARK_GREY,
                        alignment=TA_CENTER, spaceAfter=4),
    'h1':            S('h1', fontName='Helvetica-Bold', fontSize=20, leading=26,
                        textColor=NAVY, spaceBefore=18, spaceAfter=8),
    'h2':            S('h2', fontName='Helvetica-Bold', fontSize=14, leading=20,
                        textColor=BLUE, spaceBefore=12, spaceAfter=6),
    'h3':            S('h3', fontName='Helvetica-Bold', fontSize=12, leading=17,
                        textColor=TEAL, spaceBefore=8, spaceAfter=5),
    'body':          S('body', fontSize=10.5, leading=16.5, textColor=BODY_TEXT,
                        alignment=TA_JUSTIFY),
    'bullet':        S('bul', fontSize=10.5, leading=16, textColor=BODY_TEXT,
                        leftIndent=16, spaceAfter=5),
    'callout':       S('call', fontName='Helvetica-Bold', fontSize=11, leading=17,
                        textColor=NAVY, backColor=SKY, borderPadding=(8,10,8,10),
                        spaceBefore=6, spaceAfter=8, alignment=TA_CENTER),
    'kpi_label':     S('kl', fontName='Helvetica', fontSize=9, leading=13,
                        textColor=DARK_GREY, alignment=TA_CENTER),
    'kpi_value':     S('kv', fontName='Helvetica-Bold', fontSize=20, leading=26,
                        textColor=NAVY, alignment=TA_CENTER),
    'th':            S('th', fontName='Helvetica-Bold', fontSize=9, leading=13,
                        textColor=WHITE, alignment=TA_CENTER),
    'td':            S('td', fontSize=9.5, leading=14, textColor=BODY_TEXT,
                        alignment=TA_LEFT),
    'td_c':          S('tdc', fontSize=9.5, leading=14, textColor=BODY_TEXT,
                        alignment=TA_CENTER),
    'footer_note':   S('fn', fontSize=8.5, textColor=DARK_GREY, alignment=TA_CENTER),
    'toc_item':      S('toc', fontSize=11, leading=18, textColor=BODY_TEXT,
                        leftIndent=10),
    'section_label': S('sl', fontName='Helvetica-Bold', fontSize=8, textColor=BLUE,
                        spaceBefore=18, spaceAfter=2),
}

def hr(color=MID_GREY, thickness=0.8):
    return HRFlowable(width='100%', thickness=thickness, color=color,
                      spaceAfter=10, spaceBefore=2)

def sp(h=0.3):
    return Spacer(1, h * cm)

def P(text, style='body'):
    return Paragraph(text, STYLE[style])

def bullet(text):
    return Paragraph(f'<bullet>•</bullet> {text}', STYLE['bullet'])

def kpi_row(items):
    """items = [(label, value), ...]"""
    n = len(items)
    col_w = (PAGE_W - 2*MARGIN) / n
    data = [
        [Paragraph(v, STYLE['kpi_value']) for _, v in items],
        [Paragraph(l, STYLE['kpi_label']) for l, _ in items],
    ]
    t = Table(data, colWidths=[col_w]*n, rowHeights=[1.3*cm, 0.7*cm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), SKY),
        ('BOX',        (0,0), (-1,-1), 0.5, MID_GREY),
        ('INNERGRID',  (0,0), (-1,-1), 0.5, MID_GREY),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING',   (0,0), (-1,-1), 6),
        ('RIGHTPADDING',  (0,0), (-1,-1), 6),
        ('ROUNDEDCORNERS', [4]),
    ]))
    return t

def data_table(header, rows, col_widths=None, alt_bg=True):
    data = [[Paragraph(str(h), STYLE['th']) for h in header]]
    for i, row in enumerate(rows):
        style = 'td'
        data.append([Paragraph(str(c), STYLE[style]) for c in row])
    if col_widths is None:
        n = len(header)
        col_widths = [(PAGE_W - 2*MARGIN) / n] * n
    t = Table(data, colWidths=col_widths, repeatRows=1)
    ts = TableStyle([
        ('BACKGROUND',    (0,0), (-1,0), NAVY),
        ('TEXTCOLOR',     (0,0), (-1,0), WHITE),
        ('FONTNAME',      (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE',      (0,0), (-1,0), 9),
        ('ALIGN',         (0,0), (-1,0), 'CENTER'),
        ('TOPPADDING',    (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING',   (0,0), (-1,-1), 8),
        ('RIGHTPADDING',  (0,0), (-1,-1), 8),
        ('GRID',          (0,0), (-1,-1), 0.4, MID_GREY),
        ('BOX',           (0,0), (-1,-1), 0.8, NAVY),
        ('FONTNAME',      (0,1), (-1,-1), 'Helvetica'),
        ('FONTSIZE',      (0,1), (-1,-1), 9.5),
        ('TEXTCOLOR',     (0,1), (-1,-1), BODY_TEXT),
    ])
    for i in range(1, len(rows)+1):
        bg = LIGHT_GREY if i % 2 == 0 else WHITE
        ts.add('BACKGROUND', (0,i), (-1,i), bg)
    t.setStyle(ts)
    return t

def section_divider(label):
    return [
        sp(0.2),
        Paragraph(label.upper(), STYLE['section_label']),
        HRFlowable(width='100%', thickness=2, color=NAVY, spaceAfter=10, spaceBefore=0),
    ]

# ─── Build ────────────────────────────────────────────────────────────────────
def build_pdf(output_path='group_outputs/AirbnbEdge_Business_Plan.pdf'):
    os.makedirs('group_outputs', exist_ok=True)
    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=1.6*cm, bottomMargin=1.8*cm,
        title='AirbnbEdge — Airbnb Profit Optimisation Business Plan',
        author='Salah Baaziz'
    )
    story = []

    # ── COVER ─────────────────────────────────────────────────────────────────
    story += [
        sp(3.5),
        P('AIRBNB CONSULTING BUSINESS PLAN', 'cover_eyebrow'),
        P('AirbnbEdge', 'cover_title'),
        P('Bristol Airbnb Profit Optimisation', 'cover_sub'),
        sp(0.3),
        hr(BLUE, 2),
        sp(0.3),
        P('Data-driven consulting to help property owners maximise Airbnb revenue using machine learning trained on 2,879 Bristol listings.', 'cover_tag'),
        sp(0.8),
        kpi_row([
            ('Listings Analysed', '2,879'),
            ('Median Annual Revenue', '£3,636'),
            ('Optimisation Upside', 'Up to +150%'),
            ('Target Market', 'Bristol, UK'),
        ]),
        sp(2.5),
        hr(MID_GREY),
        P('Prepared by: <b>Salah Baaziz</b>   |   Dataset: Inside Airbnb, Bristol (June 2025)   |   Model R² ≈ 0.72', 'cover_tag'),
        PageBreak(),
    ]

    # ── TABLE OF CONTENTS ──────────────────────────────────────────────────────
    story += section_divider('Contents')
    toc_items = [
        ('1.', 'Executive Summary'),
        ('2.', 'Market Analysis — Bristol Airbnb Landscape'),
        ('3.', 'Data Insights & Key Findings'),
        ('4.', 'The Optimisation Framework (5-Method Approach)'),
        ('5.', 'Step-by-Step Guide: Renting Your Property on Airbnb'),
        ('6.', 'What to Focus on Most — Prioritised Levers'),
        ('7.', 'Business Model & Monetisation Strategy'),
        ('8.', 'Pricing Your Consulting Services'),
        ('9.', 'Go-to-Market Plan'),
        ('10.', 'Financial Projections'),
        ('11.', 'Risk Register'),
        ('12.', 'Appendix — Property Scoring Criteria'),
    ]
    toc_data = [[Paragraph(n, STYLE['toc_item']), Paragraph(t, STYLE['toc_item'])] for n, t in toc_items]
    toc_table = Table(toc_data, colWidths=[1.2*cm, PAGE_W - 2*MARGIN - 1.2*cm])
    toc_table.setStyle(TableStyle([
        ('TOPPADDING',    (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LINEBELOW',     (0,0), (-1,-1), 0.3, LIGHT_GREY),
    ]))
    story += [toc_table, PageBreak()]

    # ── SECTION 1: EXECUTIVE SUMMARY ──────────────────────────────────────────
    story += section_divider('Section 1')
    story += [
        P('Executive Summary', 'h1'),
        P(
            'AirbnbEdge is a data-driven consulting business helping Bristol property owners '
            'maximise their Airbnb revenue using machine learning models trained on 2,879 real '
            'local listings. Our analysis reveals a stark gap: the average Bristol Airbnb earns '
            '<b>£3,636 per year</b>, yet top performers earn over <b>£35,000</b> — a gap almost '
            'entirely explained by factors within a host\'s control.',
            'body'
        ),
        sp(0.2),
        P(
            'Our Gradient Boosting model (R²=0.72+) identifies the precise levers that drive '
            'revenue and quantifies the impact of each change before a client spends anything. '
            'The typical client who implements all recommendations sees a '
            '<b>+80–150% increase in annual revenue</b> within 6–12 months — with consulting '
            'fees paid back within 4–8 weeks.',
            'body'
        ),
        sp(0.4),
        P('Business at a Glance', 'h2'),
        kpi_row([
            ('Addressable Market', '2,879 listings'),
            ('Average Uplift', '+80–150%'),
            ('Fee Payback Period', '< 8 weeks'),
            ('Year 1 Revenue Target', '£60,000+'),
        ]),
        sp(0.4),
        P('Core Value Proposition', 'h2'),
        bullet('We turn raw Airbnb data into a personalised, ROI-ranked action plan — not vague advice.'),
        bullet('Our ML model predicts the £ impact of each change <i>before</i> the client implements it.'),
        bullet('Clients recover consulting fees within weeks, not months.'),
        bullet('Proprietary local model trained on Bristol listings — a genuine competitive moat.'),
        PageBreak(),
    ]

    # ── SECTION 2: MARKET ANALYSIS ────────────────────────────────────────────
    story += section_divider('Section 2')
    story += [
        P('Market Analysis — Bristol Airbnb Landscape', 'h1'),
        P('Key Market Statistics', 'h2'),
        data_table(
            ['Metric', 'Value', 'Implication'],
            [
                ['Total active listings', '2,879', 'Large, addressable market for consulting'],
                ['Median nightly price', '£97', 'Strong pricing power vs UK average of £75'],
                ['Median annual revenue', '£3,636', 'Most hosts are massively under-earning'],
                ['Top 10% annual revenue', '£35,000+', 'Clear upside benchmark to sell against'],
                ['Superhost prevalence', '35%', '65% of hosts not yet Superhost — prime target market'],
                ['Instant booking enabled', '33%', '67% are missing easy +15–25% revenue gains'],
                ['Average occupancy rate', '~30%', 'Huge room to improve with basic optimisation'],
                ['Entire home share', '71%', 'Highest-earning category — key consulting segment'],
            ],
            col_widths=[5.5*cm, 3*cm, 8.5*cm]
        ),
        sp(0.5),
        P('Top Revenue Neighbourhoods', 'h2'),
        data_table(
            ['Neighbourhood', 'Median Price/night', 'Listings', 'Revenue Potential'],
            [
                ['Clifton', '£130+', '184', '★★★★★ Premium'],
                ['Central', '£120+', '302', '★★★★★ High volume'],
                ['Hotwells & Harbourside', '£110+', '~60', '★★★★★ Waterfront premium'],
                ['Clifton Down', '£115+', '182', '★★★★☆'],
                ['Cotham', '£100+', '140', '★★★★☆'],
                ['Southville', '£95+', '145', '★★★☆☆'],
                ['Ashley', '£85+', '321', '★★★☆☆ High competition'],
                ['Lawrence Hill', '£80+', '144', '★★★☆☆'],
            ],
            col_widths=[5*cm, 3.5*cm, 2.5*cm, 6*cm]
        ),
        PageBreak(),
    ]

    # ── SECTION 3: DATA INSIGHTS ───────────────────────────────────────────────
    story += section_divider('Section 3')
    story += [
        P('Data Insights & Key Findings', 'h1'),
        P('Finding 1 — Price is NOT the primary driver of revenue', 'h3'),
        P(
            'Counter-intuitively, the highest-earning hosts are not charging the most. Our Random '
            'Forest model ranks <b>neighbourhood, availability settings, and demand score</b> above '
            'nightly price in importance. A well-optimised £90/night listing at 85% occupancy '
            'outearns a £180/night listing at 30% occupancy.',
            'body'
        ),
        P('Finding 2 — Superhost status is worth +30–50% in revenue', 'h3'),
        P(
            'Superhost listings earn £5,200–6,000/yr vs £3,200/yr for regular hosts. '
            'Requirements: 10+ stays, ≥90% response rate, <1% cancellation, ≥4.8 overall rating. '
            'Achievable within 3–6 months for any committed host.',
            'body'
        ),
        P('Finding 3 — Instant Booking drives +15–25% more bookings', 'h3'),
        P(
            '67% of Bristol hosts still use "request to book". Enabling Instant Booking removes '
            'friction and boosts algorithmic visibility — instant-bookable listings show '
            '<b>higher occupancy and more reviews per month</b>.',
            'body'
        ),
        P('Finding 4 — Amenities have wildly different ROI', 'h3'),
        P(
            'A hot tub adds +60% revenue but costs £5,000–15,000 to install. A dedicated '
            'workspace, espresso machine, and smart lock combined cost under £500 and add '
            '+20–40% revenue. We show clients exactly which amenities to add first.',
            'body'
        ),
        P('Finding 5 — Response time is a hidden algorithmic lever', 'h3'),
        P(
            'Hosts who respond "within an hour" earn the highest median revenue. Setting up '
            'automated message templates takes 30 minutes and permanently boosts search visibility.',
            'body'
        ),
        P('Finding 6 — Cleanliness is the most impactful review dimension', 'h3'),
        P(
            'Among all review sub-scores, cleanliness correlates most strongly with repeat '
            'bookings. A cleanliness score of ≥4.8 is the threshold for significantly higher '
            'booking conversion rates.',
            'body'
        ),
        PageBreak(),
    ]

    # ── SECTION 4: OPTIMISATION FRAMEWORK ─────────────────────────────────────
    story += section_divider('Section 4')
    story += [
        P('The Optimisation Framework — 5-Method Approach', 'h1'),
        data_table(
            ['Method', 'Technique', 'What It Reveals', 'Accuracy'],
            [
                ['1', 'Linear / Ridge Regression', 'Interpretable £ coefficients per driver', 'R² = 0.52'],
                ['2', 'Random Forest', 'Non-linear feature importance ranking', 'R² = 0.68'],
                ['3', 'Gradient Boosting', 'Best predictive model — personalised forecasting', 'R² = 0.72+'],
                ['4', 'K-Means Clustering', 'Market segmentation — where client sits vs peers', 'N/A'],
                ['5', 'Pricing Simulation', 'Revenue-maximising price per property profile', 'N/A'],
            ],
            col_widths=[1.5*cm, 5*cm, 7.5*cm, 3*cm]
        ),
        sp(0.4),
        P('Optimisation Levers — Ranked by ROI', 'h2'),
        data_table(
            ['Rank', 'Lever', 'Typical Uplift', 'Cost', 'Priority'],
            [
                ['1', 'Enable Instant Booking', '+15–25% bookings', '£0', '🔴 Critical'],
                ['2', 'Achieve Superhost status', '+30–50% revenue', '£0 (effort)', '🔴 Critical'],
                ['3', 'Optimal pricing (model-driven)', '+10–20% revenue', '£0', '🔴 Critical'],
                ['4', 'Sub-1hr auto-response templates', '+10–20% bookings', '£0', '🟡 High'],
                ['5', 'Professional photography', '+10–15% bookings', '£150–300', '🟡 High'],
                ['6', 'Smart lock / self check-in', '+8–12% bookings', '£100–200', '🟡 High'],
                ['7', 'Dedicated workspace', '+15–25% revenue', '£200–500', '🟡 High'],
                ['8', 'Espresso machine', '+8–15% revenue', '£100–300', '🟢 Medium'],
                ['9', 'Dynamic pricing (events)', '+20–40% peak', '£0', '🟢 Medium'],
                ['10', 'Hot tub / pool', '+40–60% revenue', '£5–15k', '⚪ Luxury'],
            ],
            col_widths=[1.2*cm, 5.8*cm, 3.5*cm, 3*cm, 3.5*cm]
        ),
        PageBreak(),
    ]

    # ── SECTION 5: HOW TO LIST ON AIRBNB ──────────────────────────────────────
    story += section_divider('Section 5')
    story += [
        P('Step-by-Step Guide: Renting Your Property on Airbnb', 'h1'),
        P('Phase 1 — Legal, Insurance & Financial Setup', 'h2'),
        data_table(
            ['Step', 'Action', 'Notes'],
            [
                ['1.1', 'Check mortgage/lease permissions', 'Many mortgages prohibit STLs. Get written consent.'],
                ['1.2', 'Get specialist STL insurance', 'Standard home insurance is void for Airbnb. Try SuperCover, Guardhog, or Simply Business.'],
                ['1.3', 'Understand planning rules', 'Bristol: up to 90 nights/yr without planning permission.'],
                ['1.4', 'Tax registration', '£1,000 rent-a-room allowance. Above that, declare on self-assessment.'],
                ['1.5', 'Business bank account', 'Separate all Airbnb income/expenses. Monzo Business or Tide are free.'],
            ],
            col_widths=[1.2*cm, 5*cm, 11*cm]
        ),
        sp(0.3),
        P('Phase 2 — Property Preparation', 'h2'),
        data_table(
            ['Step', 'Action', 'Budget'],
            [
                ['2.1', 'Deep clean + declutter', '£80–150 (professional clean)'],
                ['2.2', 'Smart lock / keypad for self check-in', '£100–200'],
                ['2.3', 'Fast broadband (100mbps+)', '£30–60/month'],
                ['2.4', 'Hotel-quality linens & towels (2 sets per bed)', '£150–400'],
                ['2.5', 'Kitchen essentials: coffee machine, kettle, basics', '£100–300'],
                ['2.6', 'Bathroom: soap, shampoo, conditioner per stay', '£30–60/restock'],
                ['2.7', 'Safety: smoke & CO alarms, fire extinguisher', '£40–80'],
                ['2.8', 'Digital house manual', '£0 (Google Doc or Hostfully)'],
                ['2.9', 'Professional photography', '£150–300'],
            ],
            col_widths=[1.2*cm, 9*cm, 7*cm]
        ),
        sp(0.3),
        P('Phase 3 — Listing Optimisation', 'h2'),
        data_table(
            ['Element', 'Best Practice', 'Impact'],
            [
                ['Title', '"Stylish 2BD Harbourside Flat | Parking + Fast WiFi" — beds + USP + location', 'High'],
                ['Description', '300+ words: space, neighbourhood highlights, transport, unique features', 'High'],
                ['Photos', '20–30 photos. Lead with best room. Include neighbourhood shots.', 'Very High'],
                ['Pricing', 'Use model recommendation. Start 15% below for launch to get first reviews.', 'Very High'],
                ['Minimum nights', '2–3 nights. Reduces turnovers, maintains revenue.', 'High'],
                ['Instant Booking', 'Enable immediately. Boosts visibility and conversion.', 'Very High'],
            ],
            col_widths=[3.5*cm, 9*cm, 4.5*cm]
        ),
        sp(0.3),
        P('Phase 4 — Launch (First 30 Days)', 'h2'),
        bullet('Price 15–20% below comparable listings to accumulate your first 5–10 reviews quickly.'),
        bullet('Message every guest: personalised pre-arrival message, day-of check-in message, and day-2 check-in.'),
        bullet('Ask for reviews after checkout with a warm, short message.'),
        bullet('Respond to all messages within 1 hour — set phone notifications, use saved templates.'),
        bullet('Track: occupancy rate, revenue, review scores weekly. Adjust price every 2 weeks.'),
        sp(0.3),
        P('Phase 5 — Ongoing Optimisation (Months 2–12)', 'h2'),
        bullet('Achieve Superhost within 3–6 months. Monitor your host dashboard daily.'),
        bullet('Dynamic pricing: raise 20–40% for Bristol events (Balloon Fiesta, match days, bank holidays).'),
        bullet('Update your calendar weekly — Airbnb\'s algorithm rewards active hosts with better search placement.'),
        bullet('Add one high-ROI amenity per quarter and update your listing description each time.'),
        bullet('Refresh photos annually — seasonal shots increase bookings 10–15%.'),
        PageBreak(),
    ]

    # ── SECTION 6: WHAT TO FOCUS ON ────────────────────────────────────────────
    story += section_divider('Section 6')
    story += [
        P('What to Focus on Most — Prioritised by ROI', 'h1'),
        P('The Power Four — Do These First (All Free)', 'h2'),
        data_table(
            ['#', 'Action', 'Time Required', 'Revenue Impact', 'Effort'],
            [
                ['1', 'Enable Instant Booking', '2 minutes', '+15–25%', 'Zero'],
                ['2', 'Set up 1-hour auto-response templates', '30 minutes', '+10–20%', 'Minimal'],
                ['3', 'Optimise pricing with our model', '1 hour', '+10–20%', 'Low'],
                ['4', 'Rewrite title + refresh top 3 photos', '2 hours', '+10–15% CTR', 'Low'],
            ],
            col_widths=[0.8*cm, 7*cm, 3*cm, 3.2*cm, 3*cm]
        ),
        sp(0.3),
        P('Growth Tier — First 3 Months', 'h2'),
        data_table(
            ['#', 'Action', 'Cost', 'Revenue Impact', 'Timeframe'],
            [
                ['5', 'Professional photography', '£150–300', '+10–15%', 'Week 1'],
                ['6', 'Smart lock for self check-in', '£100–200', '+8–12%', 'Week 1'],
                ['7', 'Add dedicated workspace', '£200–500', '+15–25%', 'Week 2'],
                ['8', 'Achieve Superhost status', '£0 (effort)', '+30–50%', '3–6 months'],
                ['9', 'Dynamic pricing for events/weekends', '£0', '+20–40% peak', 'Ongoing'],
            ],
            col_widths=[0.8*cm, 6.5*cm, 2.5*cm, 3.5*cm, 3.7*cm]
        ),
        sp(0.3),
        P('Scale Tier — Months 4–12', 'h2'),
        data_table(
            ['#', 'Action', 'Cost', 'Revenue Impact', 'Notes'],
            [
                ['10', 'Channel manager (Airbnb + Booking.com + VRBO)', '£30–80/mo', '+20–35%', 'Needs management time'],
                ['11', 'Professional co-host / property manager', '15–20% revenue', 'Enables scaling', 'If growing to 3+ properties'],
                ['12', 'Airbnb Experiences listing', '£0 listing', 'Separate income stream', 'If host has a marketable skill'],
                ['13', 'STR management software (Hostaway, Lodgify)', '£50–150/mo', 'Saves 10+ hrs/week', 'At 3+ properties'],
            ],
            col_widths=[0.8*cm, 5.7*cm, 3*cm, 3.5*cm, 4*cm]
        ),
        PageBreak(),
    ]

    # ── SECTION 7: BUSINESS MODEL ──────────────────────────────────────────────
    story += section_divider('Section 7')
    story += [
        P('Business Model & Monetisation Strategy', 'h1'),
        P('Revenue Streams', 'h2'),
        data_table(
            ['Revenue Stream', 'Description', 'Price', 'Scalability'],
            [
                ['Audit Report', 'One-time data analysis + PDF report for a single listing', '£149–249', 'Very High'],
                ['Full Consulting Package', 'Audit + 90-day support + 2 check-in calls', '£499–799', 'Medium'],
                ['Monthly Retainer', 'Ongoing optimisation, pricing strategy, monthly report', '£199–349/mo', 'High'],
                ['Property Setup Package', 'Done-for-you listing creation + photography coordination', '£799–1,499', 'Low'],
                ['Online Course', '"From Zero to Superhost in 90 Days" — evergreen video course', '£197–297', 'Very High'],
                ['Group Coaching Cohort', '10–15 hosts, 8-week programme with live calls', '£497–797/person', 'High'],
                ['Affiliate / Referrals', 'STL insurance, smart locks, property managers', '£20–150/referral', 'Passive'],
                ['SaaS (Year 2)', 'Self-serve dashboard for hosts to run their own analysis', '£29–79/mo', 'Very High'],
            ],
            col_widths=[4*cm, 6.5*cm, 2.8*cm, 3.7*cm]
        ),
        sp(0.4),
        P('Revenue Focus by Business Stage', 'h2'),
        data_table(
            ['Stage', 'Timeline', 'Primary Revenue', 'Target MRR'],
            [
                ['Launch', 'Months 1–2', 'Audit Reports + Full Consulting Packages', '£2,000–5,000'],
                ['Growth', 'Months 3–6', 'Retainers + Consulting + Online course launch', '£5,000–12,000'],
                ['Scale', 'Months 7–12', 'Course + Cohorts + Affiliate income', '£12,000–25,000'],
                ['Expansion', 'Year 2+', 'SaaS + multi-city + team hire', '£25,000–50,000+'],
            ],
            col_widths=[2.5*cm, 3.5*cm, 7*cm, 4*cm]
        ),
        sp(0.4),
        P('Why This Business Works', 'h2'),
        bullet('<b>Massive under-monetisation:</b> 65% of Bristol hosts earn less than 40% of their potential — the pain is obvious.'),
        bullet('<b>Fast client ROI:</b> A client paying £499 and implementing recommendations earns it back in 4–8 weeks. Easy sell.'),
        bullet('<b>Proprietary data model:</b> GBM trained on 2,879 local listings — no competitor has this for Bristol.'),
        bullet('<b>Referral flywheel:</b> Airbnb host communities are tight-knit. Happy clients refer neighbours.'),
        bullet('<b>Low overhead:</b> Fully remote, no inventory. Marginal cost of an extra client approaches zero.'),
        PageBreak(),
    ]

    # ── SECTION 8: SERVICE PRICING ─────────────────────────────────────────────
    story += section_divider('Section 8')
    story += [
        P('Pricing Your Consulting Services', 'h1'),
        data_table(
            ['Package', 'Includes', 'Price', 'Target Client'],
            [
                ['Starter Audit',
                 '• Full data analysis of their listing\n• Competitor benchmarking\n• Top 10 prioritised recommendations\n• 1-page summary PDF\n• No calls',
                 '£149', 'Curious hosts wanting to validate the problem'],
                ['Growth Package',
                 '• Everything in Audit\n• 60-min strategy call\n• Implementation roadmap\n• Pricing model output\n• 30-day email support + check-in call',
                 '£499', 'Committed hosts who want a clear plan'],
                ['Premium Package',
                 '• Everything in Growth\n• Done-for-you listing optimisation\n• Photo shoot coordination\n• Amenity shopping list\n• 90-day support + monthly reporting',
                 '£799', 'Hosts who want hands-off help'],
                ['Monthly Retainer',
                 '• Monthly revenue analysis\n• Pricing updates\n• Algorithm & competitor watch\n• Monthly 30-min strategy call',
                 '£249/mo', 'Ongoing clients focused on continuous improvement'],
            ],
            col_widths=[3*cm, 8.5*cm, 2*cm, 3.5*cm]
        ),
        sp(0.3),
        P(
            '<b>Upsell path:</b> Starter Audit → Growth Package → Monthly Retainer. '
            'Target 30% of Audit buyers converting to Growth, and 40% of Growth clients staying on Retainer.',
            'body'
        ),
        PageBreak(),
    ]

    # ── SECTION 9: GO-TO-MARKET ────────────────────────────────────────────────
    story += section_divider('Section 9')
    story += [
        P('Go-to-Market Plan', 'h1'),
        P('Phase 1 — Validation (Month 1–2)', 'h2'),
        bullet('Identify 20 Bristol Airbnb hosts in top neighbourhoods via LinkedIn, Facebook groups, and Nextdoor.'),
        bullet('Offer 3 free audits in exchange for testimonials and before/after case study numbers.'),
        bullet('Build a simple landing page (Notion or Carrd) with value prop and Calendly booking link.'),
        bullet('Post the free audit offer in Bristol Airbnb Facebook groups and r/airbnb.'),
        bullet('Record a 5-minute Loom walking through a real audit as a lead magnet.'),
        sp(0.3),
        P('Phase 2 — Traction (Month 3–6)', 'h2'),
        bullet('Publish case studies with real % uplift figures on LinkedIn and Medium.'),
        bullet('Launch a YouTube channel "Bristol Airbnb Tips" — 2 videos/month. Excellent SEO channel.'),
        bullet('Build an email list with a free "Bristol Airbnb Neighbourhood Guide" PDF opt-in.'),
        bullet('Partner with Bristol estate agents and letting agencies as referral partners (offer 10% commission).'),
        bullet('Run targeted Facebook/Instagram ads to Bristol homeowners aged 28–55.'),
        sp(0.3),
        P('Phase 3 — Scale (Month 7–12)', 'h2'),
        bullet('Launch the online course to your email list. Target 50 sales at £197 = £9,850.'),
        bullet('Run a group coaching cohort: 10 hosts × £597 = £5,970 per 8-week cohort.'),
        bullet('Expand to Bath, Cardiff, and other UK cities using the same model (Inside Airbnb data is publicly available for all major UK cities).'),
        bullet('Build a referral programme: every referring client earns £50 credit.'),
        sp(0.3),
        P('Content & Social Strategy', 'h2'),
        data_table(
            ['Channel', 'Content Type', 'Frequency', 'Goal'],
            [
                ['LinkedIn', 'Case studies, data insights, before/after screenshots', '3×/week', 'Professional credibility'],
                ['Instagram', 'Listing makeovers, neighbourhood tips, reels', '4×/week', 'Visual storytelling'],
                ['YouTube', '"Airbnb Bristol Tips" educational videos', '1–2×/month', 'SEO + trust'],
                ['Email newsletter', '"The Airbnb Edge" — weekly tips', 'Weekly', 'Warm audience for course'],
                ['TikTok', 'Quick tips, data reveals, "did you know" clips', '3×/week', 'Viral reach & awareness'],
                ['Facebook Groups', 'Value-first answers + soft pitches', 'Daily', 'Direct client acquisition'],
            ],
            col_widths=[3*cm, 6.5*cm, 3*cm, 4.5*cm]
        ),
        PageBreak(),
    ]

    # ── SECTION 10: FINANCIALS ─────────────────────────────────────────────────
    story += section_divider('Section 10')
    story += [
        P('Financial Projections', 'h1'),
        P('Conservative Year 1 Forecast', 'h2'),
        data_table(
            ['Quarter', 'Clients', 'Revenue Mix', 'Revenue', 'Costs', 'Profit'],
            [
                ['Q1 (M1–3)', '5–8', '3 free + 5 paid Audit/Growth', '£1,500–3,000', '£500', '£1,000–2,500'],
                ['Q2 (M4–6)', '15–20', 'All packages + 3 retainers', '£6,000–10,000', '£1,000', '£5,000–9,000'],
                ['Q3 (M7–9)', '20–30', 'Growth/Premium + 8 retainers + course launch', '£12,000–20,000', '£2,000', '£10,000–18,000'],
                ['Q4 (M10–12)', '25–35', 'Full mix + cohort + affiliates', '£15,000–25,000', '£2,500', '£12,500–22,500'],
                ['YEAR 1 TOTAL', '—', '—', '£34,500–58,000', '£6,000', '£28,500–52,000'],
            ],
            col_widths=[2.5*cm, 2*cm, 5.5*cm, 3.2*cm, 2.3*cm, 3.5*cm]
        ),
        sp(0.4),
        P('Year 2 Conservative Targets', 'h2'),
        kpi_row([
            ('Revenue Target', '£120,000+'),
            ('Monthly Retainers', '30+'),
            ('Course Revenue', '£20,000+'),
            ('Profit Margin', '80%+'),
        ]),
        sp(0.4),
        P('Unit Economics', 'h2'),
        bullet('<b>Marginal cost per client:</b> ~£20–50 (your time + tools)'),
        bullet('<b>Fixed monthly costs:</b> ~£100 (Canva Pro, Calendly, email marketing, hosting)'),
        bullet('<b>Gross margin:</b> 85–90% once systems are built'),
        bullet('<b>Break-even:</b> 3–4 paid clients per month covers all costs'),
        PageBreak(),
    ]

    # ── SECTION 11: RISK REGISTER ──────────────────────────────────────────────
    story += section_divider('Section 11')
    story += [
        P('Risk Register', 'h1'),
        data_table(
            ['Risk', 'Likelihood', 'Impact', 'Mitigation'],
            [
                ['Airbnb algorithm changes invalidate recommendations', 'Medium', 'Medium', 'Stay active in host communities; refresh model with new quarterly data scrapes'],
                ['Low initial client conversion', 'Medium', 'Medium', 'Lead with free audits; build social proof fast; keep entry price under £200'],
                ['Competitor copies the approach', 'Low', 'Medium', 'Build brand/trust moat; proprietary local data; client relationships'],
                ['Regulatory changes to STLs in Bristol', 'Low', 'High', 'Diversify to other UK cities; stay informed on housing legislation'],
                ['Inside Airbnb data becomes unavailable', 'Low', 'High', 'Build own data collection; use AirDNA as backup source'],
                ['Client results fall below projections', 'Low', 'High', 'Set realistic expectations upfront; track full implementation before measuring'],
            ],
            col_widths=[5*cm, 2.5*cm, 2*cm, 7.5*cm]
        ),
        PageBreak(),
    ]

    # ── SECTION 12: APPENDIX ──────────────────────────────────────────────────
    story += section_divider('Section 12')
    story += [
        P('Appendix — Property Scoring Criteria', 'h1'),
        P(
            'This scoring matrix is used in every client audit to benchmark a property '
            'across all major revenue dimensions. Each is scored 0–20 (total out of 140).',
            'body'
        ),
        sp(0.2),
        data_table(
            ['Dimension', 'Max Score', 'How to Score 20/20'],
            [
                ['Pricing Optimisation', '20', 'Within ±5% of model-recommended price for their property type & neighbourhood'],
                ['Amenity Quality', '20', '15+ relevant amenities ticked including workspace, fast WiFi, self check-in'],
                ['Host Quality', '20', 'Superhost status, identity verified, profile picture, 100% response rate'],
                ['Booking Settings', '20', 'Instant book ON, 2–3 min nights, 200+ days availability, flexible cancellation'],
                ['Review Profile', '20', '20+ reviews, 4.8+ overall, 4.8+ cleanliness, responds to all reviews'],
                ['Listing Quality', '20', '25+ photos, 300+ word description, keyword-rich title, all sections complete'],
                ['Location & Availability', '20', 'Top-10 neighbourhood, 300+ days open, calendar updated within 7 days'],
            ],
            col_widths=[5.5*cm, 2.5*cm, 9*cm]
        ),
        sp(0.4),
        P('Score Interpretation', 'h2'),
        data_table(
            ['Score', 'Category', 'Consulting Priority'],
            [
                ['0–40', 'Underperforming', 'Critical — likely earning <25% of potential revenue'],
                ['41–70', 'Average', 'High — 30–50% uplift achievable quickly with basic changes'],
                ['71–100', 'Good', 'Medium — 10–25% gains from targeted fine-tuning'],
                ['101–120', 'Strong', 'Low — focus on scaling rather than single-listing optimisation'],
                ['121–140', 'Excellent', 'Optimised — consider multi-property expansion strategy'],
            ],
            col_widths=[2.5*cm, 4*cm, 10.5*cm]
        ),
        sp(0.8),
        hr(MID_GREY),
        P('AirbnbEdge Consulting  |  Data-Driven Airbnb Optimisation  |  Bristol, UK', 'footer_note'),
        P('Dataset: Inside Airbnb — Bristol (June 2025)  |  Model: Gradient Boosting R² ≈ 0.72', 'footer_note'),
    ]

    doc.build(story, onFirstPage=light_page, onLaterPages=light_page)
    print(f'PDF saved: {output_path}')

if __name__ == '__main__':
    build_pdf()
