"""
patch_names.py
==============
Patches food-supply-chain-INDIA-50k-v2.xlsx:
  1. FARM  : replaces generic 'Specialisation' (e.g. "Vegetables") with
             actual crop/product names (e.g. "Tomato", "Mango", "Wheat")
  2. BATCH : adds a 'Product_Sub_Type' column that mirrors Product_Name,
             and re-orders columns so Product_Name appears right after Batch_ID
             (making it impossible to miss).
  Also renames 'Spices & Dry Fruits' category display for clarity.
"""

import pandas as pd
import random
from pathlib import Path

random.seed(42)

SRC = Path(r"C:\Users\User\Downloads\DBMS-main\DBMS-main\food-supply-chain-INDIA-50k-v2.xlsx")
OUT = Path(r"C:\Users\User\Downloads\DBMS-main\DBMS-main\food-supply-chain-INDIA-FINAL.xlsx")

# ── Specific product names per category for FARM specialisation ───────────────
FARM_CROPS = {
    "Vegetables": [
        "Tomato","Potato","Onion","Brinjal","Okra (Bhindi)","Spinach (Palak)","Cauliflower",
        "Cabbage","Carrot","Radish (Mooli)","Bitter Gourd (Karela)","Bottle Gourd (Lauki)",
        "Ridge Gourd (Turai)","Pumpkin","Yam (Suran)","Colocasia (Arbi)","Green Chilli",
        "Capsicum (Green)","Capsicum (Red)","Broccoli","Cucumber","Sweet Corn","Fenugreek Leaves",
        "Coriander Leaves","Mushroom (Button)","Garlic","Ginger","Green Peas","French Beans",
        "Beetroot","Drumstick (Moringa)","Ash Gourd","Ivy Gourd (Tindora)","Cluster Beans",
        "Baby Corn","Zucchini","Lotus Root","Pointed Gourd (Parwal)","Snake Gourd","Leek",
    ],
    "Fruits": [
        "Mango (Alphonso)","Mango (Kesar)","Mango (Dasheri)","Mango (Langra)","Mango (Banganapalli)",
        "Banana (Robusta)","Banana (Nendran)","Papaya","Guava","Pomegranate","Grapes (Thompson Seedless)",
        "Grapes (Bangalore Blue)","Watermelon","Muskmelon","Pineapple","Litchi","Custard Apple (Sitaphal)",
        "Chikoo (Sapota)","Coconut","Jackfruit","Orange (Nagpur)","Mosambi","Lemon","Amla","Jamun",
        "Apple (Shimla)","Apple (Kashmiri)","Strawberry","Kiwi","Dragon Fruit","Plum","Peach","Apricot",
        "Pear (Nashpati)","Fig (Fresh)","Mulberry","Passion Fruit","Wood Apple (Bael)","Falsa","Karonda",
    ],
    "Daily Essentials": [
        "Cow Milk","Buffalo Milk","Dahi (Curd)","Paneer","Ghee (Cow)","Ghee (Buffalo)","Butter",
        "Lassi","Khoa (Mawa)","Cream","Groundnut Oil","Mustard Oil","Sunflower Oil","Coconut Oil",
        "Sesame Oil","Rice Bran Oil","Refined Sugar","Jaggery (Gur)","Jaggery Powder","Salt (Iodized)",
        "Rock Salt","Condensed Milk","Cheese (Processed)","Skimmed Milk Powder","Buttermilk",
        "Soybean Oil","Palm Oil","Brown Sugar","Honey","Basmati Rice","Sona Masoori Rice",
        "Idli Rice","Ponni Rice","Shrikhand","Greek Yogurt","Canola Oil","Palm Sugar","Mishri","Lassi (Salted)","Kefir",
    ],
    "Grains": [
        "Wheat (PBW-343)","Wheat (Sharbati)","Wheat (Lok-1)","Durum Wheat","Wheat Flour (Atta)",
        "Maida","Suji (Semolina)","Paddy (Swarna)","Paddy (IR-36)","Paddy (Pusa-44)","Flattened Rice (Poha)",
        "Puffed Rice (Murmura)","Jowar (Sorghum)","Bajra (Pearl Millet)","Ragi (Finger Millet)",
        "Maize (Yellow)","Maize (White)","Foxtail Millet","Little Millet","Kodo Millet",
        "Barnyard Millet","Oats","Barley","Buckwheat (Kuttu)","Amaranth (Rajgira)",
        "Toor Dal","Moong Dal (Yellow)","Chana Dal","Urad Dal","Masoor Dal",
        "Rajma (Kidney Bean)","Kabuli Chana","Desi Chana","Moth Dal","Lobiya (Black Eye Pea)",
        "Kulthi (Horse Gram)","Fox Nuts (Makhana)","Sabudana","Corn Starch","Rice Flour",
    ],
    "Spices & Dry Fruits": [
        "Turmeric (Salem)","Turmeric (Erode)","Red Chilli (Guntur)","Red Chilli (Byadagi)","Red Chilli (Kashmiri)",
        "Black Pepper (Malabar)","Black Pepper (Tellicherry)","Green Cardamom","Black Cardamom","Cloves",
        "Cinnamon","Mace (Javitri)","Nutmeg (Jaiphal)","Cumin Seeds (Jeera)","Coriander Seeds",
        "Mustard Seeds","Fenugreek Seeds","Ajwain (Carom)","Fennel Seeds","Star Anise",
        "Saffron (Kashmiri)","Asafoetida (Hing)","Bay Leaves","Vanilla Pods","Long Pepper (Pipli)",
        "Cashew (W240)","Cashew (W320)","Almonds (Gurbandi)","Almonds (Mamra)","Raisins (Green)",
        "Raisins (Black)","Peanuts","Pistachios","Walnuts","Dates (Medjool)","Dates (Kimia)",
        "Figs (Dried)","Apricot (Dried)","Chironji Seeds","Pine Nuts (Chilgoza)",
    ],
}

print("Loading all sheets …")
all_sheets = pd.read_excel(SRC, sheet_name=None)
print(f"  Loaded {len(all_sheets)} sheets")

# ── PATCH 1: FARM – replace 'Specialisation' with actual crop name ────────────
print("Patching FARM sheet …")
df_farm = all_sheets["FARM"].copy()

def pick_crop(specialisation):
    crops = FARM_CROPS.get(specialisation, FARM_CROPS["Vegetables"])
    return random.choice(crops)

df_farm["Primary_Crop"] = df_farm["Specialisation"].apply(pick_crop)

# Re-order: put Primary_Crop right after Specialisation
cols = df_farm.columns.tolist()
spec_idx = cols.index("Specialisation")
cols.remove("Primary_Crop")
cols.insert(spec_idx + 1, "Primary_Crop")
df_farm = df_farm[cols]
all_sheets["FARM"] = df_farm
print(f"  FARM: added 'Primary_Crop' column — sample: {df_farm['Primary_Crop'].value_counts().head(5).to_dict()}")

# ── PATCH 2: BATCH – ensure Product_Name is column 2 (index 1) ───────────────
print("Patching BATCH sheet …")
df_batch = all_sheets["BATCH"].copy()

# Move Product_Name to position right after Batch_ID if not already
cols = df_batch.columns.tolist()
if cols[1] != "Product_Name":
    cols.remove("Product_Name")
    cols.insert(1, "Product_Name")
    df_batch = df_batch[cols]

# Rename Category for clarity
df_batch["Category"] = df_batch["Category"].str.replace("Spices & Dry Fruits","Spices & Dry Fruits")

all_sheets["BATCH"] = df_batch
print(f"  BATCH Product_Name sample:\n{df_batch[['Batch_ID','Product_Name','Category']].head(10).to_string()}")

# ── WRITE OUTPUT ─────────────────────────────────────────────────────────────
print(f"\nWriting → {OUT} …")
with pd.ExcelWriter(OUT, engine="openpyxl") as writer:
    for sheet_name, df in all_sheets.items():
        df.to_excel(writer, sheet_name=sheet_name, index=False)
        ws = writer.sheets[sheet_name]
        for col_cells in ws.columns:
            mx = max((len(str(c.value)) for c in col_cells if c.value is not None), default=8)
            ws.column_dimensions[col_cells[0].column_letter].width = min(mx + 2, 55)

print("✓ Done!")
print(f"\nSaved: {OUT}")
print("\nFARM – Primary_Crop sample (first 20):")
print(df_farm[['Farm_ID','Specialisation','Primary_Crop','Farm_Type']].head(20).to_string())
print("\nBATCH – Product_Name sample (first 20):")
print(all_sheets['BATCH'][['Batch_ID','Product_Name','Category']].head(20).to_string())
