"""
Convert synthetic-food-supply-chain-dataset.json → Excel
Produces multiple sheets:
  - Events        : one row per EPCIS event (flattened)
  - Products      : vocabulary EPC class entries (product master data)
  - Locations     : vocabulary location entries
  - EPCList       : one row per (event, epc) pair
  - QuantityList  : one row per (event, quantity element) pair
"""

import json
import pandas as pd
from pathlib import Path

SRC = Path(r"C:\Users\User\Downloads\DBMS-main\DBMS-main\synthetic-food-supply-chain-dataset.json")
OUT = Path(r"C:\Users\User\Downloads\DBMS-main\DBMS-main\food-supply-chain-dataset.xlsx")

print("Loading JSON …")
with open(SRC, encoding="utf-8") as f:
    doc = json.load(f)

# ── 1. MASTER DATA ──────────────────────────────────────────────────────────
vocab_list = doc.get("epcisHeader", {}).get("epcisMasterData", {}).get("vocabularyList", [])

products_rows = []
locations_rows = []

for vocab in vocab_list:
    vtype = vocab.get("type", "")
    for elem in vocab.get("vocabularyElementList", []):
        elem_id = elem.get("id", "")
        attrs = {a["id"]: a.get("attribute", "") for a in elem.get("attributes", [])}
        row = {"id": elem_id, **attrs}
        if "EPCClass" in vtype:
            products_rows.append(row)
        elif "Location" in vtype:
            locations_rows.append(row)
        else:
            # fallback: put in products
            products_rows.append({"vocab_type": vtype, **row})

df_products  = pd.DataFrame(products_rows)
df_locations = pd.DataFrame(locations_rows)

# ── 2. EVENTS ────────────────────────────────────────────────────────────────
raw_events = (
    doc.get("epcisBody", {})
       .get("eventList", [])
)

events_rows   = []
epc_rows      = []
quantity_rows = []

SCALAR_SKIP = {"epcList", "quantityList", "inputEPCList", "outputEPCList",
               "inputQuantityList", "outputQuantityList",
               "childEPCs", "childQuantityList",
               "readPoint", "bizLocation", "bizTransactionList",
               "sourceList", "destinationList", "sensorElementList",
               "fdaftr:prevID", "fdaftr:lot"}

def flatten_dict(d, prefix="", sep="_"):
    """Recursively flatten a dict, skipping known list/complex keys."""
    out = {}
    for k, v in d.items():
        full_key = f"{prefix}{sep}{k}" if prefix else k
        if isinstance(v, dict):
            out.update(flatten_dict(v, full_key, sep))
        elif isinstance(v, list):
            # serialize short lists as strings; skip big ones handled separately
            if k not in SCALAR_SKIP:
                out[full_key] = "; ".join(str(i) for i in v) if v else ""
        else:
            out[full_key] = v
    return out

print(f"Processing {len(raw_events)} events …")

for idx, ev in enumerate(raw_events):
    ev_id = ev.get("eventID", f"event_{idx}")

    # Flatten scalar fields
    flat = flatten_dict(ev)
    flat["_eventIndex"] = idx

    # readPoint / bizLocation
    flat["readPoint_id"]   = ev.get("readPoint",   {}).get("id", "")
    flat["bizLocation_id"] = ev.get("bizLocation", {}).get("id", "")

    # prevID list → semicolon string
    flat["prevIDs"] = "; ".join(ev.get("fdaftr:prevID", []))

    events_rows.append(flat)

    # EPC list rows (all variants)
    for list_key in ("epcList", "inputEPCList", "outputEPCList", "childEPCs"):
        for epc in ev.get(list_key, []):
            epc_rows.append({"eventID": ev_id, "list_key": list_key, "epc": epc})

    # Quantity list rows
    for list_key in ("quantityList", "inputQuantityList", "outputQuantityList", "childQuantityList"):
        for q in ev.get(list_key, []):
            quantity_rows.append({
                "eventID":   ev_id,
                "list_key":  list_key,
                "epcClass":  q.get("epcClass", ""),
                "quantity":  q.get("quantity", ""),
                "uom":       q.get("uom", ""),
            })

df_events   = pd.DataFrame(events_rows)
df_epc      = pd.DataFrame(epc_rows)
df_quantity = pd.DataFrame(quantity_rows)

# Drop columns that are entirely empty
df_events = df_events.dropna(axis=1, how="all")

print(f"  Events sheet:   {len(df_events)} rows × {len(df_events.columns)} cols")
print(f"  EPCList sheet:  {len(df_epc)} rows")
print(f"  Quantity sheet: {len(df_quantity)} rows")
print(f"  Products sheet: {len(df_products)} rows")
print(f"  Locations sheet:{len(df_locations)} rows")

# ── 3. WRITE EXCEL ───────────────────────────────────────────────────────────
print(f"\nWriting → {OUT} …")
with pd.ExcelWriter(OUT, engine="openpyxl") as writer:
    df_events.to_excel(writer,   sheet_name="Events",       index=False)
    df_epc.to_excel(writer,      sheet_name="EPCList",      index=False)
    df_quantity.to_excel(writer, sheet_name="QuantityList", index=False)
    df_products.to_excel(writer, sheet_name="Products",     index=False)
    df_locations.to_excel(writer,sheet_name="Locations",    index=False)

print("Done! ✓")
print(f"File saved to: {OUT}")
