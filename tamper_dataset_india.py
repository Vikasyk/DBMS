"""
tamper_dataset_india.py
=======================
Transforms the synthetic EPCIS food-supply-chain dataset into the
ER-diagram schema with INDIAN locations, scaled to ~25,000 rows total.

Entities:
  FARM, PROCESSING_FACILITY, RETAILER, BATCH,
  QUALITY_CHECK, SHIPMENT, ANOMALY_ALERT, PRICE_RECORD,
  BATCH_SHIPMENT (M:N bridge)
"""

import json, random, hashlib, re, math
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd

random.seed(2024)

SRC = Path(r"C:\Users\User\Downloads\DBMS-main\DBMS-main\synthetic-food-supply-chain-dataset.json")
OUT = Path(r"C:\Users\User\Downloads\DBMS-main\DBMS-main\food-supply-chain-INDIA.xlsx")

TARGET_BATCHES   = 6000
TARGET_FARMS     = 400
TARGET_PROC_FAC  = 350
TARGET_RETAILERS = 800
TARGET_SHIPMENTS = 12000
TARGET_ALERTS    = 2500

# ═══════════════════════════════════════════════════════════════════════════════
#  INDIA DATA TABLES
# ═══════════════════════════════════════════════════════════════════════════════
INDIA_STATES_CITIES = {
    "Maharashtra": {
        "cities": ["Mumbai","Pune","Nagpur","Nashik","Aurangabad","Solapur","Kolhapur","Thane","Navi Mumbai","Amravati","Latur","Jalgaon","Akola","Satara","Sangli"],
        "pin_ranges": [(400001,400104),(411001,411062),(440001,440037),(422001,422013)],
    },
    "Uttar Pradesh": {
        "cities": ["Lucknow","Agra","Varanasi","Kanpur","Allahabad","Meerut","Bareilly","Aligarh","Gorakhpur","Noida","Ghaziabad","Mathura","Moradabad","Saharanpur","Firozabad"],
        "pin_ranges": [(226001,226031),(282001,282010),(221001,221015),(208001,208027)],
    },
    "Punjab": {
        "cities": ["Amritsar","Ludhiana","Jalandhar","Patiala","Bathinda","Mohali","Hoshiarpur","Gurdaspur","Ferozepur","Faridkot","Moga","Pathankot","Sangrur","Barnala","Muktsar"],
        "pin_ranges": [(143001,143115),(141001,141027),(144001,144022),(147001,147021)],
    },
    "Haryana": {
        "cities": ["Gurugram","Faridabad","Ambala","Hisar","Rohtak","Panipat","Karnal","Sonipat","Yamunanagar","Rewari","Bhiwani","Sirsa","Jhajjar","Palwal","Panchkula"],
        "pin_ranges": [(122001,122510),(121001,121109),(134001,134118),(125001,125058)],
    },
    "Rajasthan": {
        "cities": ["Jaipur","Jodhpur","Udaipur","Kota","Ajmer","Bikaner","Alwar","Bharatpur","Sikar","Pali","Bhilwara","Hanumangarh","Chittorgarh","Nagaur","Barmer"],
        "pin_ranges": [(302001,302042),(342001,342037),(313001,313027),(324001,324010)],
    },
    "Gujarat": {
        "cities": ["Ahmedabad","Surat","Vadodara","Rajkot","Bhavnagar","Jamnagar","Junagadh","Gandhinagar","Anand","Mehsana","Morbi","Navsari","Vapi","Bharuch","Nadiad"],
        "pin_ranges": [(380001,380063),(395001,395017),(390001,390025),(360001,360040)],
    },
    "Karnataka": {
        "cities": ["Bengaluru","Mysuru","Hubli","Mangaluru","Belgaum","Davanagere","Bellary","Bijapur","Shimoga","Tumkur","Raichur","Bidar","Gulbarga","Udupi","Hassan"],
        "pin_ranges": [(560001,560114),(570001,570032),(580001,580032),(575001,575025)],
    },
    "Tamil Nadu": {
        "cities": ["Chennai","Coimbatore","Madurai","Tiruchirappalli","Salem","Tirunelveli","Tiruppur","Vellore","Erode","Thoothukkudi","Dindigul","Cuddalore","Thanjavur","Kancheepuram","Krishnagiri"],
        "pin_ranges": [(600001,600119),(641001,641062),(625001,625023),(620001,620021)],
    },
    "Andhra Pradesh": {
        "cities": ["Visakhapatnam","Vijayawada","Tirupati","Guntur","Kurnool","Nellore","Kakinada","Rajahmundry","Kadapa","Anantapur","Eluru","Ongole","Nandyal","Chittoor","Proddatur"],
        "pin_ranges": [(530001,530053),(520001,520015),(517501,517601),(522001,522034)],
    },
    "Telangana": {
        "cities": ["Hyderabad","Warangal","Nizamabad","Khammam","Karimnagar","Ramagundam","Mahbubnagar","Nalgonda","Adilabad","Suryapet","Miryalaguda","Mancherial","Jagtial","Siddipet","Bhongir"],
        "pin_ranges": [(500001,500100),(506001,506370),(503001,503230),(507001,507318)],
    },
    "West Bengal": {
        "cities": ["Kolkata","Howrah","Durgapur","Asansol","Siliguri","Bardhaman","Malda","Baharampur","Krishnanagar","Bankura","Purulia","Kharagpur","Haldia","Jalpaiguri","Cooch Behar"],
        "pin_ranges": [(700001,700156),(711101,711316),(713201,713346),(734001,734217)],
    },
    "Madhya Pradesh": {
        "cities": ["Bhopal","Indore","Jabalpur","Gwalior","Ujjain","Rewa","Satna","Sagar","Dewas","Murwara","Chhindwara","Ratlam","Burhanpur","Khandwa","Vidisha"],
        "pin_ranges": [(462001,462046),(452001,452020),(482001,482021),(474001,474040)],
    },
    "Bihar": {
        "cities": ["Patna","Gaya","Bhagalpur","Muzaffarpur","Purnia","Darbhanga","Arrah","Begusarai","Katihar","Munger","Chapra","Sasaram","Hajipur","Siwan","Motihari"],
        "pin_ranges": [(800001,800030),(823001,823003),(812001,812007),(842001,842009)],
    },
    "Odisha": {
        "cities": ["Bhubaneswar","Cuttack","Rourkela","Brahmapur","Puri","Sambalpur","Balasore","Baripada","Bhadrak","Jeypore","Jharsuguda","Rayagada","Angul","Kendujhar","Dhenkanal"],
        "pin_ranges": [(751001,751030),(753001,753015),(769001,769016),(760001,760011)],
    },
    "Kerala": {
        "cities": ["Thiruvananthapuram","Kochi","Kozhikode","Thrissur","Kollam","Palakkad","Alappuzha","Malappuram","Kannur","Kottayam","Kasaragod","Pathanamthitta","Idukki","Wayanad","Ernakulam"],
        "pin_ranges": [(695001,695099),(682001,682320),(673001,673641),(680001,680751)],
    },
}

INDIAN_FOOD_PRODUCTS = [
    # Grains & Cereals
    "Basmati Rice","Sona Masoori Rice","Jowar","Bajra","Ragi","Wheat Flour (Atta)","Maida","Suji (Semolina)","Poha","Corn Flour",
    # Pulses & Legumes
    "Toor Dal","Moong Dal","Chana Dal","Urad Dal","Masoor Dal","Rajma","Kabuli Chana","Moth Dal","Lobiya","Green Moong Whole",
    # Spices
    "Turmeric Powder","Red Chilli Powder","Coriander Powder","Cumin Seeds","Mustard Seeds","Fenugreek Seeds","Black Pepper","Cardamom","Cloves","Cinnamon Sticks",
    "Ajwain","Bay Leaves","Star Anise","Asafoetida (Hing)","Saffron","Curry Leaves Dried","Kasuri Methi","Garam Masala","Chaat Masala","Biryani Masala",
    # Oils & Fats
    "Groundnut Oil","Mustard Oil","Sesame Oil","Coconut Oil","Sunflower Oil","Soybean Oil","Rice Bran Oil","Palm Oil","Ghee","Butter",
    # Dairy
    "Full Cream Milk Powder","Skimmed Milk Powder","Paneer Block","Curd","Khoa (Mawa)","Condensed Milk","Cheese Slice","Buttermilk Powder","Lassi","Shrikhand",
    # Fruits & Vegetables (processed)
    "Mango Pulp (Alphonso)","Tomato Puree","Tomato Paste","Amla Powder","Kokum Extract","Tamarind Paste","Lemon Juice Concentrate","Guava Pulp","Pomegranate Juice","Coconut Milk",
    # Sugar & Sweeteners
    "Raw Cane Sugar","Refined Sugar","Jaggery (Gur)","Palm Sugar","Brown Sugar","Honey","Mishri (Rock Sugar)","Date Syrup","Stevia Powder","Coconut Sugar",
    # Processed & Packaged
    "Papad (Urad)","Pickle (Mango)","Pickle (Lime)","Chyawanprash","Murabba","Amchur Powder","Kokum Sherbet","Aam Panna Concentrate","Gulkand","Rose Water",
    # Beverages
    "Masala Chai Premix","Filter Coffee Powder","Instant Coffee","Green Tea Bags","Tulsi Tea","Ashwagandha Powder","Moringa Powder","Sattu Powder","Roasted Barley Flour","Ragi Malt",
    # Nuts & Dry Fruits
    "Cashew Whole (W240)","Almonds (Gurbandi)","Raisins","Peanuts Roasted","Pistachio","Walnuts","Dates (Medjool)","Figs Dried","Apricot Dried","Chironji",
    # Snacks & Namkeen
    "Bhujia Sev","Chivda","Murukku","Khakhra","Thekua","Namkeen Mix","Shakarpara","Mathri","Chakli","Boondi",
]

FOOD_CATEGORIES = [
    "Grains & Cereals","Pulses & Legumes","Spices & Condiments","Oils & Fats",
    "Dairy Products","Fruits & Vegetable Products","Sugar & Sweeteners",
    "Processed & Packaged","Beverages","Nuts & Dry Fruits","Snacks & Namkeen",
]

CONTAMINATION_TYPES = [
    "None","Salmonella","E. coli (STEC)","Listeria monocytogenes","Aspergillus (Aflatoxin)",
    "Pesticide Residue","Heavy Metal (Lead)","Heavy Metal (Cadmium)","Foreign Object",
    "Rodent Contamination","Fungal Mould","Adulteration","Microbial Overgrowth","Insect Infestation","Mycotoxin",
]

ALERT_TYPES = [
    "Temperature Exceedance","Cold Chain Breach","Delay Alert",
    "Quality Failure","Contamination Detected","Quantity Mismatch",
    "Document Fraud","Expiry Violation","Improper Storage","Pest Infestation Alert",
]

QC_STATUSES = ["Pass","Fail","Conditional Pass","Pending Review"]

SUPPLY_CHAIN_STAGES = ["Farm Gate","Primary Processing","Secondary Processing","Wholesale","Distribution Centre","Retail"]

TRANSPORT_MODES = ["Refrigerated Truck","Insulated Van","Railway Wagon","Cold Storage Container","Two-Wheeler (Last Mile)","Tempo","Air Cargo"]
CARRIERS = [
    "Snowman Logistics","Rivigo Reefer","Safexpress Agri","DHL Supply Chain India",
    "CONCOR Cold Chain","Blue Dart Cargo","Mahindra Logistics","TCI-FRESH","VRL Logistics",
    "Gati KWE","DTDC Express","First Flight Couriers","Delhivery Cold","XpressBees","Ecom Express",
]
CERT_STANDARDS = ["FSSAI","ISO 22000","HACCP","BRC Global Standard","IFS Food","SQF","FSSC 22000","Organic India Certified"]
STORE_TYPES    = ["Kirana Store","Supermarket","Hypermarket","Mandi (Wholesale)","Online (B2C)","Cooperative Society","Cold Store Retail","APMC Market","Modern Trade","Quick Commerce"]
FARM_TYPES     = ["Wheat Farm","Rice Paddy","Vegetable Farm","Spice Plantation","Dairy Farm","Fruit Orchard","Pulse Farm","Oilseed Farm","Sugarcane Farm","Mixed Crop Farm"]

# ── helpers ──────────────────────────────────────────────────────────────────
def rand_date(start="2022-01-01", end="2026-11-01"):
    s = datetime.strptime(start, "%Y-%m-%d")
    e = datetime.strptime(end,   "%Y-%m-%d")
    return s + timedelta(seconds=random.randint(0, int((e-s).total_seconds())))

def fmt_date(dt):
    return dt.strftime("%Y-%m-%d") if isinstance(dt, datetime) else str(dt)

def short_hash(text, n=8):
    return hashlib.md5(text.encode()).hexdigest()[:n].upper()

def rand_indian_phone():
    # Indian mobile: +91 + 10 digits starting with 6-9
    prefix = random.choice(["6","7","8","9"])
    return f"+91-{prefix}{random.randint(100000000,999999999)}"

def rand_state():
    return random.choice(list(INDIA_STATES_CITIES.keys()))

def rand_city(state):
    return random.choice(INDIA_STATES_CITIES[state]["cities"])

def rand_pin(state):
    ranges = INDIA_STATES_CITIES[state]["pin_ranges"]
    r = random.choice(ranges)
    return str(random.randint(r[0], r[1]))

def rand_street():
    nums   = ["12","45","78","23/A","56-B","Plot No. 7","Survey No. 143","Khasra No. 88","Door No. 34","H.No. 102"]
    names  = ["Gandhi Marg","Nehru Road","Station Road","MG Road","Ring Road","Sadar Bazar","Civil Lines","Patel Nagar","Lal Bahadur Nagar","Industrial Area"]
    types  = ["","Phase I","Sector 5","Block B","Extension","Colony","Nagar","Vihar",""]
    return f"{random.choice(nums)}, {random.choice(names)} {random.choice(types)}".strip()

def rand_location(state, city):
    # Plausible lat/lon for major Indian zones
    state_coords = {
        "Maharashtra": (19.0760, 72.8777), "Uttar Pradesh": (26.8467, 80.9462),
        "Punjab": (31.1471, 75.3412), "Haryana": (29.0588, 76.0856),
        "Rajasthan": (27.0238, 74.2179), "Gujarat": (22.2587, 71.1924),
        "Karnataka": (15.3173, 75.7139), "Tamil Nadu": (11.1271, 78.6569),
        "Andhra Pradesh": (15.9129, 79.7400), "Telangana": (18.1124, 79.0193),
        "West Bengal": (22.9868, 87.8550), "Madhya Pradesh": (22.9734, 78.6569),
        "Bihar": (25.0961, 85.3131), "Odisha": (20.9517, 85.0985), "Kerala": (10.8505, 76.2711),
    }
    base = state_coords.get(state, (20.5937, 78.9629))
    lat  = round(base[0] + random.uniform(-2.5, 2.5), 5)
    lon  = round(base[1] + random.uniform(-2.5, 2.5), 5)
    return f"geo:{lat},{lon}"

def gst_number(state_code, rand_part):
    return f"{state_code:02d}AAA{short_hash(rand_part)}Z"

def fssai_number():
    return f"10{random.randint(10000000000000, 99999999999999)}"

STATE_CODES = {s: i+1 for i, s in enumerate(INDIA_STATES_CITIES.keys())}

# ── company name builder ──────────────────────────────────────────────────────
FARM_PREFIXES    = ["Shree","Jai","Om","Bharat","Kisaan","Swadeshi","Desi","Sarkar","Dhan","Anaj"]
FARM_SUFFIXES    = ["Agro Farm","Krishi Kendra","Agriculture Estate","Organic Farms","Kisaan Agri","Food Farm","Produce Pvt Ltd"]
PROC_PREFIXES    = ["National","Bharat","Indo","Sai","Laxmi","Durga","Shakti","Modern","Prime","Pioneer"]
PROC_SUFFIXES    = ["Food Processing Pvt Ltd","Agro Industries","Food Products Ltd","Cold Storage & Processing","Grain Millers","Spice Mills","Dairy Processors","Food Park Unit"]
RETAIL_PREFIXES  = ["Big","Super","Desi","Fresh","Daily","Smart","City","Lucky","Jai","Shri"]
RETAIL_SUFFIXES  = ["Mart","Bazaar","Kirana","Superstores","Grocery","Food World","General Stores","Supermarket","Traders","Merchants"]

def rand_farm_name():
    return f"{random.choice(FARM_PREFIXES)} {random.choice(FARM_SUFFIXES)}"

def rand_proc_name():
    return f"{random.choice(PROC_PREFIXES)} {random.choice(PROC_SUFFIXES)}"

def rand_retail_name(city):
    return f"{random.choice(RETAIL_PREFIXES)} {city} {random.choice(RETAIL_SUFFIXES)}"

# ═══════════════════════════════════════════════════════════════════════════════
# LOAD JSON (use existing events as seed, then scale up synthetically)
# ═══════════════════════════════════════════════════════════════════════════════
print("Loading JSON base dataset …")
with open(SRC, encoding="utf-8") as f:
    doc = json.load(f)

events = doc["epcisBody"]["eventList"]
vocabs = doc["epcisHeader"]["epcisMasterData"]["vocabularyList"]

prod_map = {}
for vocab in vocabs:
    if "EPCClass" in vocab["type"]:
        for elem in vocab["vocabularyElementList"]:
            prod_map[elem["id"]] = elem.get("attributes",[{}])[0].get("attribute","")

# get all unique epcClass URIs
all_epc_classes = set()
for ev in events:
    for ql_key in ("quantityList","inputQuantityList","outputQuantityList","childQuantityList"):
        for q in ev.get(ql_key, []):
            all_epc_classes.add(q.get("epcClass",""))
all_epc_classes.discard("")
base_epc_list = sorted(all_epc_classes)
print(f"  Base unique epcClass URIs: {len(base_epc_list)}")

# ═══════════════════════════════════════════════════════════════════════════════
# 1. FARM  (~400)
# ═══════════════════════════════════════════════════════════════════════════════
print(f"Building FARM table (target {TARGET_FARMS}) …")
farm_rows = []
state_list = list(INDIA_STATES_CITIES.keys())

for i in range(TARGET_FARMS):
    state = state_list[i % len(state_list)] if i < len(state_list)*3 else rand_state()
    city  = rand_city(state)
    fid   = f"FARM-{i+1:04d}"
    farm_rows.append({
        "Farm_ID":        fid,
        "Farm_Name":      rand_farm_name(),
        "Farm_Type":      random.choice(FARM_TYPES),
        "Owner_Name":     random.choice(["Ramesh Kumar","Suresh Patel","Mohan Singh","Ajay Verma","Ravi Sharma","Priya Devi","Sunita Nair","Amit Joshi","Deepak Yadav","Pooja Gupta"]),
        "Street":         rand_street(),
        "Village":        city + " Rural" if random.random()<0.4 else city,
        "City":           city,
        "District":       city,
        "State":          state,
        "PIN_Code":       rand_pin(state),
        "Contact_No":     rand_indian_phone(),
        "Alt_Contact_No": rand_indian_phone() if random.random()<0.5 else "",
        "Location_GPS":   rand_location(state, city),
        "Land_Area_Acres":round(random.uniform(1, 500), 2),
        "Irrigation_Type":random.choice(["Canal","Borewell","Rainwater Harvesting","Drip Irrigation","Sprinkler","Tank Irrigation"]),
        "FSSAI_License":  fssai_number() if random.random()<0.6 else "",
        "GST_No":         gst_number(STATE_CODES.get(state,27), fid) if random.random()<0.5 else "",
        "Registered_Date":fmt_date(rand_date("2005-01-01","2022-12-31")),
        "Country":        "India",
    })

df_farm = pd.DataFrame(farm_rows)
print(f"  FARM: {len(df_farm)} rows × {len(df_farm.columns)} cols")

# ═══════════════════════════════════════════════════════════════════════════════
# 2. PROCESSING_FACILITY  (~350)
# ═══════════════════════════════════════════════════════════════════════════════
print(f"Building PROCESSING_FACILITY table (target {TARGET_PROC_FAC}) …")
proc_rows = []

for i in range(TARGET_PROC_FAC):
    state = state_list[i % len(state_list)] if i < len(state_list)*2 else rand_state()
    city  = rand_city(state)
    fid   = f"FAC-{i+1:04d}"
    proc_rows.append({
        "Facility_ID":      fid,
        "Facility_Name":    rand_proc_name(),
        "Facility_Type":    random.choice(["Flour Mill","Rice Mill","Dal Mill","Oil Mill","Cold Storage","Spice Processing","Dairy Plant","Canning Unit","Packaging Unit","Multi-Product Plant"]),
        "Street":           rand_street(),
        "City":             city,
        "District":         city,
        "State":            state,
        "PIN_Code":         rand_pin(state),
        "Contact_No":       rand_indian_phone(),
        "Location_GPS":     rand_location(state, city),
        "Capacity_MT_Day":  round(random.uniform(5, 2000), 1),
        "Cold_Storage_MT":  round(random.uniform(0, 5000), 1) if random.random()<0.6 else 0,
        "Cert_Standard":    random.choice(CERT_STANDARDS),
        "FSSAI_License":    fssai_number(),
        "GST_No":           gst_number(STATE_CODES.get(state,27), fid),
        "Year_Established": random.randint(1985, 2023),
        "Num_Employees":    random.randint(10, 2000),
        "Country":          "India",
    })

df_proc = pd.DataFrame(proc_rows)
print(f"  PROCESSING_FACILITY: {len(df_proc)} rows × {len(df_proc.columns)} cols")

# ═══════════════════════════════════════════════════════════════════════════════
# 3. RETAILER  (~800)
# ═══════════════════════════════════════════════════════════════════════════════
print(f"Building RETAILER table (target {TARGET_RETAILERS}) …")
ret_rows = []

for i in range(TARGET_RETAILERS):
    state = state_list[i % len(state_list)] if i < len(state_list)*5 else rand_state()
    city  = rand_city(state)
    rid   = f"RET-{i+1:04d}"
    ret_rows.append({
        "Retailer_ID":    rid,
        "Retailer_Name":  rand_retail_name(city),
        "Store_Type":     random.choice(STORE_TYPES),
        "Owner_Name":     random.choice(["Nilesh Shah","Pradeep Jain","Kavita Desai","Arun Nair","Meena Pillai","Santosh Reddy","Harpreet Kaur","Vikas Chopra","Sonal Mehta","Rohit Gupta"]),
        "Street":         rand_street(),
        "City":           city,
        "District":       city,
        "State":          state,
        "PIN_Code":       rand_pin(state),
        "Contact_No":     rand_indian_phone(),
        "Location_GPS":   rand_location(state, city),
        "FSSAI_License":  fssai_number() if random.random()<0.8 else "",
        "GST_No":         gst_number(STATE_CODES.get(state,27), rid) if random.random()<0.7 else "",
        "Avg_Daily_Sales_INR": round(random.uniform(500, 500000), 2),
        "Country":        "India",
    })

df_ret = pd.DataFrame(ret_rows)
print(f"  RETAILER: {len(df_ret)} rows × {len(df_ret.columns)} cols")

# ═══════════════════════════════════════════════════════════════════════════════
# 4. BATCH  (~6000)
# ═══════════════════════════════════════════════════════════════════════════════
print(f"Building BATCH table (target {TARGET_BATCHES}) …")
batch_rows = []
farm_ids   = df_farm["Farm_ID"].tolist()
proc_ids   = df_proc["Facility_ID"].tolist()

# extend base EPC list by hashing synthetic ones
while len(base_epc_list) < TARGET_BATCHES:
    extra_epc = f"https://id.gs1.org/01/{random.randint(10000000000000,99999999999999)}/10/{random.randint(10000,99999)}"
    base_epc_list.append(extra_epc)
base_epc_list = base_epc_list[:TARGET_BATCHES]

prod_pool = INDIAN_FOOD_PRODUCTS * (TARGET_BATCHES // len(INDIAN_FOOD_PRODUCTS) + 2)

for i, epc in enumerate(base_epc_list):
    prod_name   = prod_pool[i % len(prod_pool)]
    prod_date   = rand_date("2022-01-01","2026-10-01")
    shelf_days  = random.randint(30, 730)
    expiry_date = prod_date + timedelta(days=shelf_days)
    now_date    = datetime(2026, 11, 23)
    shelf_rem   = max(0, (expiry_date - now_date).days)
    qty         = round(random.uniform(0.5, 1000.0), 2)
    unit        = random.choice(["KG","MT","Quintal","LBS","CASES","Bags (50kg)","Litre","Tin"])
    bid         = f"BATCH-{i+1:05d}"
    batch_rows.append({
        "Batch_ID":              bid,
        "EPC_Class_URI":         epc,
        "Product_Name":          prod_name,
        "Category":              random.choice(FOOD_CATEGORIES),
        "Production_Date":       fmt_date(prod_date),
        "Expiry_Date":           fmt_date(expiry_date),
        "Shelf_Life_Days":       shelf_days,
        "Shelf_Life_Remaining":  shelf_rem,
        "Quantity":              qty,
        "Unit":                  unit,
        "Lot_Number":            f"LOT-{short_hash(epc)}-{prod_date.year}",
        "Grade":                 random.choice(["A+","A","B","C","Export Quality","Fair Average Quality (FAQ)"]),
        "Origin_Farm_ID":        random.choice(farm_ids),
        "Processed_By_Fac_ID":   random.choice(proc_ids),
        "Moisture_Pct":          round(random.uniform(8, 20), 2),
        "Foreign_Matter_Pct":    round(random.uniform(0, 2), 3),
        "FSSAI_Approved":        random.choice([True, True, True, False]),
        "Input_Batch_ID":        f"BATCH-{random.randint(1,i+1):05d}" if i>0 and random.random()<0.3 else "",
        "Output_Batch_ID":       "",  # filled later for transformation events
    })

df_batch = pd.DataFrame(batch_rows)
# fill some output batch IDs (simulate TransformationEvent)
for idx in df_batch.index:
    if df_batch.at[idx,"Input_Batch_ID"] != "":
        in_bid = df_batch.at[idx,"Input_Batch_ID"]
        # find that input batch and set output
        mask = df_batch["Batch_ID"] == in_bid
        if mask.any():
            df_batch.loc[mask, "Output_Batch_ID"] = df_batch.at[idx,"Batch_ID"]

print(f"  BATCH: {len(df_batch)} rows × {len(df_batch.columns)} cols")

# ═══════════════════════════════════════════════════════════════════════════════
# 5. QUALITY_CHECK  (1–2 checks per batch → ~8000)
# ═══════════════════════════════════════════════════════════════════════════════
print("Building QUALITY_CHECK table …")
qc_rows = []
batch_id_list = df_batch["Batch_ID"].tolist()

for bid in batch_id_list:
    n_checks = random.choices([1, 2, 3], weights=[60, 30, 10])[0]
    for c in range(n_checks):
        status    = random.choices(QC_STATUSES, weights=[62, 15, 15, 8])[0]
        cont_type = "None" if status in ("Pass","Pending Review") else random.choice(CONTAMINATION_TYPES[1:])
        chk_date  = rand_date("2022-01-01","2026-11-01")
        qcid      = f"QC-{len(qc_rows)+1:06d}"
        qc_rows.append({
            "Check_ID":           qcid,
            "Batch_ID":           bid,
            "Check_Date":         fmt_date(chk_date),
            "Inspector_ID":       f"INS-{random.randint(1,120):03d}",
            "Facility_ID":        random.choice(proc_ids),
            "Status":             status,
            "Contamination_Type": cont_type,
            "Temperature_C":      round(random.uniform(-2, 35), 1),
            "Humidity_Pct":       round(random.uniform(25, 95), 1),
            "pH_Level":           round(random.uniform(3.5, 8.5), 2),
            "Moisture_Pct":       round(random.uniform(7, 20), 2),
            "Lab_Test_Code":      f"LAB-{short_hash(bid+str(c))}",
            "Remarks":            (
                "No issues. Batch approved for dispatch." if status == "Pass"
                else f"FAIL: {cont_type} detected. Batch quarantined." if status == "Fail"
                else f"Conditional approval. {cont_type} trace found within permissible limit." if status == "Conditional Pass"
                else "Lab test in progress. Awaiting NABL report."
            ),
        })

df_qc = pd.DataFrame(qc_rows)
print(f"  QUALITY_CHECK: {len(df_qc)} rows × {len(df_qc.columns)} cols")

# ═══════════════════════════════════════════════════════════════════════════════
# 6. SHIPMENT  (~12,000)
# ═══════════════════════════════════════════════════════════════════════════════
print(f"Building SHIPMENT table (target {TARGET_SHIPMENTS}) …")
ship_rows = []
ret_id_list = df_ret["Retailer_ID"].tolist()

# Base events from JSON (shipping)
shipping_events = [e for e in events if e.get("bizStep") == "shipping"]

# helper to build shipment row
def make_shipment(sid, src_state, src_city, dst_state, dst_city, ship_date_dt, batch_ids, qty, unit):
    cost_per_km  = random.uniform(15, 80)
    distance_km  = random.uniform(50, 2500)
    trans_cost   = round(cost_per_km * distance_km / 100, 2)
    return {
        "Shipment_ID":          sid,
        "Shipment_Date":        fmt_date(ship_date_dt),
        "Expected_Delivery":    fmt_date(ship_date_dt + timedelta(days=random.randint(1,10))),
        "Actual_Delivery":      fmt_date(ship_date_dt + timedelta(days=random.randint(1,14))) if random.random()<0.85 else "",
        "Source_City":          src_city,
        "Source_State":         src_state,
        "Source_PIN":           rand_pin(src_state),
        "Destination_City":     dst_city,
        "Destination_State":    dst_state,
        "Destination_PIN":      rand_pin(dst_state),
        "Quantity_Shipped":     round(qty, 2),
        "Unit":                 unit,
        "Transportation_Cost_INR": trans_cost,
        "Transport_Mode":       random.choice(TRANSPORT_MODES),
        "Carrier_Name":         random.choice(CARRIERS),
        "Vehicle_No":           f"{random.choice(['MH','DL','KA','TN','GJ','RJ','UP','HR','PB','WB'])}-{random.randint(10,99)}-{random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')}{random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')}-{random.randint(1000,9999)}",
        "Batch_IDs":            "; ".join(batch_ids),
        "Retailer_ID":          random.choice(ret_id_list),
        "Supply_Chain_Stage":   random.choice(SUPPLY_CHAIN_STAGES),
        "Track_Shipment_Qty":   round(qty, 2),
        "Cold_Chain_Maintained":random.choice([True, True, True, False]),
        "Temperature_During_Transit_C": round(random.uniform(-5, 25), 1),
        "Status":               random.choices(["Delivered","In Transit","Delayed","Partial Delivery","Returned"],[60,20,10,7,3])[0],
    }

# generate shipments
batch_pool = df_batch[["Batch_ID","Unit","Quantity"]].to_dict("records")

for i in range(TARGET_SHIPMENTS):
    sid   = f"SHIP-{i+1:05d}"
    # pick 1-3 batches
    n_batches = random.choices([1,2,3], weights=[60,30,10])[0]
    picked    = random.sample(batch_pool, min(n_batches, len(batch_pool)))
    b_ids     = [p["Batch_ID"] for p in picked]
    qty       = sum(p["Quantity"] for p in picked)
    unit      = picked[0]["Unit"]
    src_state = rand_state()
    dst_state = rand_state()
    src_city  = rand_city(src_state)
    dst_city  = rand_city(dst_state)
    ship_date = rand_date("2022-01-01","2026-11-01")
    ship_rows.append(make_shipment(sid, src_state, src_city, dst_state, dst_city, ship_date, b_ids, qty, unit))

df_ship = pd.DataFrame(ship_rows)
print(f"  SHIPMENT: {len(df_ship)} rows × {len(df_ship.columns)} cols")

# ═══════════════════════════════════════════════════════════════════════════════
# 7. ANOMALY_ALERT  (~2500)
# ═══════════════════════════════════════════════════════════════════════════════
print(f"Building ANOMALY_ALERT table (target {TARGET_ALERTS}) …")
alert_rows = []
failed_qc  = df_qc[df_qc["Status"].isin(["Fail","Conditional Pass"])].to_dict("records")
ship_id_list = df_ship["Shipment_ID"].tolist()

# alerts from failed QC (capped)
for qrow in random.sample(failed_qc, min(int(TARGET_ALERTS*0.55), len(failed_qc))):
    alert_date = datetime.strptime(qrow["Check_Date"], "%Y-%m-%d") + timedelta(days=random.randint(0,5))
    score      = round(random.uniform(0.55,1.0),3) if qrow["Status"]=="Fail" else round(random.uniform(0.25,0.6),3)
    aid        = f"ALT-{len(alert_rows)+1:06d}"
    alert_rows.append({
        "Alert_ID":               aid,
        "Alert_Date":             fmt_date(alert_date),
        "Alert_Type":             "Quality Failure" if qrow["Status"]=="Fail" else "Contamination Detected",
        "Anomaly_Score":          score,
        "Severity":               "Critical" if score>0.85 else "High" if score>0.7 else "Medium" if score>0.5 else "Low",
        "Description":            f"Batch {qrow['Batch_ID']} failed QC on {qrow['Check_Date']}. {qrow['Remarks']}",
        "Batch_ID":               qrow["Batch_ID"],
        "Check_ID":               qrow["Check_ID"],
        "Triggered_Shipment_ID":  random.choice(ship_id_list),
        "Assigned_To":            f"INS-{random.randint(1,120):03d}",
        "Resolved":               random.choices([True,False],[60,40])[0],
        "Resolution_Date":        fmt_date(alert_date + timedelta(days=random.randint(1,30))) if random.random()<0.6 else "",
        "Action_Taken":           random.choice(["Batch recalled","Quarantine extended","Re-test ordered","Supplier warned","Batch destroyed","Re-process approved","Investigation opened"]),
    })

# shipment-based alerts
for _ in range(TARGET_ALERTS - len(alert_rows)):
    srow   = random.choice(ship_rows)
    score  = round(random.uniform(0.1,0.95),3)
    atype  = random.choice(ALERT_TYPES)
    aid    = f"ALT-{len(alert_rows)+1:06d}"
    a_date = rand_date("2022-01-01","2026-11-01")
    alert_rows.append({
        "Alert_ID":               aid,
        "Alert_Date":             fmt_date(a_date),
        "Alert_Type":             atype,
        "Anomaly_Score":          score,
        "Severity":               "Critical" if score>0.85 else "High" if score>0.7 else "Medium" if score>0.5 else "Low",
        "Description":            f"Shipment {srow['Shipment_ID']}: {atype} detected. Carrier: {srow['Carrier_Name']}.",
        "Batch_ID":               "",
        "Check_ID":               "",
        "Triggered_Shipment_ID":  srow["Shipment_ID"],
        "Assigned_To":            f"INS-{random.randint(1,120):03d}",
        "Resolved":               random.choices([True,False],[55,45])[0],
        "Resolution_Date":        fmt_date(a_date + timedelta(days=random.randint(1,20))) if random.random()<0.55 else "",
        "Action_Taken":           random.choice(["Shipment held at checkpoint","Driver re-routed","Cold chain restored","Cargo inspected","Penalty issued to carrier","Insurance claim filed"]),
    })

df_alert = pd.DataFrame(alert_rows)
print(f"  ANOMALY_ALERT: {len(df_alert)} rows × {len(df_alert.columns)} cols")

# ═══════════════════════════════════════════════════════════════════════════════
# 8. PRICE_RECORD  (1 per batch → ~6000)
# ═══════════════════════════════════════════════════════════════════════════════
print("Building PRICE_RECORD table …")
price_rows = []

# Indian price benchmarks per category (INR per KG approx)
category_prices = {
    "Grains & Cereals":          (20, 120),
    "Pulses & Legumes":          (60, 300),
    "Spices & Condiments":       (80, 2500),
    "Oils & Fats":               (90, 300),
    "Dairy Products":            (40, 600),
    "Fruits & Vegetable Products":(30, 400),
    "Sugar & Sweeteners":        (35, 500),
    "Processed & Packaged":      (50, 800),
    "Beverages":                 (80, 1200),
    "Nuts & Dry Fruits":         (200, 2000),
    "Snacks & Namkeen":          (50, 400),
}

for i, brow in df_batch.iterrows():
    cat   = brow["Category"]
    rng   = category_prices.get(cat, (30, 500))
    stage = random.choice(SUPPLY_CHAIN_STAGES)
    farm_price  = round(random.uniform(rng[0], rng[0]+(rng[1]-rng[0])*0.4), 2)
    sell_price  = round(farm_price * random.uniform(1.15, 2.8), 2)
    state = rand_state()
    price_date  = rand_date("2022-01-01","2026-11-01")
    price_rows.append({
        "Price_ID":              f"PRC-{i+1:06d}",
        "Batch_ID":              brow["Batch_ID"],
        "Product_Name":          brow["Product_Name"],
        "Price_Date":            fmt_date(price_date),
        "Supply_Chain_Stage":    stage,
        "Market_Location":       rand_city(state) + ", " + state,
        "Mandi_Name":            random.choice(["Azadpur Mandi","Vashi APMC","Yeshwanthpur APMC","Koyambedu Market","Gaddiannaram APMC","Gultekdi Market","Lasalgaon Onion Mandi","Unjha Mandi"]),
        "Cost_Per_Unit_INR":     farm_price,
        "Selling_Price_INR":     sell_price,
        "MSP_INR":               round(farm_price * random.uniform(0.85, 1.05), 2),
        "Price_Change_Pct":      round((sell_price-farm_price)/farm_price*100, 2),
        "Currency":              "INR",
        "Unit":                  brow["Unit"],
        "Season":                random.choice(["Kharif","Rabi","Zaid","Year-Round"]),
    })

df_price = pd.DataFrame(price_rows)
print(f"  PRICE_RECORD: {len(df_price)} rows × {len(df_price.columns)} cols")

# ═══════════════════════════════════════════════════════════════════════════════
# 9. BATCH_SHIPMENT bridge  (M:N — Included_In)
# ═══════════════════════════════════════════════════════════════════════════════
print("Building BATCH_SHIPMENT bridge …")
bs_rows = []
for srow in ship_rows:
    for bid in str(srow["Batch_IDs"]).split(";"):
        bid = bid.strip()
        if bid:
            bs_rows.append({"Batch_ID": bid, "Shipment_ID": srow["Shipment_ID"]})
df_bs = pd.DataFrame(bs_rows).drop_duplicates()
print(f"  BATCH_SHIPMENT: {len(df_bs)} rows")

# ═══════════════════════════════════════════════════════════════════════════════
# 10. WRITE EXCEL
# ═══════════════════════════════════════════════════════════════════════════════
SHEET_ORDER = [
    ("FARM",                df_farm),
    ("PROCESSING_FACILITY", df_proc),
    ("RETAILER",            df_ret),
    ("BATCH",               df_batch),
    ("QUALITY_CHECK",       df_qc),
    ("SHIPMENT",            df_ship),
    ("ANOMALY_ALERT",       df_alert),
    ("PRICE_RECORD",        df_price),
    ("BATCH_SHIPMENT",      df_bs),
]

total_rows = sum(len(df) for _, df in SHEET_ORDER)
print(f"\nTotal rows across all sheets: {total_rows:,}")
print(f"Writing → {OUT} …")

with pd.ExcelWriter(OUT, engine="openpyxl") as writer:
    for sheet_name, df in SHEET_ORDER:
        df.to_excel(writer, sheet_name=sheet_name, index=False)
        ws = writer.sheets[sheet_name]
        for col_cells in ws.columns:
            max_len = max((len(str(c.value)) for c in col_cells if c.value is not None), default=8)
            ws.column_dimensions[col_cells[0].column_letter].width = min(max_len + 2, 55)

print("\n✓ Done!")
print(f"\nSheet Summary:")
print(f"{'Sheet':<25} {'Rows':>7}  {'Cols':>5}")
print("-" * 42)
for name, df in SHEET_ORDER:
    print(f"  {name:<23} {len(df):>7,}  {len(df.columns):>5}")
print("-" * 42)
print(f"  {'TOTAL':<23} {total_rows:>7,}")
print(f"\nFile saved: {OUT}")
