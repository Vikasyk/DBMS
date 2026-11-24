"""
tamper_dataset.py
=================
Transforms the synthetic EPCIS food-supply-chain dataset into the
relational schema defined by the ER diagram:

  FARM → (Produces) → BATCH → (Undergoes) → QUALITY_CHECK
  BATCH → (Processes) → PROCESSING_FACILITY
  SHIPMENT → (Included_In) → BATCH
  SHIPMENT → (Receives) → RETAILER
  ANOMALY_ALERT → (Triggers) → SHIPMENT
  BATCH ← (Has) → PRICE_RECORD

Outputs: food-supply-chain-ER-dataset.xlsx  (one sheet per entity)
"""

import json, random, hashlib, re
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd

random.seed(42)

# ── paths ────────────────────────────────────────────────────────────────────
SRC = Path(r"C:\Users\User\Downloads\DBMS-main\DBMS-main\synthetic-food-supply-chain-dataset.json")
OUT = Path(r"C:\Users\User\Downloads\DBMS-main\DBMS-main\food-supply-chain-ER-dataset.xlsx")

print("Loading JSON …")
with open(SRC, encoding="utf-8") as f:
    doc = json.load(f)

events   = doc["epcisBody"]["eventList"]
vocabs   = doc["epcisHeader"]["epcisMasterData"]["vocabularyList"]

# ── helper data ───────────────────────────────────────────────────────────────
PRODUCT_NAMES = [
    "Wheat Grain","Basmati Rice","Corn Kernels","Soybeans","Sunflower Seeds",
    "Tomato Paste","Olive Oil","Canola Oil","Brown Sugar","White Sugar",
    "Whole Milk Powder","Cheese Block","Butter","Yogurt","Cream",
    "Chicken Breast","Beef Mince","Pork Loin","Salmon Fillet","Tuna Canned",
    "Apple Juice","Orange Juice","Mango Pulp","Coconut Water","Grape Juice",
    "Green Tea","Black Coffee","Cocoa Powder","Vanilla Extract","Chilli Sauce",
    "Pasta Penne","Noodles","Bread Loaf","Biscuits","Crackers",
    "Frozen Peas","Frozen Corn","Baby Spinach","Broccoli Florets","Carrots",
    "Groundnut Oil","Mustard Oil","Sesame Seeds","Turmeric Powder","Cumin Seeds",
    "Honey Jar","Jam Strawberry","Pickle Mango","Ketchup","Mayonnaise",
]

FOOD_CATEGORIES = [
    "Grains & Cereals","Dairy Products","Meat & Poultry","Seafood",
    "Fruits & Vegetables","Oils & Fats","Beverages","Processed Foods",
    "Condiments & Spices","Frozen Foods",
]

BIZ_STEPS_ROLE = {
    "collecting":    "FARM",
    "commissioning": "PROCESSING_FACILITY",
    "assembling":    "PROCESSING_FACILITY",
    "disassembling": "PROCESSING_FACILITY",
    "packing":       "PROCESSING_FACILITY",
    "shipping":      "SHIPMENT",
    "receiving":     "RETAILER",
    "installing":    "RETAILER",
}

CONTAMINATION_TYPES = [
    "None","Salmonella","E. coli","Listeria","Campylobacter",
    "Aflatoxin","Pesticide Residue","Heavy Metals","Foreign Object","Norovirus",
]
ALERT_TYPES = ["Temperature Exceedance","Delay Alert","Quality Failure","Contamination Detected","Quantity Mismatch"]
QC_STATUSES  = ["Pass","Fail","Conditional Pass","Pending Review"]
US_STATES    = ["California","Texas","Florida","New York","Illinois","Ohio","Georgia","Washington","Arizona","Colorado"]
CITIES_BY_STATE = {
    "California": ["Los Angeles","San Francisco","San Diego","Fresno","Sacramento"],
    "Texas":      ["Houston","Dallas","Austin","San Antonio","El Paso"],
    "Florida":    ["Miami","Orlando","Tampa","Jacksonville","Fort Lauderdale"],
    "New York":   ["New York City","Buffalo","Rochester","Albany","Syracuse"],
    "Illinois":   ["Chicago","Aurora","Rockford","Joliet","Springfield"],
    "Ohio":       ["Columbus","Cleveland","Cincinnati","Toledo","Akron"],
    "Georgia":    ["Atlanta","Savannah","Augusta","Macon","Columbus"],
    "Washington": ["Seattle","Spokane","Tacoma","Bellevue","Olympia"],
    "Arizona":    ["Phoenix","Tucson","Mesa","Chandler","Scottsdale"],
    "Colorado":   ["Denver","Colorado Springs","Aurora","Fort Collins","Boulder"],
}

SUPPLY_CHAIN_STAGES = ["Farm","Processing","Wholesale","Distribution","Retail"]

def rand_date(start="2024-01-01", end="2026-11-01"):
    s = datetime.strptime(start, "%Y-%m-%d")
    e = datetime.strptime(end,   "%Y-%m-%d")
    return s + timedelta(seconds=random.randint(0, int((e-s).total_seconds())))

def fmt_date(dt):  return dt.strftime("%Y-%m-%d")
def fmt_dt(dt):    return dt.strftime("%Y-%m-%d %H:%M:%S")

def short_hash(text, n=8):
    return hashlib.md5(text.encode()).hexdigest()[:n].upper()

def rand_phone():
    return f"+1-{random.randint(200,999)}-{random.randint(100,999)}-{random.randint(1000,9999)}"

def rand_pin():
    return str(random.randint(10000,99999))

def rand_state():
    return random.choice(US_STATES)

def rand_city(state):
    return random.choice(CITIES_BY_STATE.get(state, ["Anytown"]))

def rand_street():
    return f"{random.randint(1,9999)} {random.choice(['Main','Oak','Elm','Cedar','Maple','Farm','Industry','Commerce'])} {random.choice(['St','Ave','Blvd','Rd','Lane','Way'])}"

# ── parse location vocab ──────────────────────────────────────────────────────
loc_map = {}   # location_id -> dict of attrs
for vocab in vocabs:
    if "Location" in vocab["type"]:
        for elem in vocab["vocabularyElementList"]:
            lid  = elem["id"]
            attr = {a["id"]: a.get("attribute","") for a in elem.get("attributes",[])}
            loc_map[lid] = attr

# ── parse product vocab ───────────────────────────────────────────────────────
prod_map = {}  # epcClass_id -> short description
for vocab in vocabs:
    if "EPCClass" in vocab["type"]:
        for elem in vocab["vocabularyElementList"]:
            prod_map[elem["id"]] = elem.get("attributes",[{}])[0].get("attribute","")

# ── categorise events by bizStep ─────────────────────────────────────────────
farm_events        = [e for e in events if e.get("bizStep") == "collecting"]
processing_events  = [e for e in events if e.get("bizStep") in ("commissioning","assembling","disassembling","packing")]
shipping_events    = [e for e in events if e.get("bizStep") == "shipping"]
receiving_events   = [e for e in events if e.get("bizStep") == "receiving"]

print(f"farm:{len(farm_events)}  proc:{len(processing_events)}  ship:{len(shipping_events)}  recv:{len(receiving_events)}")

# ═══════════════════════════════════════════════════════════════════════════════
# 1.  FARM  (derived from "collecting" events + location vocab)
# ═══════════════════════════════════════════════════════════════════════════════
seen_farm_locs = set()
farm_rows = []

def make_farm(farm_id, loc_id, event_time_str):
    loc = loc_map.get(loc_id, {})
    state = loc.get("cbvmda:state", rand_state())
    if state not in CITIES_BY_STATE:
        state = rand_state()
    city = loc.get("cbvmda:city", rand_city(state))
    return {
        "Farm_ID":     farm_id,
        "Farm_Name":   loc.get("cbvmda:name", f"Farm-{farm_id}"),
        "Street":      loc.get("cbvmda:streetAddressOne", rand_street()),
        "City":        city,
        "State":       state,
        "PIN_Code":    loc.get("cbvmda:postalCode", rand_pin()),
        "Contact_No":  rand_phone(),
        "Location":    loc.get("cbvmda:geoLocation",""),
        "Country":     "US",
        "Registered_Date": fmt_date(rand_date("2015-01-01","2022-12-31")),
    }

farm_id_map = {}  # loc_id -> Farm_ID
for ev in farm_events:
    loc_id = ev.get("bizLocation",{}).get("id","")
    if loc_id and loc_id not in seen_farm_locs:
        seen_farm_locs.add(loc_id)
        fid = f"FARM-{len(farm_rows)+1:03d}"
        farm_id_map[loc_id] = fid
        farm_rows.append(make_farm(fid, loc_id, ev.get("eventTime","")))

df_farm = pd.DataFrame(farm_rows)
print(f"FARM: {len(df_farm)} rows")

# ═══════════════════════════════════════════════════════════════════════════════
# 2.  PROCESSING_FACILITY  (from commissioning / assembling / packing events)
# ═══════════════════════════════════════════════════════════════════════════════
seen_proc_locs = set()
proc_rows = []
proc_id_map = {}  # loc_id -> Facility_ID

for ev in processing_events:
    loc_id = ev.get("bizLocation",{}).get("id","")
    if loc_id and loc_id not in seen_proc_locs:
        seen_proc_locs.add(loc_id)
        loc    = loc_map.get(loc_id, {})
        state  = loc.get("cbvmda:state", rand_state())
        if state not in CITIES_BY_STATE:
            state = rand_state()
        city   = loc.get("cbvmda:city", rand_city(state))
        fid    = f"FAC-{len(proc_rows)+1:03d}"
        proc_id_map[loc_id] = fid
        proc_rows.append({
            "Facility_ID":   fid,
            "Facility_Name": loc.get("cbvmda:name", f"Processing-Facility-{fid}"),
            "Street":        loc.get("cbvmda:streetAddressOne", rand_street()),
            "City":          city,
            "State":         state,
            "PIN_Code":      loc.get("cbvmda:postalCode", rand_pin()),
            "Location":      loc.get("cbvmda:geoLocation",""),
            "Country":       "US",
            "Capacity_MT":   round(random.uniform(50,5000),1),
            "Cert_Standard": random.choice(["ISO 22000","HACCP","FSSC 22000","BRC","SQF"]),
        })

df_proc = pd.DataFrame(proc_rows)
print(f"PROCESSING_FACILITY: {len(df_proc)} rows")

# ═══════════════════════════════════════════════════════════════════════════════
# 3.  RETAILER  (from "receiving" events)
# ═══════════════════════════════════════════════════════════════════════════════
seen_ret_locs = set()
ret_rows = []
ret_id_map = {}  # loc_id -> Retailer_ID

for ev in receiving_events:
    loc_id = ev.get("bizLocation",{}).get("id","")
    if loc_id and loc_id not in seen_ret_locs:
        seen_ret_locs.add(loc_id)
        loc    = loc_map.get(loc_id, {})
        state  = loc.get("cbvmda:state", rand_state())
        if state not in CITIES_BY_STATE:
            state = rand_state()
        city   = loc.get("cbvmda:city", rand_city(state))
        rid    = f"RET-{len(ret_rows)+1:03d}"
        ret_id_map[loc_id] = rid
        ret_rows.append({
            "Retailer_ID":   rid,
            "Retailer_Name": loc.get("cbvmda:name", f"Retailer-{rid}"),
            "Street":        loc.get("cbvmda:streetAddressOne", rand_street()),
            "City":          city,
            "State":         state,
            "PIN_Code":      loc.get("cbvmda:postalCode", rand_pin()),
            "Contact_No":    rand_phone(),
            "Location":      loc.get("cbvmda:geoLocation",""),
            "Country":       "US",
            "Store_Type":    random.choice(["Supermarket","Hypermarket","Grocery Store","Online Retailer","Convenience Store"]),
        })

df_ret = pd.DataFrame(ret_rows)
print(f"RETAILER: {len(df_ret)} rows")

# ═══════════════════════════════════════════════════════════════════════════════
# 4.  BATCH  (one per unique epcClass seen across all events)
# ═══════════════════════════════════════════════════════════════════════════════
# Map epcClass → batch info (from quantityList of collecting/commissioning events)
epc_to_batch = {}   # epcClass -> batch_id
batch_rows   = []

def epc_to_batch_id(epc_class):
    if epc_class not in epc_to_batch:
        bid = f"BATCH-{len(epc_to_batch)+1:05d}"
        epc_to_batch[epc_class] = bid
    return epc_to_batch[epc_class]

# gather all epc classes
all_epc_classes = set()
for ev in events:
    for ql_key in ("quantityList","inputQuantityList","outputQuantityList","childQuantityList"):
        for q in ev.get(ql_key, []):
            all_epc_classes.add(q.get("epcClass",""))
all_epc_classes.discard("")

prod_name_list = list(prod_map.values())
food_product_pool = PRODUCT_NAMES * (len(all_epc_classes)//len(PRODUCT_NAMES) + 2)

for i, epc in enumerate(sorted(all_epc_classes)):
    bid = epc_to_batch_id(epc)
    prod_name = food_product_pool[i % len(food_product_pool)]
    prod_date = rand_date("2024-01-01","2026-10-01")
    shelf_days = random.randint(14, 365)
    expiry_date = prod_date + timedelta(days=shelf_days)
    now_date    = datetime(2026, 11, 23)
    shelf_rem   = max(0, (expiry_date - now_date).days)
    qty         = round(random.uniform(0.5, 500.0), 2)
    batch_rows.append({
        "Batch_ID":             bid,
        "EPC_Class_URI":        epc,
        "Product_Name":         prod_name,
        "Category":             random.choice(FOOD_CATEGORIES),
        "Production_Date":      fmt_date(prod_date),
        "Expiry_Date":          fmt_date(expiry_date),
        "Shelf_Life_Days":      shelf_days,
        "Shelf_Life_Remaining": shelf_rem,
        "Quantity":             qty,
        "Unit":                 random.choice(["LBS","KG","MT","CASES","UNITS"]),
        "Lot_Number":           f"LOT-{short_hash(epc)}",
        "Origin_Farm_ID":       random.choice(df_farm["Farm_ID"].tolist()) if not df_farm.empty else "",
        "Processed_By_Fac_ID":  random.choice(df_proc["Facility_ID"].tolist()) if not df_proc.empty else "",
    })

df_batch = pd.DataFrame(batch_rows)
print(f"BATCH: {len(df_batch)} rows")

# ═══════════════════════════════════════════════════════════════════════════════
# 5.  SHIPMENT  (from "shipping" events)
# ═══════════════════════════════════════════════════════════════════════════════
shipment_rows = []
ship_id_map   = {}   # eventID -> Shipment_ID

for ev in shipping_events:
    ev_id  = ev.get("eventID","")
    s_id   = f"SHIP-{len(shipment_rows)+1:05d}"
    ship_id_map[ev_id] = s_id
    src_id = ""
    dst_id = ""
    for sl in ev.get("sourceList",[]):
        src_id = sl.get("source","")
    for dl in ev.get("destinationList",[]):
        dst_id = dl.get("destination","")
    
    # get quantity from quantityList
    qty_shipped = sum(q.get("quantity",0) for q in ev.get("quantityList",[]))
    unit        = ev.get("quantityList",[{}])[0].get("uom","LBS") if ev.get("quantityList") else "LBS"
    
    # find the batch ids for this shipment
    batch_ids = []
    for q in ev.get("quantityList",[]):
        epc = q.get("epcClass","")
        if epc in epc_to_batch:
            batch_ids.append(epc_to_batch[epc])
    
    src_loc  = loc_map.get(src_id, {})
    dst_loc  = loc_map.get(dst_id, {})
    ev_time  = ev.get("eventTime","")

    shipment_rows.append({
        "Shipment_ID":         s_id,
        "Shipment_Date":       ev_time[:10] if ev_time else fmt_date(rand_date()),
        "Source_Location_ID":  src_id,
        "Source_Name":         src_loc.get("cbvmda:name",""),
        "Source_City":         src_loc.get("cbvmda:city",""),
        "Source_State":        src_loc.get("cbvmda:state",""),
        "Destination_ID":      dst_id,
        "Dest_Name":           dst_loc.get("cbvmda:name",""),
        "Dest_City":           dst_loc.get("cbvmda:city",""),
        "Dest_State":          dst_loc.get("cbvmda:state",""),
        "Quantity_Shipped":    round(qty_shipped,2),
        "Unit":                unit,
        "Transportation_Cost": round(random.uniform(50, 5000), 2),
        "Transport_Mode":      random.choice(["Truck","Rail","Air","Ship","Refrigerated Van"]),
        "Carrier_Name":        random.choice(["FoodEx Logistics","ColdChain Inc","AgriTransport","FreshMove LLC","GrainHaul Co"]),
        "Batch_IDs":           "; ".join(batch_ids),
        "Retailer_ID":         ret_id_map.get(dst_id,""),
        "EPCIS_Event_ID":      ev_id,
        "Track_Shipment_Qty":  round(qty_shipped,2),   # derived
    })

df_ship = pd.DataFrame(shipment_rows)
print(f"SHIPMENT: {len(df_ship)} rows")

# ═══════════════════════════════════════════════════════════════════════════════
# 6.  QUALITY_CHECK  (one per batch, some pass some fail)
# ═══════════════════════════════════════════════════════════════════════════════
qc_rows = []
batch_id_list = df_batch["Batch_ID"].tolist()
proc_id_list  = df_proc["Facility_ID"].tolist() if not df_proc.empty else ["FAC-001"]

for i, bid in enumerate(batch_id_list):
    status = random.choices(QC_STATUSES, weights=[60,15,15,10])[0]
    cont_type = "None" if status == "Pass" else random.choice(CONTAMINATION_TYPES[1:])
    check_date = rand_date("2024-01-01","2026-11-01")
    qc_rows.append({
        "Check_ID":           f"QC-{i+1:05d}",
        "Batch_ID":           bid,
        "Check_Date":         fmt_date(check_date),
        "Inspector_ID":       f"INS-{random.randint(1,50):03d}",
        "Facility_ID":        random.choice(proc_id_list),
        "Status":             status,
        "Contamination_Type": cont_type,
        "Remarks":            (
            "No issues detected." if status == "Pass"
            else f"Detected {cont_type}; batch flagged for review."
            if status == "Fail"
            else "Minor deviation noted; conditional approval granted."
            if status == "Conditional Pass"
            else "Awaiting lab results."
        ),
        "Temperature_C":      round(random.uniform(-2, 30), 1),
        "Humidity_Pct":       round(random.uniform(30, 95), 1),
        "Lab_Test_Code":      f"LAB-{short_hash(bid+str(i))}",
    })

df_qc = pd.DataFrame(qc_rows)
print(f"QUALITY_CHECK: {len(df_qc)} rows")

# ═══════════════════════════════════════════════════════════════════════════════
# 7.  ANOMALY_ALERT  (triggered by failed QC or shipment anomalies)
# ═══════════════════════════════════════════════════════════════════════════════
alert_rows = []
failed_qc  = df_qc[df_qc["Status"].isin(["Fail","Conditional Pass"])]
ship_id_list = df_ship["Shipment_ID"].tolist()

for _, qrow in failed_qc.iterrows():
    alert_date = datetime.strptime(qrow["Check_Date"], "%Y-%m-%d") + timedelta(days=random.randint(0,3))
    score = round(random.uniform(0.5, 1.0), 3) if qrow["Status"] == "Fail" else round(random.uniform(0.2,0.6),3)
    aid   = f"ALT-{len(alert_rows)+1:05d}"
    alert_rows.append({
        "Alert_ID":          aid,
        "Alert_Date":        fmt_date(alert_date),
        "Alert_Type":        "Quality Failure" if qrow["Status"]=="Fail" else "Contamination Detected",
        "Anomaly_Score":     score,
        "Description":       f"Batch {qrow['Batch_ID']} failed QC on {qrow['Check_Date']}. {qrow['Remarks']}",
        "Batch_ID":          qrow["Batch_ID"],
        "Check_ID":          qrow["Check_ID"],
        "Triggered_Shipment_ID": random.choice(ship_id_list) if ship_id_list else "",
        "Severity":          "High" if score>0.75 else "Medium" if score>0.5 else "Low",
        "Resolved":          random.choice([True, False]),
    })

# add some shipment-delay / temperature alerts
for _ in range(min(200, len(ship_id_list))):
    s_row = df_ship.sample(1).iloc[0]
    score = round(random.uniform(0.1, 0.9), 3)
    aid   = f"ALT-{len(alert_rows)+1:05d}"
    atype = random.choice(ALERT_TYPES)
    alert_rows.append({
        "Alert_ID":          aid,
        "Alert_Date":        fmt_date(rand_date("2024-01-01","2026-11-01")),
        "Alert_Type":        atype,
        "Anomaly_Score":     score,
        "Description":       f"Shipment {s_row['Shipment_ID']}: {atype} detected during transit.",
        "Batch_ID":          "",
        "Check_ID":          "",
        "Triggered_Shipment_ID": s_row["Shipment_ID"],
        "Severity":          "High" if score>0.75 else "Medium" if score>0.5 else "Low",
        "Resolved":          random.choice([True, False]),
    })

df_alert = pd.DataFrame(alert_rows)
print(f"ANOMALY_ALERT: {len(df_alert)} rows")

# ═══════════════════════════════════════════════════════════════════════════════
# 8.  PRICE_RECORD  (one per batch × supply-chain stage)
# ═══════════════════════════════════════════════════════════════════════════════
price_rows = []
for i, brow in df_batch.iterrows():
    stage      = random.choice(SUPPLY_CHAIN_STAGES)
    base_price = round(random.uniform(0.5, 50.0), 2)
    sell_price = round(base_price * random.uniform(1.1, 2.5), 2)
    price_date = rand_date("2024-01-01","2026-11-01")
    state      = rand_state()
    price_rows.append({
        "Price_ID":              f"PRC-{i+1:05d}",
        "Batch_ID":              brow["Batch_ID"],
        "Price_Date":            fmt_date(price_date),
        "Supply_Chain_Stage":    stage,
        "Market_Location":       rand_city(state) + ", " + state,
        "Cost_Per_Unit":         base_price,
        "Selling_Price":         sell_price,
        "Price_Change_Pct":      round((sell_price - base_price) / base_price * 100, 2),
        "Currency":              "USD",
        "Unit":                  brow["Unit"],
    })

df_price = pd.DataFrame(price_rows)
print(f"PRICE_RECORD: {len(df_price)} rows")

# ═══════════════════════════════════════════════════════════════════════════════
# 9.  RELATIONSHIP BRIDGE TABLES
# ═══════════════════════════════════════════════════════════════════════════════
# BATCH_SHIPMENT  (M:N — Included_In)
batch_ship_rows = []
for _, srow in df_ship.iterrows():
    for bid in str(srow["Batch_IDs"]).split(";"):
        bid = bid.strip()
        if bid:
            batch_ship_rows.append({"Batch_ID": bid, "Shipment_ID": srow["Shipment_ID"]})
df_batch_ship = pd.DataFrame(batch_ship_rows).drop_duplicates()
print(f"BATCH_SHIPMENT bridge: {len(df_batch_ship)} rows")

# ═══════════════════════════════════════════════════════════════════════════════
# 10.  WRITE EXCEL
# ═══════════════════════════════════════════════════════════════════════════════
print(f"\nWriting → {OUT} …")

SHEET_ORDER = [
    ("FARM",                df_farm),
    ("PROCESSING_FACILITY", df_proc),
    ("RETAILER",            df_ret),
    ("BATCH",               df_batch),
    ("QUALITY_CHECK",       df_qc),
    ("SHIPMENT",            df_ship),
    ("ANOMALY_ALERT",       df_alert),
    ("PRICE_RECORD",        df_price),
    ("BATCH_SHIPMENT",      df_batch_ship),
]

with pd.ExcelWriter(OUT, engine="openpyxl") as writer:
    for sheet_name, df in SHEET_ORDER:
        df.to_excel(writer, sheet_name=sheet_name, index=False)
        ws = writer.sheets[sheet_name]
        # auto-width columns
        for col_cells in ws.columns:
            max_len = max((len(str(c.value)) for c in col_cells if c.value is not None), default=8)
            ws.column_dimensions[col_cells[0].column_letter].width = min(max_len + 2, 50)

print("\nDone! ✓")
print(f"Saved to: {OUT}")
print("\nSheet summary:")
for name, df in SHEET_ORDER:
    print(f"  {name:<25} {len(df):>6} rows × {len(df.columns):>2} cols")
