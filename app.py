import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import date

# ---------- CONFIG ----------
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------- SIMPLE PASSWORD AUTH ----------
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    pwd = st.text_input("Enter access password", type="password")
    if pwd == st.secrets.get("APP_PASSWORD", "changeme"):
        st.session_state.authenticated = True
        st.rerun()
    else:
        st.stop()

# ---------- BRANCH SELECTOR (global) ----------
branches_data = supabase.table("branches").select("*").execute().data
branch_options = {b['code']: b['id'] for b in branches_data}
branch_names = [b['name'] for b in branches_data]
selected_branch_name = st.sidebar.selectbox("Select Branch", ["All Branches"] + branch_names)
if selected_branch_name == "All Branches":
    branch_id = None
else:
    branch_id = branch_options[[b['code'] for b in branches_data if b['name'] == selected_branch_name][0]]

# ---------- SIDEBAR NAVIGATION ----------
page = st.sidebar.radio("Go to", [
    "Branches",
    "Products",
    "CSV Upload (Inventory/Movements)",
    "Inventory",
    "Alert Dashboard",
    "AI Limits"
])

# ---------- HELPER: Generic CSV uploader ----------
def upload_csv_to_table(table_name, df, extra_columns={}):
    """Insert a pandas DataFrame into a Supabase table."""
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
# PAGE: BRANCHES
# ============================================================
if page == "Branches":
    st.header("🏢 Branches / Tenants")

    # Display existing branches
    st.subheader("Current Branches")
    all_branches = supabase.table("branches").select("*").execute().data
    if all_branches:
        df_b = pd.DataFrame(all_branches)
        df_b = df_b.rename(columns={"name": "Name", "code": "Code", "manager_email": "Manager Email"})
        st.dataframe(df_b, use_container_width=True)
    else:
        st.info("No branches yet. Add one below.")

    st.markdown("---")

    # Manual Entry
    st.subheader("➕ Add Single Branch")
    with st.form("add_branch_form"):
        name = st.text_input("Branch Name*")
        code = st.text_input("Branch Code* (e.g., LG01)")
        email = st.text_input("Manager Email (for alerts)")
        submitted = st.form_submit_button("Add Branch")
        if submitted:
            if not name or not code:
                st.error("Name and code are required.")
            else:
                try:
                    supabase.table("branches").insert({
                        "name": name,
                        "code": code,
                        "manager_email": email or None
                    }).execute()
                    st.success(f"Branch '{name}' added.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed: {e}")

    st.markdown("---")

    # CSV Upload
    st.subheader("📁 Upload Branches CSV")
    st.markdown("CSV columns: `name`, `code`, `manager_email`")
    uploaded_file = st.file_uploader("Choose branches CSV", type="csv", key="branches_csv")
    if uploaded_file:
        df = pd.read_csv(uploaded_file)
        st.dataframe(df.head())
        if st.button("Upload Branches"):
            # Ensure required columns exist
            if not set(['name','code']).issubset(df.columns):
                st.error("CSV must contain 'name' and 'code' columns.")
            else:
                # Convert to list of dicts
                records = df[['name','code','manager_email']].to_dict(orient="records")
                try:
                    supabase.table("branches").insert(records).execute()
                    st.success("Branches uploaded successfully!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Upload failed: {e}")

# ============================================================
# PAGE: PRODUCTS
# ============================================================
elif page == "Products":
    st.header("📦 Products Master")

    # Display existing
    st.subheader("Current Products")
    all_products = supabase.table("products").select("*").execute().data
    if all_products:
        df_p = pd.DataFrame(all_products)
        df_p = df_p.rename(columns={
            "sku": "SKU",
            "name": "Name",
            "category": "Category",
            "shelf_life_days": "Shelf Life (days)"
        })
        st.dataframe(df_p, use_container_width=True)
    else:
        st.info("No products yet.")

    st.markdown("---")

    # Manual Entry
    st.subheader("➕ Add Single Product")
    with st.form("add_product_form"):
        sku = st.text_input("SKU*")
        name = st.text_input("Product Name*")
        category = st.text_input("Category")
        shelf_life = st.number_input("Shelf Life (days)", min_value=1, value=90)
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
                        "shelf_life_days": shelf_life
                    }).execute()
                    st.success(f"Product '{name}' added.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed: {e}")

    st.markdown("---")

    # CSV Upload
    st.subheader("📁 Upload Products CSV")
    st.markdown("CSV columns: `sku`, `name`, `category`, `shelf_life_days`")
    uploaded_file = st.file_uploader("Choose products CSV", type="csv", key="products_csv")
    if uploaded_file:
        df = pd.read_csv(uploaded_file)
        st.dataframe(df.head())
        if st.button("Upload Products"):
            if not set(['sku','name']).issubset(df.columns):
                st.error("CSV must contain 'sku' and 'name' columns.")
            else:
                # Fill missing optional columns
                if 'category' not in df.columns:
                    df['category'] = None
                if 'shelf_life_days' not in df.columns:
                    df['shelf_life_days'] = 90
                records = df[['sku','name','category','shelf_life_days']].to_dict(orient="records")
                try:
                    supabase.table("products").insert(records).execute()
                    st.success("Products uploaded successfully!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Upload failed: {e}")

# ============================================================
# PAGE: CSV UPLOAD (Inventory/Movements)
# ============================================================
elif page == "CSV Upload (Inventory/Movements)":
    st.header("📁 Upload Inventory or Movement Data")
    upload_type = st.selectbox("What are you uploading?", 
                               ["Inventory (current stock)", "Stock Movements (sales/restock)"])
    st.markdown("Download template: [Template CSV](https://example.com) (will be in repo)")

    uploaded_file = st.file_uploader("Choose CSV", type="csv", key="data_csv")
    if uploaded_file:
        df = pd.read_csv(uploaded_file)
        st.dataframe(df.head())

        # Resolve branch ID
        if branch_id:
            selected_branch_id = branch_id
        else:
            branch_list = supabase.table("branches").select("id,name").execute().data
            branch_map = {b['name']: b['id'] for b in branch_list}
            chosen = st.selectbox("Select branch for data", list(branch_map.keys()))
            selected_branch_id = branch_map[chosen]

        if upload_type == "Inventory (current stock)":
            # Expected columns: product_sku, batch, quantity, expiry_date, storage_location
            required = {'product_sku', 'batch', 'quantity', 'expiry_date', 'storage_location'}
            if not required.issubset(df.columns):
                st.error(f"CSV must have columns: {required}")
                st.stop()
            # Resolve SKU -> product_id
            skus = df['product_sku'].unique().tolist()
            products_data = supabase.table("products").select("id, sku").in_("sku", skus).execute().data
            sku_to_id = {p['sku']: p['id'] for p in products_data}
            df['product_id'] = df['product_sku'].map(sku_to_id)
            if df['product_id'].isna().any():
                missing = df[df['product_id'].isna()]['product_sku'].unique()
                st.error(f"These SKUs not found in products: {missing}. Add them first.")
                st.stop()
            df['branch_id'] = selected_branch_id
            df['expiry_date'] = pd.to_datetime(df['expiry_date']).dt.date
            # Keep only relevant columns
            df = df[['branch_id', 'product_id', 'batch', 'quantity', 'expiry_date', 'storage_location']]
            if st.button("Upload Inventory"):
                res = upload_csv_to_table("inventory", df)
                if res:
                    st.success("Inventory uploaded successfully!")

        else:  # Stock Movements
            # Expected: product_sku, quantity_change, movement_date, notes (optional)
            required = {'product_sku', 'quantity_change', 'movement_date'}
            if not required.issubset(df.columns):
                st.error(f"CSV must have columns: {required}")
                st.stop()
            skus = df['product_sku'].unique().tolist()
            products_data = supabase.table("products").select("id, sku").in_("sku", skus).execute().data
            sku_to_id = {p['sku']: p['id'] for p in products_data}
            df['product_id'] = df['product_sku'].map(sku_to_id)
            if df['product_id'].isna().any():
                missing = df[df['product_id'].isna()]['product_sku'].unique()
                st.error(f"These SKUs not found: {missing}")
                st.stop()
            df['branch_id'] = selected_branch_id
            df['movement_date'] = pd.to_datetime(df['movement_date']).dt.date
            # notes optional
            if 'notes' not in df.columns:
                df['notes'] = ""
            df = df[['branch_id', 'product_id', 'quantity_change', 'movement_date', 'notes']]
            if st.button("Upload Movements"):
                res = upload_csv_to_table("stock_movements", df)
                if res:
                    st.success("Movements uploaded!")

# ============================================================
# PAGE: INVENTORY
# ============================================================
elif page == "Inventory":
    st.header("📦 Current Inventory")
    query = supabase.table("inventory").select("*, products(name, sku), branches(name)")
    if branch_id:
        query = query.eq("branch_id", branch_id)
    inventory_data = query.execute().data
    if inventory_data:
        df_inv = pd.DataFrame(inventory_data)
        df_inv['product_name'] = df_inv['products'].apply(lambda x: x['name'])
        df_inv['branch_name'] = df_inv['branches'].apply(lambda x: x['name'])
        df_inv = df_inv[['branch_name', 'product_name', 'batch', 'quantity', 'expiry_date', 'storage_location']]
        st.dataframe(df_inv)
    else:
        st.write("No inventory data.")

    st.subheader("➕ Manual Entry")
    with st.form("manual_inv"):
        if branch_id:
            selected_br_name = selected_branch_name
        else:
            selected_br_name = st.selectbox("Branch", branch_names)
        product_sku = st.text_input("Product SKU")
        batch = st.text_input("Batch")
        quantity = st.number_input("Quantity", min_value=0)
        expiry_date = st.date_input("Expiry Date", min_value=date.today())
        location = st.selectbox("Storage Location", ["warehouse", "shelf", "cold_room"])
        if st.form_submit_button("Add Item"):
            # Resolve product and branch ids
            product = supabase.table("products").select("id").eq("sku", product_sku).execute()
            if not product.data:
                st.error("Product not found.")
            else:
                br_id = [b['id'] for b in branches_data if b['name'] == selected_br_name][0]
                supabase.table("inventory").insert({
                    "branch_id": br_id,
                    "product_id": product.data[0]['id'],
                    "batch": batch,
                    "quantity": quantity,
                    "expiry_date": expiry_date.isoformat() if expiry_date else None,
                    "storage_location": location
                }).execute()
                st.success("Added!")

# ============================================================
# PAGE: ALERT DASHBOARD
# ============================================================
elif page == "Alert Dashboard":
    st.header("🚨 Open Alerts & Advisories")
    query = supabase.table("alert_log").select("*, products(name, sku), branches(name)")
    if branch_id:
        query = query.eq("branch_id", branch_id)
    alerts = query.order("created_at", desc=True).execute().data
    if alerts:
        df_alerts = pd.DataFrame(alerts)
        df_alerts['product'] = df_alerts['products'].apply(lambda x: x['name'])
        df_alerts['branch'] = df_alerts['branches'].apply(lambda x: x['name'])
        df_alerts = df_alerts[['branch', 'product', 'batch', 'alert_type', 'details', 'action_taken', 'created_at']]
        st.dataframe(df_alerts)
        # Mark action taken
        st.subheader("Mark Action as Done")
        alert_ids = [a['id'] for a in alerts]
        alert_id = st.selectbox("Select Alert ID", alert_ids, format_func=lambda x: f"Alert {x}")
        action_text = st.text_input("Action taken description")
        if st.button("Mark Done"):
            supabase.table("alert_log").update({
                "action_taken": action_text,
                "action_date": "now()"
            }).eq("id", alert_id).execute()
            st.success("Logged. Refreshing...")
            st.rerun()
    else:
        st.info("No alerts. Great job!")

# ============================================================
# PAGE: AI LIMITS
# ============================================================
elif page == "AI Limits":
    st.header("📊 AI-Computed Stock Limits")
    query = supabase.table("stock_limits").select("*, products(name, sku), branches(name)")
    if branch_id:
        query = query.eq("branch_id", branch_id)
    limits = query.execute().data
    if limits:
        df_lim = pd.DataFrame(limits)
        df_lim['product'] = df_lim['products'].apply(lambda x: x['name'])
        df_lim['branch'] = df_lim['branches'].apply(lambda x: x['name'])
        df_lim = df_lim[['branch', 'product', 'avg_daily_demand', 'safety_stock', 'reorder_point', 'max_stock', 'calculated_at']]
        st.dataframe(df_lim)
    else:
        st.info("No limits computed yet. Run the daily scheduled Edge Function or wait for the next cycle.")
