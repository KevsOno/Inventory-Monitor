import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import date, datetime

# ---------- CONFIG ----------
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------- AUTH ----------
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    pwd = st.text_input("Enter access password", type="password")
    if pwd == st.secrets.get("APP_PASSWORD", "changeme"):
        st.session_state.authenticated = True
        st.rerun()
    else:
        st.stop()

# ---------- EMAIL LINK AUTO-MARK (One-Click Done from Email) ----------
params = st.query_params
if "alert_id" in params and "action" in params:
    # params["alert_id"] is a list in Streamlit's query_params, take the first element
    alert_id = params["alert_id"][0] if isinstance(params["alert_id"], list) else params["alert_id"]
    supabase.table("alert_log").update({
        "action_taken": "Marked done via email link",
        "action_date": "now()"
    }).eq("id", alert_id).execute()
    st.success(f"✅ Alert #{alert_id} marked as done!")
    st.query_params.clear()
    st.rerun()

# ---------- GLOBAL BRANCH SELECTOR ----------
branches_data = supabase.table("branches").select("*").execute().data
branch_options = {b['code']: b['id'] for b in branches_data}
branch_names = [b['name'] for b in branches_data]

selected_branch_name = st.sidebar.selectbox("Select Branch", ["All Branches"] + branch_names)
if selected_branch_name == "All Branches":
    branch_id = None
else:
    branch_id = next(b['id'] for b in branches_data if b['name'] == selected_branch_name)

# ---------- NAVIGATION ----------
page = st.sidebar.radio("Go to", [
    "Dashboard",
    "Branches",
    "Products",
    "Inventory",
    "CSV Upload",
    "Alerts & Advisories",
    "AI Limits"
])

# ---------- HELPERS ----------
def validate_csv_columns(df, required_cols, label="CSV"):
    """Check required columns, return (is_valid, message)."""
    missing = required_cols - set(df.columns)
    if missing:
        return False, f"❌ Missing columns in {label}: {', '.join(missing)}\n\n📋 Required: {', '.join(required_cols)}"
    return True, ""

def upload_csv_to_table(table_name, df, extra_columns={}):
    """Insert a DataFrame into a Supabase table."""
    for col, val in extra_columns.items():
        df[col] = val
    records = df.to_dict(orient="records")
    try:
        res = supabase.table(table_name).insert(records).execute()
        return res
    except Exception as e:
        st.error(f"Error inserting into {table_name}: {e}")
        return None

# ============================================================
# PAGE: DASHBOARD (KPIs, Waste, Transfer suggestions not shown)
# ============================================================
if page == "Dashboard":
    st.header("📊 Executive Summary")

    # Fetch data with cost
    inv_query = supabase.table("inventory").select("product_id, quantity, products(cost)")
    alert_query = supabase.table("alert_log").select("*, products(cost)")

    if branch_id:
        inv_query = inv_query.eq("branch_id", branch_id)
        alert_query = alert_query.eq("branch_id", branch_id)

    inv = inv_query.execute().data
    alerts = alert_query.execute().data

    if alerts:
        df_a = pd.DataFrame(alerts)
        total_alerts = len(df_a)

        # Wastage value
        expiring = df_a[df_a['alert_type'] == 'EXPIRY']
        inv_df = pd.DataFrame(inv) if inv else pd.DataFrame()
        wastage_val = 0
        if not inv_df.empty:
            for _, row in expiring.iterrows():
                qty = inv_df[inv_df['product_id'] == row['product_id']]['quantity'].sum()
                cost = row['products']['cost'] if row['products'] else 0
                wastage_val += qty * cost

        # Metrics
        stockout = len(df_a[df_a['alert_type'] == 'RESTOCK'])
        dead_stock = len(df_a[df_a['alert_type'] == 'DEAD_STOCK'])
        actioned = len(df_a[df_a['action_taken'].notna()])
        compliance = round((actioned / total_alerts * 100), 1) if total_alerts else 0

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Waste Risk", f"₦{wastage_val:,.0f}")
        c2.metric("Stock‑out Risks", stockout)
        c3.metric("Dead Stock", dead_stock)
        c4.metric("Actions Done", f"{compliance}%")

        st.subheader("Alert Type Breakdown")
        st.bar_chart(df_a['alert_type'].value_counts())
    else:
        st.info("No alert data available yet. Run the daily Edge Function to generate alerts.")

# ============================================================
# PAGE: BRANCHES (multi‑role emails, CSV upload)
# ============================================================
elif page == "Branches":
    st.header("🏢 Branch Management")

    # Display existing
    st.subheader("Current Branches")
    all_branches = supabase.table("branches").select("*").execute().data
    if all_branches:
        df_b = pd.DataFrame(all_branches)
        display_cols = ['name','code','storekeeper_email','procurement_email','inventory_email','auditor_email','manager_email']
        st.dataframe(df_b[display_cols].rename(columns={
            'name':'Name', 'code':'Code', 'storekeeper_email':'Storekeeper', 'procurement_email':'Procurement',
            'inventory_email':'Inventory', 'auditor_email':'Auditor', 'manager_email':'Manager'
        }))
    else:
        st.info("No branches yet.")

    st.markdown("---")

    # Manual entry
    st.subheader("➕ Add Single Branch")
    with st.form("add_branch_form"):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Branch Name*")
            code = st.text_input("Branch Code* (e.g., LG01)")
        with col2:
            storekeeper_email = st.text_input("Storekeeper Email")
            procurement_email = st.text_input("Procurement Email")
            inventory_email = st.text_input("Inventory Email")
            auditor_email = st.text_input("Auditor Email")
        submitted = st.form_submit_button("Add Branch")
        if submitted:
            if not name or not code:
                st.error("Name and code are required.")
            else:
                try:
                    supabase.table("branches").insert({
                        "name": name,
                        "code": code,
                        "storekeeper_email": storekeeper_email or None,
                        "procurement_email": procurement_email or None,
                        "inventory_email": inventory_email or None,
                        "auditor_email": auditor_email or None
                    }).execute()
                    st.success(f"Branch '{name}' added.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed: {e}")

    st.markdown("---")

    # CSV Upload
    st.subheader("📁 Upload Branches CSV")
    st.markdown("**CSV columns:** `name`, `code`, `storekeeper_email`, `procurement_email`, `inventory_email`, `auditor_email`")
    template_df = pd.DataFrame(columns=['name','code','storekeeper_email','procurement_email','inventory_email','auditor_email'])
    csv = template_df.to_csv(index=False)
    st.download_button("📥 Download Branch Template", csv, "branches_template.csv", "text/csv")

    uploaded_file = st.file_uploader("Choose branches CSV", type="csv", key="branches_csv")
    if uploaded_file:
        df = pd.read_csv(uploaded_file)
        st.dataframe(df.head())
        required = {'name','code'}
        is_valid, msg = validate_csv_columns(df, required, "branches CSV")
        if not is_valid:
            st.error(msg)
            st.stop()
        # Fill missing optional columns
        for col in ['storekeeper_email','procurement_email','inventory_email','auditor_email']:
            if col not in df.columns:
                df[col] = None
        if st.button("Upload Branches"):
            records = df[['name','code','storekeeper_email','procurement_email','inventory_email','auditor_email']].to_dict(orient="records")
            try:
                supabase.table("branches").insert(records).execute()
                st.success("Branches uploaded!")
                st.rerun()
            except Exception as e:
                st.error(f"Upload failed: {e}")

# ============================================================
# PAGE: PRODUCTS (cost, shelf life, CSV upload with template)
# ============================================================
elif page == "Products":
    st.header("📦 Products Master")

    # Display current
    st.subheader("Current Products")
    prods = supabase.table("products").select("*").execute().data
    if prods:
        df_p = pd.DataFrame(prods)
        st.dataframe(df_p[['sku','name','category','shelf_life_days','cost']].rename(columns={
            'sku':'SKU','name':'Name','category':'Category','shelf_life_days':'Shelf Life (days)','cost':'Unit Cost (₦)'
        }))
    else:
        st.info("No products yet.")

    st.markdown("---")

    # Manual Entry
    st.subheader("➕ Add Single Product")
    with st.form("add_product_form"):
        col1, col2 = st.columns(2)
        with col1:
            sku = st.text_input("SKU*")
            name = st.text_input("Product Name*")
            category = st.text_input("Category")
        with col2:
            shelf_life = st.number_input("Shelf Life (days)", min_value=1, value=90)
            cost = st.number_input("Unit Cost (₦)", min_value=0.0, value=0.0, format="%.2f")
        submitted = st.form_submit_button("Add Product")
        if submitted:
            if not sku or not name:
                st.error("SKU and name are required.")
            else:
                try:
                    supabase.table("products").insert({
                        "sku": sku,
                        "name": name,
                        "category": category or None,
                        "shelf_life_days": shelf_life,
                        "cost": cost
                    }).execute()
                    st.success(f"Product '{name}' added.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed: {e}")

    st.markdown("---")

    # CSV Upload
    st.subheader("📁 Upload Products CSV")
    st.markdown("**CSV columns:** `sku`, `name`, `category`, `shelf_life_days`, `cost`")
    template_p = pd.DataFrame(columns=['sku','name','category','shelf_life_days','cost'])
    csv_p = template_p.to_csv(index=False)
    st.download_button("📥 Download Product Template", csv_p, "products_template.csv", "text/csv")

    uploaded_file = st.file_uploader("Choose products CSV", type="csv", key="products_csv")
    if uploaded_file:
        df = pd.read_csv(uploaded_file)
        st.dataframe(df.head())
        required = {'sku','name'}
        is_valid, msg = validate_csv_columns(df, required, "products CSV")
        if not is_valid:
            st.error(msg)
            st.stop()
        # Fill missing optional columns
        if 'category' not in df.columns:
            df['category'] = None
        if 'shelf_life_days' not in df.columns:
            df['shelf_life_days'] = 90
        if 'cost' not in df.columns:
            df['cost'] = 0.0
        if st.button("Upload Products"):
            records = df[['sku','name','category','shelf_life_days','cost']].to_dict(orient="records")
            try:
                supabase.table("products").insert(records).execute()
                st.success("Products uploaded!")
                st.rerun()
            except Exception as e:
                st.error(f"Upload failed: {e}")

# ============================================================
# PAGE: INVENTORY (view only, manual entry optional but kept minimal)
# ============================================================
elif page == "Inventory":
    st.header("📦 Current Inventory")

    query = supabase.table("inventory").select("*, products(name, sku, cost), branches(name)")
    if branch_id:
        query = query.eq("branch_id", branch_id)
    inv_data = query.execute().data

    if inv_data:
        df_i = pd.DataFrame(inv_data)
        df_i['product'] = df_i['products'].apply(lambda x: x['name'] if x else '')
        df_i['branch'] = df_i['branches'].apply(lambda x: x['name'] if x else '')
        st.dataframe(df_i[['branch','product','batch','quantity','expiry_date','storage_location']])
    else:
        st.info("No inventory records found.")

    # A quick manual entry form (single item)
    st.subheader("➕ Quick Manual Entry (one item)")
    with st.form("manual_inv"):
        prod_sku = st.text_input("Product SKU")
        batch = st.text_input("Batch")
        qty = st.number_input("Quantity", min_value=0)
        exp_date = st.date_input("Expiry Date", min_value=date.today())
        location = st.selectbox("Storage Location", ["warehouse", "shelf", "cold_room"])
        if st.form_submit_button("Add Item"):
            if not prod_sku:
                st.error("SKU required.")
            else:
                prod_res = supabase.table("products").select("id").eq("sku", prod_sku).execute()
                if not prod_res.data:
                    st.error("Product not found.")
                else:
                    br_id = branch_id if branch_id else st.selectbox("Branch", branch_names)
                    # If All Branches is selected, need to pick a branch
                    if not br_id:
                        br_id = branch_options[[b['code'] for b in branches_data if b['name'] == br_id][0]]
                    supabase.table("inventory").insert({
                        "branch_id": br_id,
                        "product_id": prod_res.data[0]['id'],
                        "batch": batch,
                        "quantity": qty,
                        "expiry_date": exp_date.isoformat() if exp_date else None,
                        "storage_location": location
                    }).execute()
                    st.success("Item added!")
                    st.rerun()

# ============================================================
# PAGE: CSV UPLOAD (Inventory / Movements)
# ============================================================
elif page == "CSV Upload":
    st.header("📁 Upload Inventory or Movement Data")
    upload_type = st.selectbox("Data Type", ["Inventory (current stock)", "Stock Movements (sales/restock)"])

    # Determine branch
    if branch_id:
        selected_branch_id = branch_id
        selected_branch_label = selected_branch_name
    else:
        branch_list = supabase.table("branches").select("id,name").execute().data
        branch_map = {b['name']: b['id'] for b in branch_list}
        selected_branch_label = st.selectbox("Select branch for data", list(branch_map.keys()))
        selected_branch_id = branch_map[selected_branch_label]

    uploaded_file = st.file_uploader("Choose CSV", type="csv", key="data_csv")
    if uploaded_file:
        df = pd.read_csv(uploaded_file)
        st.dataframe(df.head())

        if upload_type == "Inventory (current stock)":
            required_cols = {'product_sku','batch','quantity','expiry_date','storage_location'}
            is_valid, msg = validate_csv_columns(df, required_cols, "inventory CSV")
            if not is_valid:
                st.error(msg)
                st.stop()
            # SKU resolution
            skus = df['product_sku'].unique().tolist()
            products_data = supabase.table("products").select("id, sku").in_("sku", skus).execute().data
            sku_to_id = {p['sku']: p['id'] for p in products_data}
            df['product_id'] = df['product_sku'].map(sku_to_id)
            missing = df[df['product_id'].isna()]['product_sku'].unique()
            if len(missing) > 0:
                st.error(f"❌ These SKUs not found in products: {missing}. Add them first.")
                st.stop()
            df['branch_id'] = selected_branch_id
            df['expiry_date'] = pd.to_datetime(df['expiry_date']).dt.date
            df = df[['branch_id','product_id','batch','quantity','expiry_date','storage_location']]
            if st.button("Upload Inventory"):
                res = upload_csv_to_table("inventory", df)
                if res:
                    st.success(f"Inventory uploaded for {selected_branch_label}!")
        else:
            required_cols = {'product_sku','quantity_change','movement_date'}
            is_valid, msg = validate_csv_columns(df, required_cols, "movements CSV")
            if not is_valid:
                st.error(msg)
                st.stop()
            skus = df['product_sku'].unique().tolist()
            products_data = supabase.table("products").select("id, sku").in_("sku", skus).execute().data
            sku_to_id = {p['sku']: p['id'] for p in products_data}
            df['product_id'] = df['product_sku'].map(sku_to_id)
            missing = df[df['product_id'].isna()]['product_sku'].unique()
            if len(missing) > 0:
                st.error(f"❌ These SKUs not found: {missing}")
                st.stop()
            df['branch_id'] = selected_branch_id
            df['movement_date'] = pd.to_datetime(df['movement_date']).dt.date
            if 'notes' not in df.columns:
                df['notes'] = ""
            df = df[['branch_id','product_id','quantity_change','movement_date','notes']]
            if st.button("Upload Movements"):
                res = upload_csv_to_table("stock_movements", df)
                if res:
                    st.success(f"Movements uploaded for {selected_branch_label}!")

# ============================================================
# PAGE: ALERTS & ADVISORIES
# ============================================================
elif page == "Alerts & Advisories":
    st.header("🚨 Alerts & Advisories")

    query = supabase.table("alert_log").select("*, products(name), branches(name)")
    if branch_id:
        query = query.eq("branch_id", branch_id)
    alerts = query.order("created_at", desc=True).execute().data

    if alerts:
        df_al = pd.DataFrame(alerts)
        df_al['product'] = df_al['products'].apply(lambda x: x['name'] if x else '')
        df_al['branch'] = df_al['branches'].apply(lambda x: x['name'] if x else '')
        st.dataframe(df_al[['branch','product','batch','alert_type','details','action_taken','created_at']])

        st.subheader("Manual Action Update")
        # Only unactioned alerts for selection
        unactioned = [a for a in alerts if not a.get('action_taken')]
        if unactioned:
            alert_id = st.selectbox("Select Alert ID", [a['id'] for a in unactioned])
            action_text = st.text_input("Action Description")
            if st.button("Mark Done"):
                supabase.table("alert_log").update({
                    "action_taken": action_text,
                    "action_date": "now()"
                }).eq("id", alert_id).execute()
                st.success("Marked as done.")
                st.rerun()
        else:
            st.info("All alerts have been actioned.")
    else:
        st.info("No alerts available. Good job!")

# ============================================================
# PAGE: AI LIMITS (Self-Learning)
# ============================================================
elif page == "AI Limits":
    st.header("📊 AI-Computed Stock Limits")
    st.caption("These limits are automatically updated daily based on sales velocity.")

    lim_query = supabase.table("stock_limits").select("*, products(name), branches(name)")
    if branch_id:
        lim_query = lim_query.eq("branch_id", branch_id)
    limits = lim_query.execute().data

    if limits:
        df_l = pd.DataFrame(limits)
        df_l['product'] = df_l['products'].apply(lambda x: x['name'] if x else '')
        df_l['branch'] = df_l['branches'].apply(lambda x: x['name'] if x else '')
        st.dataframe(df_l[['branch','product','avg_daily_demand','safety_stock','reorder_point','max_stock','calculated_at']])
    else:
        st.info("No AI limits computed yet. Ensure the Edge Function has run and stock movements exist.")
