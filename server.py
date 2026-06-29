from __future__ import annotations

import base64
import getpass
import hashlib
import hmac
import json
import os
import re
import secrets
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

HOST = "127.0.0.1"
PORT = 8787
TODAY = date.today()
ROOT = Path(__file__).resolve().parent
SESSIONS: dict[str, dict] = {}
DB_PASSWORD = os.environ.get("SUPABASE_DB_PASSWORD")
if not DB_PASSWORD and __name__ == "__main__":
    DB_PASSWORD = getpass.getpass("Supabase DB password: ")
SESSION_SECRET = os.environ.get("SESSION_SECRET") or DB_PASSWORD or "local-dev-session-secret"


def parse_date(value):
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    for pattern in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(text[:10], pattern).date()
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def row_date(row, entry_key="entry_date"):
    return parse_date(row.get(entry_key)) or parse_date(row.get("created_at"))


def is_today(row, entry_key="entry_date"):
    return row_date(row, entry_key) == TODAY


def clean_text(value):
    return (str(value or "").strip())


def is_blank(value):
    return clean_text(value) == ""


def clean_location(value):
    text = clean_text(value) or "Unassigned"
    return text.upper()


def norm(value):
    return clean_text(value).lower()


def split_list(value):
    return [item.strip() for item in re.split(r"[,\n]+", clean_text(value)) if item.strip()]


def money(value):
    cleaned = re.sub(r"[^0-9.\-]", "", clean_text(value))
    if cleaned in ("", "-", "."):
        return 0
    try:
        return int(Decimal(cleaned))
    except Exception:
        return 0


def pct(num, den):
    return f"{round((num / den) * 100) if den else 0}%"


def rs(num):
    return f"Rs. {num:,.0f}"


def month_key(day):
    return day.strftime("%Y-%m") if day else ""


def month_label(key):
    if not key:
        return "Unassigned"
    try:
        return datetime.strptime(key, "%Y-%m").strftime("%b-%Y")
    except ValueError:
        return key


def parse_month_year(value):
    text = clean_text(value)
    if not text:
        return None
    for pattern in ("%b-%Y", "%B-%Y", "%m-%Y", "%Y-%m", "%b %Y", "%B %Y"):
        try:
            parsed = datetime.strptime(text, pattern)
            return date(parsed.year, parsed.month, 1)
        except ValueError:
            pass
    day = parse_date(text)
    return date(day.year, day.month, 1) if day else None


def add_month(month_day):
    if month_day.month == 12:
        return date(month_day.year + 1, 1, 1)
    return date(month_day.year, month_day.month + 1, 1)


def month_end(month_day):
    return add_month(month_day) - timedelta(days=1)


def month_range_keys(filters):
    start = parse_month_year(filters.get("monthFrom"))
    end = parse_month_year(filters.get("monthTo"))
    if not start and not end:
        return []
    start = start or end
    end = end or start
    if start > end:
        start, end = end, start
    keys = []
    cursor = start
    while cursor <= end:
        keys.append(month_key(cursor))
        cursor = add_month(cursor)
    return keys


def month_in_date_range(month_day, filters):
    if not month_day:
        return True
    start = parse_month_year(filters.get("monthFrom"))
    end = parse_month_year(filters.get("monthTo"))
    if start and end and start > end:
        start, end = end, start
    if start and month_day < date(start.year, start.month, 1):
        return False
    if end and month_day > date(end.year, end.month, 1):
        return False
    return True


def incentive_date_filters(filters):
    scoped = dict(filters or {})
    month_start = parse_month_year(scoped.get("monthFrom"))
    month_finish = parse_month_year(scoped.get("monthTo"))
    if month_start and month_finish and month_start > month_finish:
        month_start, month_finish = month_finish, month_start
    if month_start:
        scoped["dateFrom"] = month_start.isoformat()
    elif not scoped.get("dateFrom"):
        scoped["dateFrom"] = "2026-06-01"
    if month_finish:
        scoped["dateTo"] = month_end(month_finish).isoformat()
    elif not scoped.get("dateTo"):
        scoped["dateTo"] = "2026-06-30"
    return scoped


def bucket_age(day):
    if not day:
        return "> 30"
    diff = (TODAY - day).days
    if diff <= 0:
        return "Today"
    if diff <= 15:
        return "1-15"
    if diff <= 30:
        return "16-30"
    return "> 30"


def tat_bucket(days):
    if days <= 0:
        return "Same Day"
    if days <= 10:
        return "1-10"
    if days <= 20:
        return "11-20"
    return ">20"


def is_lost_lead(row):
    return norm(row.get("l_status")) == "lost"


def is_active_lead(row):
    return is_blank(row.get("l_booking_status"))


def is_followup_pending(row):
    return is_blank(row.get("l_status"))


def is_followup_done(row):
    updated_on = parse_date(row.get("l_last_updated_on"))
    return norm(row.get("l_booking_status")) == "next follow up" and bool(updated_on) and updated_on <= TODAY


def is_active_booking(row):
    return is_blank(row.get("status"))


def house_kind(value):
    text = norm(value).replace("-", " ").replace("_", " ")
    compact = text.replace(" ", "")
    if text == "in house" or compact == "inhouse":
        return "in"
    if text == "out house" or compact == "outhouse":
        return "out"
    return ""


def mg_model_group(row):
    model = norm(row.get("model"))
    variant = norm(row.get("variant"))
    text = f"{model} {variant}"
    if any(name in text for name in ("windsor", "comet", "zs ev")):
        return "premium_ev"
    if any(name in text for name in ("hector", "astor", "majestor")):
        return "hector_astor_majestor"
    return "other"


def incentive_slab(total_retail):
    if total_retail >= 7:
        return "Champion", 5000, 6000
    if total_retail >= 4:
        return "Performer", 3500, 3750
    if total_retail >= 2:
        return "Mandatory Qualification", 2000, 2500
    return "Not Qualified", 0, 0


def db():
    if not DB_PASSWORD:
        raise RuntimeError("SUPABASE_DB_PASSWORD environment variable is required")
    import pg8000.dbapi

    return pg8000.dbapi.connect(
        database="postgres",
        user="postgres",
        password=DB_PASSWORD,
        host="db.lstyimmqzkskwvcrytev.supabase.co",
        port=5432,
        ssl_context=True,
        timeout=10,
    )


def dict_rows(cur):
    columns = [item[0] for item in (cur.description or [])]
    return [dict(zip(columns, row)) for row in cur.fetchall()]


def dict_one(cur):
    columns = [item[0] for item in (cur.description or [])]
    row = cur.fetchone()
    return dict(zip(columns, row)) if row else None


def _b64_encode(data):
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64_decode(text):
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def make_session_token(user):
    payload = _b64_encode(json.dumps(user, separators=(",", ":"), default=str).encode("utf-8"))
    signature = hmac.new(SESSION_SECRET.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).digest()
    return f"{payload}.{_b64_encode(signature)}"


def read_session_token(token):
    if not token or "." not in token:
        return None
    payload, signature = token.rsplit(".", 1)
    expected = _b64_encode(hmac.new(SESSION_SECRET.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).digest())
    if not hmac.compare_digest(signature, expected):
        return None
    try:
        return json.loads(_b64_decode(payload).decode("utf-8"))
    except Exception:
        return None


def password_matches(stored, entered):
    if stored is None:
        return False
    stored_text = clean_text(stored)
    entered_text = clean_text(entered)
    if stored_text == entered_text:
        return True
    try:
        return str(int(Decimal(stored_text))) == entered_text
    except Exception:
        return False


def authenticate(email, password):
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            'select "Email", "Name", "Password", "Brand", "Location" from public."User Access" where lower("Email") = lower(%s) limit 1',
            (email,),
        )
        user = dict_one(cur)
    if not user or not password_matches(user.get("Password"), password):
        return None
    return {
        "email": user["Email"],
        "name": user.get("Name") or user["Email"],
        "brands": split_list(user.get("Brand")),
        "locations": [clean_location(x) for x in split_list(user.get("Location"))],
    }


def fetch_table(cur, table):
    cur.execute(f'select * from public."{table}"')
    return dict_rows(cur)


def brand_ok(row, selected_brand):
    if not selected_brand:
        return True
    return norm(row.get("brand") or row.get("l_brand")) == norm(selected_brand)


def target_brand_ok(row, selected_brand):
    if not selected_brand:
        return True
    return norm(row.get("Brand")) == norm(selected_brand)


def location_ok(row, allowed_locations, lead=False):
    value = row.get("l_location") if lead else row.get("sales_location")
    return clean_location(value) in set(allowed_locations)


def target_location_ok(row, allowed_locations):
    return clean_location(row.get("Location")) in set(allowed_locations)


def sc_brand_ok(row, selected_brand):
    if not selected_brand:
        return True
    return norm(row.get("Brand")) == norm(selected_brand)


def sc_location_ok(row, allowed_locations):
    return clean_location(row.get("SalesLocation")) in set(allowed_locations)


def row_model(row):
    return clean_text(row.get("model") or row.get("l_model"))


def row_source(row):
    return clean_text(row.get("source") or row.get("l_source"))


def in_date_range(row, filters, entry_key="entry_date"):
    day = row_date(row, entry_key)
    start = parse_date(filters.get("dateFrom"))
    end = parse_date(filters.get("dateTo"))
    if start and (not day or day < start):
        return False
    if end and (not day or day > end):
        return False
    return True


def filter_values(filters, key):
    value = filters.get(key)
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return [clean_text(item) for item in value if clean_text(item)]
    return [clean_text(value)]


def matches_common_filters(row, filters, lead=False):
    locations = filter_values(filters, "location")
    models = filter_values(filters, "model")
    entry_key = "l_entry_date" if lead else "entry_date"
    if locations and clean_location(row.get("l_location") if lead else row.get("sales_location")) not in {clean_location(item) for item in locations}:
        return False
    if models and norm(row_model(row)) not in {norm(item) for item in models}:
        return False
    return in_date_range(row, filters, entry_key)


def filter_options(leads, bookings, retails, cancellations, sc_rows=None):
    sc_rows = sc_rows or []
    locations = sorted(
        {clean_location(r.get("l_location")) for r in leads}
        | {clean_location(r.get("sales_location")) for r in bookings}
        | {clean_location(r.get("sales_location")) for r in retails}
        | {clean_location(r.get("sales_location")) for r in cancellations}
        | {clean_location(r.get("SalesLocation")) for r in sc_rows}
    )
    sources = sorted({row_source(r) for r in leads + bookings + cancellations if row_source(r)})
    models = sorted({row_model(r) for r in leads + bookings + retails + cancellations if row_model(r)})
    return {"locations": locations, "sources": sources, "models": models}


def filter_target_rows(targets, selected_brand, allowed_locations, filters):
    locations = filter_values(filters, "location")
    location_set = {clean_location(item) for item in locations}
    rows = []
    for row in targets:
        month_day = parse_month_year(row.get("Month_Year"))
        if not target_brand_ok(row, selected_brand):
            continue
        if not target_location_ok(row, allowed_locations):
            continue
        if location_set and clean_location(row.get("Location")) not in location_set:
            continue
        if not month_in_date_range(month_day, filters):
            continue
        rows.append(row)
    return rows


def build_target_report(selected_brand, filters, options, sc_rows, targets, retails):
    target_by_key = defaultdict(lambda: {"target": 0, "name": "", "email": "", "location": "", "month": ""})
    for row in targets:
        email = norm(row.get("SC Email"))
        month_day = parse_month_year(row.get("Month_Year"))
        key_month = month_key(month_day) or clean_text(row.get("Month_Year")) or "Unassigned"
        key = (email, key_month)
        item = target_by_key[key]
        item["target"] += money(row.get("Target"))
        item["name"] = item["name"] or clean_text(row.get("SC Name")) or "Unassigned"
        item["email"] = item["email"] or clean_text(row.get("SC Email"))
        item["location"] = item["location"] or clean_location(row.get("Location"))
        item["month"] = key_month

    sc_by_email = {}
    for row in sc_rows:
        email = norm(row.get("Sales Person Email ID"))
        if not email:
            continue
        sc_by_email[email] = {
            "name": clean_text(row.get("Sales Person")) or "Unassigned",
            "email": clean_text(row.get("Sales Person Email ID")),
            "location": clean_location(row.get("SalesLocation")),
        }

    retail_by_key = Counter()
    for row in retails:
        email = norm(row.get("sales_person_email_id"))
        day = row_date(row)
        key_month = month_key(day) or "Unassigned"
        key = (email, key_month)
        retail_by_key[key] += 1

    selected_months = month_range_keys(filters)
    months = selected_months or sorted({key[1] for key in target_by_key} or {key[1] for key in retail_by_key if key[0] in sc_by_email})
    keys = []
    for email in sorted(sc_by_email, key=lambda value: (sc_by_email[value]["name"], value)):
        for key_month in months:
            if month_in_date_range(parse_month_year(key_month), filters):
                keys.append((email, key_month))

    rows = []
    for key in keys:
        target = target_by_key[key]
        sc = sc_by_email.get(key[0], {})
        target_value = target["target"]
        retail = retail_by_key[key]
        rows.append([
            sc.get("name") or target["name"] or "Unassigned",
            sc.get("location") or target["location"] or "Unassigned",
            month_label(target["month"] or key[1]),
            target_value,
            retail,
            max(target_value - retail, 0),
            pct(retail, target_value),
        ])

    total_target = sum(row[3] for row in rows)
    total_retail = sum(row[4] for row in rows)
    rows.append(["Total", "", "", total_target, total_retail, max(total_target - total_retail, 0), pct(total_retail, total_target)])

    return {
        "brand": selected_brand,
        "reportType": "target",
        "groupLabel": "Sales Person",
        "locations": options.get("locations", []),
        "groups": [row[0] for row in rows[:-1]],
        "filters": filters,
        "filterOptions": options,
        "cards": [
            {"label": "TOTAL TARGET", "value": total_target},
            {"label": "TOTAL RETAIL", "value": total_retail},
            {"label": "ACHIEVEMENT", "value": pct(total_retail, total_target)},
            {"label": "SALES PERSONS", "value": len(rows) - 1},
        ],
        "tables": [
            {
                "title": "Sales Person Target Achievement",
                "wide": True,
                "headers": ["SC Name", "Location", "Month", "Target", "Retail", "Pending", "Achievement %"],
                "rows": rows,
            }
        ],
    }


def build_incentive_report(selected_brand, filters, options, sc_rows, retails):
    filters = incentive_date_filters(filters)
    if norm(selected_brand) != "mg":
        return {
            "brand": selected_brand,
            "reportType": "incentive",
            "groupLabel": "Sales Person",
            "locations": options.get("locations", []),
            "groups": [],
            "filters": filters,
            "filterOptions": options,
            "cards": [
                {"label": "TOTAL RETAIL", "value": 0},
                {"label": "GROSS INCENTIVE", "value": rs(0)},
                {"label": "DEDUCTION", "value": rs(0)},
                {"label": "NET INCENTIVE", "value": rs(0)},
            ],
            "tables": [
                {
                    "title": "MG Sales Incentive",
                    "wide": True,
                    "headers": ["Note"],
                    "rows": [["MG incentive calculation is currently configured only for MG brand."]],
                }
            ],
        }

    retail_by_email = defaultdict(list)
    for row in retails:
        if matches_common_filters(row, filters):
            retail_by_email[norm(row.get("sales_person_email_id"))].append(row)

    rows = []
    total_retail_sum = 0
    total_ham_sum = 0
    total_premium_sum = 0
    total_other_sum = 0
    total_gross_sum = 0
    total_deduction_sum = 0
    total_net_sum = 0
    for sc in sorted(sc_rows, key=lambda row: (clean_location(row.get("SalesLocation")), clean_text(row.get("Sales Person")))):
        email = norm(sc.get("Sales Person Email ID"))
        sc_retails = retail_by_email.get(email, [])
        total_retail = len(sc_retails)
        ham_count = sum(1 for row in sc_retails if mg_model_group(row) == "hector_astor_majestor")
        premium_count = sum(1 for row in sc_retails if mg_model_group(row) == "premium_ev")
        other_count = max(total_retail - ham_count - premium_count, 0)
        slab, ham_rate, premium_rate = incentive_slab(total_retail)
        gross = ham_count * ham_rate + premium_count * premium_rate
        finance_inhouse = sum(1 for row in sc_retails if house_kind(row.get("in_out_house")) == "in")
        insurance_inhouse = sum(1 for row in sc_retails if house_kind(row.get("insurance_from")) == "in")
        finance_pct = round((finance_inhouse / total_retail) * 100) if total_retail else 0
        insurance_pct = round((insurance_inhouse / total_retail) * 100) if total_retail else 0
        deduction_pct = 0
        deduction_notes = []
        if total_retail and finance_pct < 50:
            deduction_pct += 20
            deduction_notes.append("Finance <50%")
        if total_retail and insurance_pct < 90:
            deduction_pct += 20
            deduction_notes.append("Insurance <90%")
        deduction_amount = round(gross * deduction_pct / 100)
        net = max(gross - deduction_amount, 0)
        total_retail_sum += total_retail
        total_ham_sum += ham_count
        total_premium_sum += premium_count
        total_other_sum += other_count
        total_gross_sum += gross
        total_deduction_sum += deduction_amount
        total_net_sum += net
        rows.append([
            clean_text(sc.get("Sales Person")) or "Unassigned",
            clean_location(sc.get("SalesLocation")),
            total_retail,
            slab,
            ham_count,
            premium_count,
            other_count,
            rs(gross),
            f"{finance_pct}%",
            f"{insurance_pct}%",
            f"{deduction_pct}%",
            rs(deduction_amount),
            rs(net),
            ", ".join(deduction_notes) or "-",
        ])

    rows.append([
        "Total",
        "",
        total_retail_sum,
        "",
        total_ham_sum,
        total_premium_sum,
        total_other_sum,
        rs(total_gross_sum),
        "",
        "",
        "",
        rs(total_deduction_sum),
        rs(total_net_sum),
        "",
    ])

    return {
        "brand": selected_brand,
        "reportType": "incentive",
        "groupLabel": "Sales Person",
        "locations": options.get("locations", []),
        "groups": [row[0] for row in rows[:-1]],
        "filters": filters,
        "filterOptions": options,
        "cards": [
            {"label": "TOTAL RETAIL", "value": total_retail_sum},
            {"label": "GROSS INCENTIVE", "value": rs(total_gross_sum)},
            {"label": "DEDUCTION", "value": rs(total_deduction_sum)},
            {"label": "NET INCENTIVE", "value": rs(total_net_sum)},
        ],
        "tables": [
            {
                "title": "MG Sales Incentive",
                "wide": True,
                "headers": [
                    "SC Name",
                    "Location",
                    "Retail",
                    "Slab",
                    "Hector/Astor/Majestor",
                    "Windsor/Comet/ZS EV",
                    "Other",
                    "Gross Incentive",
                    "Finance %",
                    "Insurance %",
                    "Deduction %",
                    "Deduction",
                    "Net Incentive",
                    "Remarks",
                ],
                "rows": rows,
            },
            {
                "title": "MG Incentive Policy Basis",
                "headers": ["Rule", "Value"],
                "rows": [
                    ["2-3 cars", "Rs. 2,000 per Hector/Astor/Majestor; Rs. 2,500 per Windsor/Comet/ZS EV"],
                    ["4-6 cars", "Rs. 3,500 per Hector/Astor/Majestor; Rs. 3,750 per Windsor/Comet/ZS EV"],
                    ["7+ cars", "Rs. 5,000 per Hector/Astor/Majestor; Rs. 6,000 per Windsor/Comet/ZS EV"],
                    ["Finance deduction", "20% if in-house finance penetration is below 50%"],
                    ["Insurance deduction", "20% if in-house insurance penetration is below 90%"],
                    ["Date scope", "Defaults to 01-Jun-2026 to 30-Jun-2026 unless date filters are applied"],
                ],
            },
        ],
    }


def group_key(row, report_type, lead=False, booking_source_by_no=None):
    if report_type == "source":
        value = row_source(row)
        if not value and booking_source_by_no and row.get("booking_no"):
            value = booking_source_by_no.get(row.get("booking_no"))
        return clean_text(value) or "Unassigned"
    if report_type == "model":
        return row_model(row) or "Unknown"
    value = row.get("l_location") if lead else row.get("sales_location")
    return clean_location(value)


def group_label(report_type):
    return {"source": "Source", "model": "Model", "target": "Sales Person", "incentive": "Sales Person"}.get(report_type, "Location")


def build_report(user, selected_brand, filters=None, report_type="location"):
    filters = filters or {}
    report_type = report_type if report_type in {"location", "source", "model", "target", "incentive"} else "location"
    if selected_brand not in user["brands"]:
        raise ValueError("Brand is not allowed for this user")

    with db() as conn, conn.cursor() as cur:
        leads = fetch_table(cur, "Singhania_Leads")
        bookings = fetch_table(cur, "Singhania_Bookings")
        retails = fetch_table(cur, "Singhania_Retails")
        targets = fetch_table(cur, "Sales Target")
        sc_rows = fetch_table(cur, "Singhania SC Data")
        cur.execute('select * from public.singhania_cancellation')
        cancellations = dict_rows(cur)

    allowed_locations = user["locations"]
    leads = [r for r in leads if brand_ok(r, selected_brand) and location_ok(r, allowed_locations, lead=True)]
    bookings = [r for r in bookings if brand_ok(r, selected_brand) and location_ok(r, allowed_locations)]
    retails = [r for r in retails if brand_ok(r, selected_brand) and location_ok(r, allowed_locations)]
    cancellations = [r for r in cancellations if brand_ok(r, selected_brand) and location_ok(r, allowed_locations)]
    targets = [r for r in targets if target_brand_ok(r, selected_brand) and target_location_ok(r, allowed_locations)]
    sc_rows = [r for r in sc_rows if sc_brand_ok(r, selected_brand) and sc_location_ok(r, allowed_locations) and norm(r.get("Role")) == "sc"]
    options = filter_options(leads, bookings, retails, cancellations, sc_rows)
    target_locations = {clean_location(r.get("Location")) for r in targets}
    options["locations"] = sorted(set(options["locations"]) | target_locations)

    source_filters = filter_values(filters, "source")
    source_filter_set = {norm(item) for item in source_filters}
    booking_source_by_no = {r.get("booking_no"): row_source(r) for r in bookings if r.get("booking_no")}
    leads = [
        r for r in leads
        if matches_common_filters(r, filters, lead=True)
        and (not source_filter_set or norm(row_source(r)) in source_filter_set)
    ]
    bookings = [
        r for r in bookings
        if matches_common_filters(r, filters)
        and (not source_filter_set or norm(row_source(r)) in source_filter_set)
    ]
    retails = [
        r for r in retails
        if matches_common_filters(r, filters)
        and (not source_filter_set or norm(booking_source_by_no.get(r.get("booking_no"))) in source_filter_set)
    ]
    targets = filter_target_rows(targets, selected_brand, allowed_locations, filters)
    location_filter_set = {clean_location(item) for item in filter_values(filters, "location")}
    if location_filter_set:
        sc_rows = [r for r in sc_rows if clean_location(r.get("SalesLocation")) in location_filter_set]
    cancellations = [
        r for r in cancellations
        if matches_common_filters(r, filters)
        and (not source_filter_set or norm(row_source(r)) in source_filter_set)
    ]

    if report_type == "target":
        return build_target_report(selected_brand, filters, options, sc_rows, targets, retails)

    if report_type == "incentive":
        return build_incentive_report(selected_brand, filters, options, sc_rows, retails)

    groups = sorted(
        {group_key(r, report_type, lead=True, booking_source_by_no=booking_source_by_no) for r in leads}
        | {group_key(r, report_type, booking_source_by_no=booking_source_by_no) for r in bookings}
        | {group_key(r, report_type, booking_source_by_no=booking_source_by_no) for r in retails}
        | {group_key(r, report_type, booking_source_by_no=booking_source_by_no) for r in cancellations}
    )

    lead_by_loc = defaultdict(list)
    booking_by_loc = defaultdict(list)
    retail_by_loc = defaultdict(list)
    cancel_by_loc = defaultdict(list)
    for row in leads:
        lead_by_loc[group_key(row, report_type, lead=True, booking_source_by_no=booking_source_by_no)].append(row)
    for row in bookings:
        booking_by_loc[group_key(row, report_type, booking_source_by_no=booking_source_by_no)].append(row)
    for row in retails:
        retail_by_loc[group_key(row, report_type, booking_source_by_no=booking_source_by_no)].append(row)
    for row in cancellations:
        cancel_by_loc[group_key(row, report_type, booking_source_by_no=booking_source_by_no)].append(row)

    model_names = [name for name, _ in Counter((r.get("model") or "Unknown").strip() or "Unknown" for r in retails).most_common(8)]

    cards = [
        {"label": "TOTAL LEADS", "value": len(leads)},
        {"label": "TOTAL BOOKING", "value": len(bookings)},
        {"label": "TOTAL RETAIL", "value": len(retails)},
        {"label": "TOTAL CANCELLATION", "value": len(cancellations)},
        {"label": "E TO B", "value": pct(len(bookings), len(leads))},
        {"label": "E TO R", "value": pct(len(retails), len(leads))},
    ]

    etbr_rows = []
    for loc in groups:
        lrows = lead_by_loc[loc]
        brows = booking_by_loc[loc]
        rrows = retail_by_loc[loc]
        crows = cancel_by_loc[loc]
        lost = sum(1 for r in lrows if is_lost_lead(r))
        active = sum(1 for r in lrows if is_active_lead(r))
        follow_done = sum(1 for r in lrows if is_followup_done(r))
        follow_pending = sum(1 for r in lrows if is_followup_pending(r))
        active_bookings = sum(1 for r in brows if is_active_booking(r))
        etbr_rows.append([
            loc,
            sum(1 for r in lrows if is_today(r, "l_entry_date")),
            len(lrows),
            0,
            active,
            lost,
            follow_done,
            follow_pending,
            sum(1 for r in brows if is_today(r)),
            len(brows),
            active_bookings,
            0,
            sum(1 for r in rrows if is_today(r)),
            len(rrows),
            "0%",
            pct(len(brows), len(lrows)),
            pct(len(rrows), len(lrows)),
            len(crows),
        ])
    etbr_rows.append([
        "Total",
        sum(r[1] for r in etbr_rows),
        sum(r[2] for r in etbr_rows),
        0,
        sum(r[4] for r in etbr_rows),
        sum(r[5] for r in etbr_rows),
        sum(r[6] for r in etbr_rows),
        sum(r[7] for r in etbr_rows),
        sum(r[8] for r in etbr_rows),
        sum(r[9] for r in etbr_rows),
        sum(r[10] for r in etbr_rows),
        0,
        sum(r[12] for r in etbr_rows),
        sum(r[13] for r in etbr_rows),
        "0%",
        pct(sum(r[9] for r in etbr_rows), sum(r[2] for r in etbr_rows)),
        pct(sum(r[13] for r in etbr_rows), sum(r[2] for r in etbr_rows)),
        sum(r[17] for r in etbr_rows),
    ])

    lead_detail_rows = []
    follow_rows = []
    live_lead_rows = []
    model_rows = []
    for loc in groups:
        lrows = lead_by_loc[loc]
        rrows = retail_by_loc[loc]
        lost = sum(1 for r in lrows if is_lost_lead(r))
        lead_detail_rows.append([loc, len(lrows), sum(1 for r in lrows if "auto" in norm(r.get("l_source"))), lost])

        follow_counts = Counter()
        for row in lrows:
            if is_active_lead(row):
                follow_counts[bucket_age(row_date(row, "l_entry_date"))] += 1
        follow_rows.append([loc, follow_counts["Today"], follow_counts["1-15"], follow_counts["16-30"], follow_counts["> 30"], sum(follow_counts.values())])

        live_counts = Counter(bucket_age(row_date(r, "l_entry_date")) for r in lrows if is_active_lead(r))
        live_lead_rows.append([loc, live_counts["Today"], live_counts["1-15"], live_counts["16-30"], live_counts["> 30"], sum(live_counts.values())])

        model_counts = Counter((r.get("model") or "Unknown").strip() or "Unknown" for r in rrows)
        model_rows.append([loc, 0, len(rrows), "0%"] + [model_counts[m] for m in model_names])

    lead_detail_rows.append(["Total", len(leads), sum(r[2] for r in lead_detail_rows), sum(r[3] for r in lead_detail_rows)])
    follow_rows.append(["TOTAL"] + [sum(r[i] for r in follow_rows) for i in range(1, 6)])
    live_lead_rows.append(["TOTAL"] + [sum(r[i] for r in live_lead_rows) for i in range(1, 6)])
    model_rows.append(["Total", 0, len(retails), "0%"] + [sum(r[i] for r in model_rows) for i in range(4, 4 + len(model_names))])

    open_bookings = [r for r in bookings if is_active_booking(r)]
    booking_age_by_loc = defaultdict(Counter)
    for row in open_bookings:
        booking_age_by_loc[group_key(row, report_type, booking_source_by_no=booking_source_by_no)][bucket_age(row_date(row))] += 1
    booking_age_rows = []
    for loc in groups:
        counts = booking_age_by_loc[loc]
        booking_age_rows.append([loc, counts["Today"], counts["1-15"], counts["16-30"], counts["> 30"], sum(counts.values())])
    booking_age_rows.append(["TOTAL"] + [sum(r[i] for r in booking_age_rows) for i in range(1, 6)])

    booking_dates = {}
    for row in bookings:
        key = row.get("booking_no")
        if key and key not in booking_dates:
            booking_dates[key] = row_date(row)
    tat_by_loc = defaultdict(Counter)
    for row in retails:
        rday = row_date(row)
        bday = booking_dates.get(row.get("booking_no"))
        if rday and bday:
            tat_by_loc[group_key(row, report_type, booking_source_by_no=booking_source_by_no)][tat_bucket((rday - bday).days)] += 1
    tat_rows = []
    for loc in groups:
        counts = tat_by_loc[loc]
        tat_rows.append([loc, counts["Same Day"], counts["1-10"], counts["11-20"], counts[">20"]])
    tat_rows.append(["TOTAL"] + [sum(r[i] for r in tat_rows) for i in range(1, 5)])

    finance_rows = []
    insurance_rows = []
    ew_rows = []
    for loc in groups:
        rrows = retail_by_loc[loc]
        retail = len(rrows)
        inhouse = sum(1 for r in rrows if house_kind(r.get("in_out_house")) == "in")
        outhouse = sum(1 for r in rrows if house_kind(r.get("in_out_house")) == "out")
        finance_rows.append([loc, retail, inhouse, pct(inhouse, retail), outhouse, pct(outhouse, retail)])

        ins_inhouse = sum(1 for r in rrows if house_kind(r.get("insurance_from")) == "in")
        ins_outhouse = sum(1 for r in rrows if house_kind(r.get("insurance_from")) == "out")
        insurance_rows.append([loc, retail, ins_inhouse, pct(ins_inhouse, retail), ins_outhouse, pct(ins_outhouse, retail)])

        ew = sum(1 for r in rrows if norm(r.get("extended_warranty")) == "yes")
        ew_rows.append([loc, retail, ew, pct(ew, retail)])

    finance_rows.append(["Total", len(retails), sum(r[2] for r in finance_rows), pct(sum(r[2] for r in finance_rows), len(retails)), sum(r[4] for r in finance_rows), pct(sum(r[4] for r in finance_rows), len(retails))])
    insurance_rows.append(["Total", len(retails), sum(r[2] for r in insurance_rows), pct(sum(r[2] for r in insurance_rows), len(retails)), sum(r[4] for r in insurance_rows), pct(sum(r[4] for r in insurance_rows), len(retails))])
    ew_rows.append(["Total", len(retails), sum(r[2] for r in ew_rows), pct(sum(r[2] for r in ew_rows), len(retails))])
    etbr_header_rows = [
        [
            {"label": group_label(report_type), "rowSpan": 2},
            {"label": "Leads", "colSpan": 5},
            {"label": "Follow Up", "colSpan": 2},
            {"label": "Booking", "colSpan": 4},
            {"label": "Retail", "colSpan": 5},
            {"label": "Cancellation", "rowSpan": 2},
        ],
        ["FTD", "Total", "Auto", "Active", "Lost", "Done", "Pending", "FTD", "Total", "Active", "Target", "FTD", "Total", "(%)", "E to B (%)", "E to R (%)"],
    ]

    return {
        "brand": selected_brand,
        "reportType": report_type,
        "groupLabel": group_label(report_type),
        "locations": groups,
        "groups": groups,
        "filters": filters,
        "filterOptions": options,
        "cards": cards,
        "tables": [
            {"title": "ETBR", "wide": True, "headers": [group_label(report_type), "FTD", "Total", "Auto", "Active", "Lost", "Done", "Pending", "FTD", "Total", "Active", "Target", "FTD", "Total", "(%)", "E to B (%)", "E to R (%)", "Cancellation"], "headerRows": etbr_header_rows, "rows": etbr_rows},
            {"title": "Lead Details", "headers": [group_label(report_type), "Total", "Auto", "Lost"], "rows": lead_detail_rows},
            {"title": "Follow Up Summary", "headers": [group_label(report_type), "Today", "1-15", "16-30", "> 30", "Total"], "rows": follow_rows},
            {"title": "Live Leads (Aging)", "headers": [group_label(report_type), "Today", "1-15", "16-30", "> 30", "Total"], "rows": live_lead_rows},
            {"title": "Sales Target", "wide": True, "headers": [group_label(report_type), "Target", "Retail", "%"] + model_names, "rows": model_rows},
            {"title": "Live Bookings (Aging)", "headers": [group_label(report_type), "Today", "1-15", "16-30", "> 30", "Total"], "rows": booking_age_rows},
            {"title": "Booking to Retail TAT", "headers": [group_label(report_type), "Same Day", "1-10", "11-20", ">20"], "rows": tat_rows},
            {"title": f"{group_label(report_type)} Summary (Finance)", "headers": [group_label(report_type), "Retail", "Inhouse", "%", "Outhouse", "%"], "rows": finance_rows},
            {"title": f"{group_label(report_type)} Summary (Insurance)", "headers": [group_label(report_type), "Retail", "Inhouse", "%", "Outhouse", "%"], "rows": insurance_rows},
            {"title": f"{group_label(report_type)} Summary (EW)", "headers": [group_label(report_type), "Retail", "EW", "%"], "rows": ew_rows},
        ],
    }


class Handler(BaseHTTPRequestHandler):
    def send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Session-Token")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def send_json(self, payload, status=HTTPStatus.OK):
        data = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(status)
        self.send_cors_headers()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def read_json(self):
        size = int(self.headers.get("Content-Length", "0"))
        if not size:
            return {}
        return json.loads(self.rfile.read(size).decode("utf-8"))

    def session_user(self):
        token = self.headers.get("X-Session-Token", "")
        return SESSIONS.get(token)

    def do_OPTIONS(self):
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_cors_headers()
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            data = (ROOT / "index.html").read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_cors_headers()
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if parsed.path.startswith("/assets/"):
            asset = (ROOT / parsed.path.lstrip("/")).resolve()
            if ROOT in asset.parents and asset.exists() and asset.is_file():
                data = asset.read_bytes()
                content_type = {
                    ".svg": "image/svg+xml",
                    ".png": "image/png",
                    ".jpg": "image/jpeg",
                    ".jpeg": "image/jpeg",
                    ".webp": "image/webp",
                    ".js": "text/javascript",
                }.get(asset.suffix.lower(), "application/octet-stream")
                self.send_response(HTTPStatus.OK)
                self.send_cors_headers()
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self):
        parsed = urlparse(self.path)
        try:
            payload = self.read_json()
            if parsed.path == "/api/login":
                user = authenticate(payload.get("email"), payload.get("password"))
                if not user:
                    self.send_json({"error": "Invalid user id or password"}, HTTPStatus.UNAUTHORIZED)
                    return
                token = secrets.token_urlsafe(32)
                SESSIONS[token] = user
                self.send_json({"token": token, "user": {k: user[k] for k in ("email", "name", "brands", "locations")}})
                return

            user = self.session_user()
            if not user:
                self.send_json({"error": "Session expired. Please login again."}, HTTPStatus.UNAUTHORIZED)
                return

            if parsed.path == "/api/report":
                self.send_json(build_report(user, payload.get("brand"), payload.get("filters") or {}, payload.get("reportType") or "location"))
                return

            self.send_error(HTTPStatus.NOT_FOUND)
        except Exception as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)


if __name__ == "__main__":
    print(f"React dashboard running at http://{HOST}:{PORT}")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
