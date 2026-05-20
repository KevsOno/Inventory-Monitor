
# Multi‑Branch Inventory Intelligence System

[![Live App](https://img.shields.io/badge/Streamlit-App-FF4B4B)](https://inventory-monitor.streamlit.app)
[![Supabase](https://img.shields.io/badge/Supabase-PostgreSQL-3FCF8E)](https://supabase.com)

A production‑hardened inventory system that handles **36,000+ SKUs** across multiple branches. Built for **Penafort Energy** to reduce expiry write‑offs and automate inter‑branch transfers – running on free‑tier infrastructure.

**Live demo:** [inventory-monitor.streamlit.app](https://inventory-monitor.streamlit.app)

---

## ✨ Features

- **Dashboard** – Total inventory value + 30‑day waste risk, alert compliance.
- **FEFO batch prioritisation** – First Expired, First Out with a **90‑day write‑off threshold** (realistic for retail).
- **AI‑computed stock limits** – Reorder point, safety stock, max stock recalculated daily from sales velocity.
- **Automated alerts** – Email alerts for batches ≤90 days to expiry, one‑click “Mark Done” via signed URL.
- **Inter‑branch transfer suggestions** – Two types:
  - **Surplus → Deficit** (quantity‑based)
  - **Expiry risk** (batches ≤30 days in slow‑selling branches → higher‑demand branch)
- **Execute transfer** – One‑click execution records stock movements and updates inventory; the system automatically learns from it.
- **Role‑based access** – Admin (full edit, can execute transfers) / Viewer (read‑only).
- **CSV upload** – Chunked inserts (500 rows), downloadable templates, and **auto‑creation of missing products**.
- **User‑friendly sorting** – In Risk & FEFO: “Highest risk first”, “Earliest expiry first”, “Highest financial value first”.
- **Pagination everywhere** – Server‑side offset with cached exact counts for fast navigation.

---

## 🧠 Architecture

**Streamlit (presentation) ←→ Supabase (computation)**

All heavy computation lives in PostgreSQL:
- `view_inventory_list`, `view_risk_list`, `view_transfer_suggestions`, `view_expiry_transfer_suggestions`, `view_all_transfer_suggestions` – database views.
- Daily maintenance (stock limits, risk scores, alerts) – **PostgreSQL function** (`daily_inventory_maintenance()`) scheduled with `pg_cron`.
- Dashboard aggregates – RPC functions.

Streamlit is a thin, memory‑safe presentation layer.

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | Streamlit (Python) |
| Database | Supabase (PostgreSQL 15) |
| Auth | Streamlit secrets + two‑password scheme |
| Scheduling | `pg_cron` (PostgreSQL extension) |
| Deployment | Streamlit Cloud (free tier) |

---

## 📦 Setup

### 1. Clone & install

```bash
git clone https://github.com/yourusername/inventory-monitor.git
cd inventory-monitor
pip install -r requirements.txt
```

### 2. Configure Supabase

- Create a Supabase project.
- Run the SQL scripts in [`setup.sql`](setup.sql) to create tables, views, functions, and indexes.
- Enable the `pg_cron` extension.
- Create the `daily_inventory_maintenance()` function (included in `setup.sql`).
- Run `SELECT daily_inventory_maintenance();` once to populate initial risk scores.
- (Optional) Schedule the function to run daily:
  ```sql
  SELECT cron.schedule('daily-inventory-maintenance', '0 2 * * *', 'SELECT daily_inventory_maintenance();');
  ```

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

Connect your GitHub repo, add the same secrets, and deploy.

---

## ⚙️ Performance Optimisations (v2+)

After initial prototype, the system was hardened for scale:

- **Database views** – eliminated client‑side joins & pandas flattening.
- **Pagination + cached exact counts** – no `COUNT(*)` on every page.
- **Chunked SKU lookup** – avoids URL length errors for large CSV uploads.
- **Auto‑creation of missing products** – inventory upload never fails.
- **Date serialisation** – fixed “date not JSON serializable” errors.
- **Integer conversion** – prevents `invalid input syntax for type integer` (e.g., `0.0` → `0`).
- **Combined transfer suggestions** – surplus/deficit + expiry‑based, united in a single view.
- **Execute transfer with stock movement logging** – complete feedback loop; system learns from executed transfers.
- **User‑friendly sort labels** – non‑technical users can sort intuitively.
- **Role‑based UI** – viewers see suggestions but cannot execute transfers.

Result: Handles 36k SKUs, 100k+ inventory rows, multiple concurrent users on free tiers.

---

## 🧪 Testing

- 36,000 synthetic SKUs + 100,000 inventory rows.
- Pagination response <200ms.
- CSV upload of 10,000 rows succeeds without timeout.
- All database constraints and foreign keys validated.

---

## 📝 Limitations & Future Work

- **Atomic CSV uploads** – partial chunk failure leaves previous chunks committed. Fix: staging table + transaction.
- **Keyset pagination** – for extremely deep pages (offset >10,000) – not yet needed.
- **Real‑time POS integration** – currently relies on CSV exports from the mall ERP.

---

## 👤 Author

**Oghenekevbe Michael Onoriode**  
[Portfolio](https://kevs-ono-portfolio.netlify.app) · [GitHub](https://github.com/kevsono) · [LinkedIn](https://linkedin.com/in/kevsono)

Built for **Penafort Energy** as part of operational infrastructure modernisation.

---

## 📄 License

MIT
