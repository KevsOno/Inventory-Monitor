import streamlit as st
import pandas as pd
from supabase import create_client, Client
import uuid
from datetime import date

# ---------- CONFIG ----------
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------- AUTH LIGHT (simple password) ----------
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    pwd = st.text_input("Enter access password", type="password")
    if pwd == st.secrets.get("APP_PASSWORD", "changeme"):
        st.session_state.authenticated = True
        st.rerun()
    else:
        st.stop()

# ---------- BRANCH SELECTOR ----------
branches = supabase.table("branches").select("*").execute().data
branch_options = {b['code']: b['id'] for b in branches}
branch_names = [b['name'] for b in branches]
selected_branch_name = st.sidebar.selectbox("Select Branch", ["All Branches"] + branch_names)
if selected_branch_name == "All Branches":
    branch_id = None
else:
    branch_id = branch_options[[b['code'] for b in branches if b['name'] == selected_branch_name][0]]

# ---------- SIDEBAR NAVIGATION ----------
page = st.sidebar.radio("Go to", ["CSV Upload", "Inventory", "Alert Dashboard", "AI Limits"])

# ---------- HELPER FUNCTIONS ----------
def upload_csv_to_table(table_name, df, extra_columns={}):
    """Upsert CSV dataframe into Supabase. df must match table columns."""
    for col, val in extra_columns.items():
        df[col] = val
    records = df.to_dict(orient="records")
    res = supabase.table(table_name).insert(records).execute()
    return res

# ---------- PAGE: CSV UPLOAD ----------
if page == "CSV Upload":
    st.header("📁 Upload Data via CSV")

    upload_type = st.selectbox("What are you uploading?", 
                               ["Inventory (current stock)", "Stock Movements (sales/restock)"])
    st.markdown("Download template: [Template CSV](https://example.com) (coming in repo)")

    uploaded_file = st.file_uploader("Choose CSV", type="csv")
    if uploaded_file:
        df = pd.read_csv(uploaded_file)
        st.dataframe(df.head())

        if upload_type == "Inventory (current stock)":
            # Expected columns: product_sku, batch, quantity, expiry_date, storage_location
            # Need to map product_sku to product_id
            skus = df['product_sku'].unique()
            products = supabase.table("products").select("id, sku").in_("sku", list(skus)).execute().data
            sku_to_id = {p['sku']: p['id'] for p in products}
            df['product_id'] = df['product_sku'].map(sku_to_id)
            if df['product_id'].isna().any():
                st.error("Some SKUs not found in products master. Add them first.")
                st.stop()
            df['branch_id'] = branch_id if branch_id else st.selectbox("Select branch for data", [b['name'] for b in branches])
            # Convert expiry_date to date
            df['expiry_date'] = pd.to_datetime(df['expiry_date']).dt.date
            df = df[['branch_id', 'product_id', 'batch', 'quantity', 'expiry_date', 'storage_location']]
            if st.button("Upload Inventory"):
                upload_csv_to_table("inventory", df)
                st.success("Inventory uploaded successfully!")

        else:  # Stock Movements
            # Expected: product_sku, quantity_change, movement_date
            skus = df['product_sku'].unique()
            products = supabase.table("products").select("id, sku").in_("sku", list(skus)).execute().data
            sku_to_id = {p['sku']: p['id'] for p in products}
            df['product_id'] = df['product_sku'].map(sku_to_id)
            if df['product_id'].isna().any():
                st.error("Some SKUs not found.")
                st.stop()
            df['branch_id'] = branch_id if branch_id else st.selectbox("Select branch", [b['name'] for b in branches])
            df['movement_date'] = pd.to_datetime(df['movement_date']).dt.date
            df = df[['branch_id', 'product_id', 'quantity_change', 'movement_date', 'notes']]
            if st.button("Upload Movements"):
                upload_csv_to_table("stock_movements", df)
                st.success("Movements uploaded!")

# ---------- PAGE: INVENTORY (VIEW & MANUAL ENTRY) ----------
elif page == "Inventory":
    st.header("📦 Current Inventory")
    query = supabase.table("inventory").select("*, products(name, sku), branches(name)")
    if branch_id:
        query = query.eq("branch_id", branch_id)
    inventory_data = query.execute().data
    if inventory_data:
        df_inv = pd.DataFrame(inventory_data)
        # Flatten nested
        df_inv['product_name'] = df_inv['products'].apply(lambda x: x['name'])
        df_inv['branch_name'] = df_inv['branches'].apply(lambda x: x['name'])
        df_inv = df_inv[['branch_name', 'product_name', 'batch', 'quantity', 'expiry_date', 'storage_location']]
        st.dataframe(df_inv)
    else:
        st.write("No inventory data.")

    st.subheader("➕ Manual Entry (single item)")
    with st.form("manual_inv"):
        branch_name = st.selectbox("Branch", branch_names) if not branch_id else selected_branch_name
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
                br = [b for b in branches if b['name'] == branch_name][0]
                supabase.table("inventory").insert({
                    "branch_id": br['id'],
                    "product_id": product.data[0]['id'],
                    "batch": batch,
                    "quantity": quantity,
                    "expiry_date": expiry_date.isoformat(),
                    "storage_location": location
                }).execute()
                st.success("Added!")

# ---------- PAGE: ALERT DASHBOARD ----------
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
        alert_id = st.selectbox("Select Alert ID", [a['id'] for a in alerts])
        action_text = st.text_input("Action taken description")
        if st.button("Mark Done"):
            supabase.table("alert_log").update({"action_taken": action_text, "action_date": "now()"}).eq("id", alert_id).execute()
            st.success("Logged.")
    else:
        st.write("No alerts. Great job!")

# ---------- PAGE: AI LIMITS ----------
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
        st.write("No limits computed yet. Run the daily job or wait for the scheduled function.")
