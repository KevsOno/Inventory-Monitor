
# Multi‑Branch Inventory Intelligence System

[![Live App](https://img.shields.io/badge/Streamlit-App-FF4B4B)](https://inventory-monitor.streamlit.app)
[![Supabase](https://img.shields.io/badge/Supabase-PostgreSQL-3FCF8E)](https://supabase.com)

A production‑hardened inventory system that handles **36,000+ SKUs** across multiple branches. Built for **Penafort Energy** to reduce expiry write‑offs and automate inter‑branch transfers – running on free‑tier infrastructure.

**Live demo:** [inventory-monitor.streamlit.app](https://inventory-monitor.streamlit.app)

---

## Features

- **Dashboard** – Total inventory value + 30‑day waste risk.
- **FEFO batch prioritisation** – First Expired, First Out with **90‑day write‑off threshold**.
- **AI‑computed stock limits** – Reorder point, safety stock, max stock based on sales velocity.
- **Automated alerts** – Email alerts for batches ≤90 days to expiry, one‑click “mark done”.
- **Inter‑branch transfer suggestions** – Database‑driven surplus → deficit logic.
- **Role‑based access** – Admin (edit) / Viewer (read‑only).
- **CSV upload** – Chunked inserts (500 rows), downloadable templates.
- **Pagination everywhere** – Server‑side offset with cached exact counts.

---

## Architecture

**Streamlit (presentation) ←→ Supabase (computation)**

All heavy computation lives in PostgreSQL:
- `view_risk_list`, `view_transfer_suggestions`, `view_inventory_list` – database views.
- Daily maintenance (stock limits, risk scores, alerts) – Edge Function + pg_cron.
- Dashboard aggregates – RPC functions.

Streamlit is a thin, memory‑safe presentation layer.

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | Streamlit |
| Database | Supabase (PostgreSQL) |
| Auth | Streamlit secrets + two passwords |
| Scheduling | Supabase Edge Functions + pg_cron |
| Deployment | Streamlit Cloud (free tier) |

---

## Setup

### 1. Clone & install

```bash
git clone https://github.com/yourusername/inventory-monitor.git
cd inventory-monitor
pip install -r requirements.txt
```

### 2. Configure Supabase

- Create a Supabase project.
- Run the SQL scripts in [`setup.sql`](setup.sql) to create tables, views, functions, indexes.
- Enable `pg_cron` extension.
- Deploy the Edge Function `daily-inventory-maintenance`.
- Run `SELECT daily_inventory_maintenance();` once to populate risk scores.

### 3. Set Streamlit secrets

Create `.streamlit/secrets.toml`:

```toml
SUPABASE_URL = "your_supabase_url"
SUPABASE_KEY = "your_supabase_anon_key"
APP_PASSWORD = "admin_password"
VIEWER_PASSWORD = "viewer_password"
```

### 4. Run locally

```bash
streamlit run app.py
```

### 5. Deploy to Streamlit Cloud

Connect your GitHub repo, add the same secrets, deploy.

---

## Performance Optimisations (v2)

After initial prototype, the system was hardened for scale:

- **Database views** – eliminated client‑side joins & pandas flattening.
- **Pagination + cached counts** – no `COUNT(*)` on every page.
- **Fixed division‑by‑zero** when product costs are zero.
- **Corrected UUID foreign keys** (integer → UUID).
- **90‑day expiry threshold** (realistic for retail).
- **Chunked CSV uploads** with partial‑failure protection.
- **Pagination reset** on branch switch.

Result: Handles 36k SKUs, 100k+ inventory rows, multiple concurrent users – on free tiers.

---

## Testing

- 36,000 synthetic SKUs + 100,000 inventory rows.
- Pagination response <200ms.
- CSV upload of 5,000 rows succeeds without timeout.

---

## Limitations & Future Work

- **Atomic CSV uploads** – partial chunk failure leaves previous chunks committed. Fix: staging table + transaction.
- **Keyset pagination** – for extremely deep pages (offset >10,000).
- **Real‑time POS integration** – currently relies on CSV exports from the mall ERP.

---

## Author

**Oghenekevbe Michael Onoriode**  
[Portfolio](https://kevs-ono-portfolio.netlify.app) · [GitHub](https://github.com/kevsono) · [LinkedIn](https://linkedin.com/in/kevsono)

Built for **Penafort Energy** as part of operational infrastructure modernisation.

---

## License

MIT

Just copy and paste this into your `README.md` file. The live app URL is now `inventory-monitor.streamlit.app`. You may still want to replace `yourusername` with your actual GitHub username in the clone URL, but that's optional.
