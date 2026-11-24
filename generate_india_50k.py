"""
generate_india_50k.py
=====================
Generates a comprehensive Indian food supply chain dataset with:
  - 50,000 FARMS
  - 50,000 BATCHES  (20% veg, 20% fruit, 20% daily essentials, 20% grains, 20% spices/pulses)
  - 3,000  PROCESSING_FACILITY
  - 10,000 RETAILER
  - 50,000 SHIPMENT
  - 60,000 QUALITY_CHECK
  - 15,000 ANOMALY_ALERT
  - 50,000 PRICE_RECORD
  - BATCH_SHIPMENT bridge
Uses numpy vectorised generation for speed.
"""

import json, random, hashlib, math
from datetime import datetime, timedelta
from pathlib import Path
import numpy as np
import pandas as pd

rng = np.random.default_rng(2024)
random.seed(2024)

OUT = Path(r"C:\Users\User\Downloads\DBMS-main\DBMS-main\food-supply-chain-INDIA-50k-v2.xlsx")

N_FARMS    = 50_000
N_BATCHES  = 50_000
N_PROC     =  3_000
N_RETAIL   = 10_000
N_SHIP     = 50_000
N_QC       = 60_000
N_ALERT    = 15_000
N_PRICE    = 50_000

# ═══════════════════════════════════════════════════════════════════════════════
#  COMPREHENSIVE INDIA PLACE DATA
# ═══════════════════════════════════════════════════════════════════════════════
# Format: state -> { districts: [...], cities/towns: [...], pin_base: int }
INDIA = {
    "Andhra Pradesh": {
        "districts": ["Visakhapatnam","East Godavari","West Godavari","Krishna","Guntur","Prakasam","Nellore","Kurnool","Kadapa","Chittoor","Anantapur","Sri Potti Sriramulu Nellore","Tirupati","Bapatla","Eluru"],
        "cities":    ["Visakhapatnam","Vijayawada","Tirupati","Guntur","Nellore","Kurnool","Kakinada","Rajahmundry","Kadapa","Anantapur","Eluru","Ongole","Nandyal","Chittoor","Proddatur","Tenali","Bhimavaram","Machilipatnam","Dharmavaram","Hindupur"],
        "pin_base":  500000, "code": "AP", "gst": 28,
        "lat": (13.5, 19.0), "lon": (77.0, 84.5),
    },
    "Arunachal Pradesh": {
        "districts": ["Papum Pare","West Kameng","East Kameng","Tawang","Lohit"],
        "cities":    ["Itanagar","Naharlagun","Pasighat","Tawang","Bomdila","Ziro","Along","Tezu","Roing","Changlang"],
        "pin_base":  790000, "code": "AR", "gst": 12,
        "lat": (26.5, 29.4), "lon": (91.5, 97.4),
    },
    "Assam": {
        "districts": ["Kamrup","Dibrugarh","Jorhat","Nagaon","Sonitpur","Lakhimpur","Cachar","Dhubri","Goalpara","Barpeta"],
        "cities":    ["Guwahati","Dispur","Dibrugarh","Jorhat","Silchar","Tezpur","Nagaon","Tinsukia","Golaghat","Sivasagar","Lakhimpur","Dhubri","Kokrajhar","Bongaigaon","Hailakandi"],
        "pin_base":  781000, "code": "AS", "gst": 18,
        "lat": (24.1, 27.5), "lon": (89.7, 96.0),
    },
    "Bihar": {
        "districts": ["Patna","Gaya","Bhagalpur","Muzaffarpur","Purnia","Darbhanga","Araria","Aurangabad","Begusarai","Bettiah","Buxar","Chhapra","Danapur","East Champaran","Gopalganj"],
        "cities":    ["Patna","Gaya","Bhagalpur","Muzaffarpur","Purnia","Darbhanga","Arrah","Begusarai","Katihar","Munger","Chapra","Sasaram","Hajipur","Siwan","Motihari","Buxar","Aurangabad","Nawada","Jehanabad","Dehri"],
        "pin_base":  800000, "code": "BR", "gst": 10,
        "lat": (24.3, 27.5), "lon": (83.3, 88.3),
    },
    "Chhattisgarh": {
        "districts": ["Raipur","Bilaspur","Durg","Rajnandgaon","Korba","Raigarh","Janjgir","Jashpur","Kanker","Bastar"],
        "cities":    ["Raipur","Bilaspur","Durg","Bhilai","Korba","Rajnandgaon","Jagdalpur","Ambikapur","Raigarh","Dhamtari","Mahasamund","Chirmiri","Bemetara","Kawardha","Mungeli"],
        "pin_base":  490000, "code": "CG", "gst": 22,
        "lat": (17.8, 24.0), "lon": (80.2, 84.4),
    },
    "Goa": {
        "districts": ["North Goa","South Goa"],
        "cities":    ["Panaji","Margao","Vasco da Gama","Mapusa","Ponda","Calangute","Bicholim","Sanquelim","Curchorem","Canacona"],
        "pin_base":  403000, "code": "GA", "gst": 30,
        "lat": (14.9, 15.8), "lon": (73.7, 74.3),
    },
    "Gujarat": {
        "districts": ["Ahmedabad","Surat","Vadodara","Rajkot","Bhavnagar","Jamnagar","Junagadh","Anand","Gandhinagar","Mehsana","Morbi","Navsari","Vapi","Bharuch","Nadiad","Patan","Dahod","Narmada","Tapi","Valsad"],
        "cities":    ["Ahmedabad","Surat","Vadodara","Rajkot","Bhavnagar","Jamnagar","Junagadh","Gandhinagar","Anand","Mehsana","Morbi","Navsari","Vapi","Bharuch","Nadiad","Patan","Dahod","Surendranagar","Porbandar","Amreli","Botad","Modasa","Deesa","Palanpur","Himatnagar","Godhra","Halol","Ankleshwar"],
        "pin_base":  380000, "code": "GJ", "gst": 24,
        "lat": (20.1, 24.7), "lon": (68.1, 74.5),
    },
    "Haryana": {
        "districts": ["Gurugram","Faridabad","Ambala","Hisar","Rohtak","Panipat","Karnal","Sonipat","Yamunanagar","Rewari","Bhiwani","Sirsa","Jhajjar","Palwal","Panchkula","Nuh","Mahendragarh","Jind","Kaithal","Fatehabad"],
        "cities":    ["Gurugram","Faridabad","Ambala","Hisar","Rohtak","Panipat","Karnal","Sonipat","Yamunanagar","Rewari","Bhiwani","Sirsa","Jhajjar","Palwal","Panchkula","Bahadurgarh","Hansi","Fatehabad","Kaithal","Jind","Narnaul","Narwana","Tohana","Pehowa","Thanesar"],
        "pin_base":  121000, "code": "HR", "gst": 6,
        "lat": (27.6, 30.9), "lon": (74.4, 77.6),
    },
    "Himachal Pradesh": {
        "districts": ["Shimla","Mandi","Kullu","Kangra","Hamirpur","Una","Chamba","Bilaspur","Sirmaur","Solan"],
        "cities":    ["Shimla","Dharamshala","Mandi","Solan","Kullu","Manali","Hamirpur","Una","Chamba","Bilaspur","Paonta Sahib","Nahan","Rampur","Baddi","Nalagarh"],
        "pin_base":  171000, "code": "HP", "gst": 2,
        "lat": (30.4, 33.2), "lon": (75.6, 79.0),
    },
    "Jharkhand": {
        "districts": ["Ranchi","Dhanbad","Bokaro","Jamshedpur","Hazaribag","Deoghar","Giridih","Ramgarh","Palamu","Chatra"],
        "cities":    ["Ranchi","Dhanbad","Bokaro","Jamshedpur","Hazaribag","Deoghar","Giridih","Ramgarh","Medininagar","Chatra","Simdega","Lohardaga","Phusro","Chas","Adityapur"],
        "pin_base":  825000, "code": "JH", "gst": 20,
        "lat": (21.9, 25.3), "lon": (83.3, 87.9),
    },
    "Karnataka": {
        "districts": ["Bengaluru Urban","Mysuru","Hubli-Dharwad","Mangaluru","Belagavi","Davanagere","Ballari","Vijayapura","Shivamogga","Tumakuru","Raichur","Bidar","Kalaburagi","Udupi","Hassan","Kodagu","Chitradurga","Haveri","Gadag","Koppal"],
        "cities":    ["Bengaluru","Mysuru","Hubli","Mangaluru","Belagavi","Davanagere","Ballari","Vijayapura","Shivamogga","Tumakuru","Raichur","Bidar","Kalaburagi","Udupi","Hassan","Madikeri","Chitradurga","Haveri","Gadag","Koppal","Ramanagara","Chikkamagaluru","Bagalkot","Karwar","Sirsi","Bhadravati","Hosapete","Gangavathi"],
        "pin_base":  560000, "code": "KA", "gst": 29,
        "lat": (11.6, 18.5), "lon": (74.0, 78.6),
    },
    "Kerala": {
        "districts": ["Thiruvananthapuram","Kollam","Pathanamthitta","Alappuzha","Kottayam","Idukki","Ernakulam","Thrissur","Palakkad","Malappuram","Kozhikode","Wayanad","Kannur","Kasaragod"],
        "cities":    ["Thiruvananthapuram","Kochi","Kozhikode","Thrissur","Kollam","Palakkad","Alappuzha","Malappuram","Kannur","Kottayam","Kasaragod","Pathanamthitta","Chalakudy","Thalassery","Manjeri","Vatakara","Perinthalmanna","Tirur","Irinjalakuda","Kayamkulam","Changanacherry","Pala","Muvattupuzha","Kothamangalam"],
        "pin_base":  682000, "code": "KL", "gst": 32,
        "lat": (8.3, 12.8), "lon": (74.9, 77.4),
    },
    "Madhya Pradesh": {
        "districts": ["Bhopal","Indore","Jabalpur","Gwalior","Ujjain","Rewa","Satna","Sagar","Dewas","Murwara","Chhindwara","Ratlam","Burhanpur","Khandwa","Vidisha","Hoshangabad","Balaghat","Chhatarpur","Damoh","Datia"],
        "cities":    ["Bhopal","Indore","Jabalpur","Gwalior","Ujjain","Rewa","Satna","Sagar","Dewas","Murwara","Chhindwara","Ratlam","Burhanpur","Khandwa","Vidisha","Hoshangabad","Balaghat","Chhatarpur","Damoh","Datia","Singrauli","Shivpuri","Morena","Bhind","Guna","Mandsaur","Neemuch","Shajapur","Agar Malwa","Narsinghpur"],
        "pin_base":  462000, "code": "MP", "gst": 23,
        "lat": (21.1, 26.9), "lon": (74.0, 82.8),
    },
    "Maharashtra": {
        "districts": ["Mumbai City","Mumbai Suburban","Thane","Pune","Nashik","Aurangabad","Nagpur","Solapur","Kolhapur","Amravati","Latur","Jalgaon","Akola","Satara","Sangli","Osmanabad","Nanded","Parbhani","Beed","Hingoli","Washim","Yavatmal","Buldhana","Wardha","Chandrapur","Gadchiroli","Gondia","Bhandara","Ratnagiri","Sindhudurg","Raigad","Dhule","Nandurbar","Jalna","Ahmednagar"],
        "cities":    ["Mumbai","Pune","Nagpur","Nashik","Aurangabad","Solapur","Kolhapur","Thane","Navi Mumbai","Amravati","Latur","Jalgaon","Akola","Satara","Sangli","Osmanabad","Nanded","Parbhani","Beed","Wardha","Chandrapur","Gondia","Ratnagiri","Dhule","Jalna","Ahmednagar","Shirdi","Ichalkaranji","Pandharpur","Kalyan","Dombivli","Vasai","Virar","Bhiwandi","Ulhasnagar"],
        "pin_base":  400000, "code": "MH", "gst": 27,
        "lat": (15.6, 22.0), "lon": (72.6, 80.9),
    },
    "Manipur": {
        "districts": ["Imphal West","Imphal East","Thoubal","Bishnupur","Senapati"],
        "cities":    ["Imphal","Thoubal","Bishnupur","Churachandpur","Senapati","Ukhrul","Tamenglong","Chandel","Moreh","Jiribam"],
        "pin_base":  795000, "code": "MN", "gst": 14,
        "lat": (23.8, 25.7), "lon": (93.0, 94.8),
    },
    "Meghalaya": {
        "districts": ["East Khasi Hills","West Khasi Hills","Ri Bhoi","South Garo Hills","West Garo Hills"],
        "cities":    ["Shillong","Tura","Jowai","Nongstoin","Baghmara","Williamnagar","Resubelpara","Mawkyrwat","Nongpoh","Cherrapunji"],
        "pin_base":  793000, "code": "ML", "gst": 17,
        "lat": (25.0, 26.1), "lon": (89.8, 92.8),
    },
    "Mizoram": {
        "districts": ["Aizawl","Lunglei","Champhai","Kolasib","Serchhip"],
        "cities":    ["Aizawl","Lunglei","Champhai","Kolasib","Serchhip","Siaha","Lawngtlai","Mamit","Saiha","Hnahthial"],
        "pin_base":  796000, "code": "MZ", "gst": 15,
        "lat": (21.9, 24.5), "lon": (92.3, 93.5),
    },
    "Nagaland": {
        "districts": ["Kohima","Dimapur","Mokokchung","Tuensang","Wokha"],
        "cities":    ["Kohima","Dimapur","Mokokchung","Tuensang","Wokha","Mon","Phek","Zunheboto","Longleng","Peren"],
        "pin_base":  797000, "code": "NL", "gst": 13,
        "lat": (25.2, 27.0), "lon": (93.3, 95.3),
    },
    "Odisha": {
        "districts": ["Bhubaneswar","Cuttack","Rourkela","Brahmapur","Puri","Sambalpur","Balasore","Baripada","Bhadrak","Jeypore","Jharsuguda","Rayagada","Angul","Kendujhar","Dhenkanal","Koraput","Bolangir","Bargarh","Mayurbhanj","Khordha"],
        "cities":    ["Bhubaneswar","Cuttack","Rourkela","Brahmapur","Puri","Sambalpur","Balasore","Baripada","Bhadrak","Jeypore","Jharsuguda","Rayagada","Angul","Kendujhar","Dhenkanal","Koraput","Titlagarh","Bargarh","Phulbani","Bhawanipatna"],
        "pin_base":  751000, "code": "OR", "gst": 21,
        "lat": (17.8, 22.6), "lon": (81.4, 87.5),
    },
    "Punjab": {
        "districts": ["Amritsar","Ludhiana","Jalandhar","Patiala","Bathinda","Mohali","Hoshiarpur","Gurdaspur","Ferozepur","Faridkot","Moga","Pathankot","Sangrur","Barnala","Muktsar","Mansa","Nawanshahr","Fatehgarh Sahib","Kapurthala","Rupnagar"],
        "cities":    ["Amritsar","Ludhiana","Jalandhar","Patiala","Bathinda","Mohali","Hoshiarpur","Gurdaspur","Ferozepur","Faridkot","Moga","Pathankot","Sangrur","Barnala","Muktsar","Mansa","Nawanshahr","Khanna","Phagwara","Abohar","Malout","Rajpura","Zirakpur","Morinda"],
        "pin_base":  140000, "code": "PB", "gst": 3,
        "lat": (29.5, 32.5), "lon": (73.9, 76.9),
    },
    "Rajasthan": {
        "districts": ["Jaipur","Jodhpur","Udaipur","Kota","Ajmer","Bikaner","Alwar","Bharatpur","Sikar","Pali","Bhilwara","Hanumangarh","Chittorgarh","Nagaur","Barmer","Jaisalmer","Jhunjhunu","Tonk","Bundi","Baran","Jhalawar","Dausa","Karauli","Sawai Madhopur","Sirohi","Jalore","Banswara","Dungarpur","Pratapgarh","Rajsamand"],
        "cities":    ["Jaipur","Jodhpur","Udaipur","Kota","Ajmer","Bikaner","Alwar","Bharatpur","Sikar","Pali","Bhilwara","Hanumangarh","Chittorgarh","Nagaur","Barmer","Jaisalmer","Jhunjhunu","Tonk","Bundi","Sri Ganganagar","Kishangarh","Beawar","Makrana","Sujangarh","Lachhmangarh","Fatehpur","Churu","Sawai Madhopur","Sirohi","Balotra"],
        "pin_base":  302000, "code": "RJ", "gst": 8,
        "lat": (23.0, 30.2), "lon": (69.5, 78.3),
    },
    "Sikkim": {
        "districts": ["East Sikkim","West Sikkim","North Sikkim","South Sikkim"],
        "cities":    ["Gangtok","Namchi","Mangan","Jorethang","Rangpo","Singtam","Gyalshing","Ravangla","Chungthang","Soreng"],
        "pin_base":  737000, "code": "SK", "gst": 11,
        "lat": (27.1, 28.1), "lon": (88.0, 88.9),
    },
    "Tamil Nadu": {
        "districts": ["Chennai","Coimbatore","Madurai","Tiruchirappalli","Salem","Tirunelveli","Tiruppur","Vellore","Erode","Thoothukkudi","Dindigul","Cuddalore","Thanjavur","Kancheepuram","Krishnagiri","Dharmapuri","Villupuram","Perambalur","Ariyalur","Nagapattinam","Tiruvarur","Ramanathapuram","Sivaganga","Virudhunagar","Pudukkottai","Karur","Namakkal","Nilgiris","Tenkasi","Ranipet"],
        "cities":    ["Chennai","Coimbatore","Madurai","Tiruchirappalli","Salem","Tirunelveli","Tiruppur","Vellore","Erode","Thoothukkudi","Dindigul","Cuddalore","Thanjavur","Kancheepuram","Krishnagiri","Dharmapuri","Villupuram","Nagapattinam","Ramanathapuram","Karur","Namakkal","Ooty","Hosur","Nagercoil","Tambaram","Avadi","Ambattur","Kumbakonam","Tiruvannamalai","Sivakasi"],
        "pin_base":  600000, "code": "TN", "gst": 33,
        "lat": (8.1, 13.6), "lon": (76.2, 80.4),
    },
    "Telangana": {
        "districts": ["Hyderabad","Warangal","Nizamabad","Khammam","Karimnagar","Ramagundam","Mahbubnagar","Nalgonda","Adilabad","Suryapet","Miryalaguda","Mancherial","Jagtial","Siddipet","Bhongir","Sangareddy","Vikarabad","Wanaparthy","Narayanpet","Mahabubabad"],
        "cities":    ["Hyderabad","Warangal","Nizamabad","Khammam","Karimnagar","Ramagundam","Mahbubnagar","Nalgonda","Adilabad","Suryapet","Miryalaguda","Mancherial","Jagtial","Siddipet","Bhongir","Sangareddy","Zahirabad","Bodhan","Bhadrachalam","Kothagudem","Palwancha","Jadcherla","Narayanpet","Tandur"],
        "pin_base":  500000, "code": "TS", "gst": 36,
        "lat": (15.9, 19.9), "lon": (77.2, 81.3),
    },
    "Tripura": {
        "districts": ["West Tripura","South Tripura","Gomati","Dhalai","North Tripura"],
        "cities":    ["Agartala","Dharmanagar","Udaipur","Kailashahar","Belonia","Khowai","Ambassa","Sonamura","Sabroom","Melaghar"],
        "pin_base":  799000, "code": "TR", "gst": 16,
        "lat": (22.9, 24.5), "lon": (91.2, 92.3),
    },
    "Uttar Pradesh": {
        "districts": ["Lucknow","Agra","Varanasi","Kanpur","Allahabad","Meerut","Bareilly","Aligarh","Gorakhpur","Noida","Ghaziabad","Mathura","Moradabad","Saharanpur","Firozabad","Muzaffarnagar","Shahjahanpur","Rampur","Jhansi","Bijnor","Budaun","Hardoi","Lakhimpur","Sitapur","Unnao","Fatehpur","Rae Bareli","Banda","Chitrakoot","Mahoba"],
        "cities":    ["Lucknow","Agra","Varanasi","Kanpur","Prayagraj","Meerut","Bareilly","Aligarh","Gorakhpur","Noida","Ghaziabad","Mathura","Moradabad","Saharanpur","Firozabad","Muzaffarnagar","Shahjahanpur","Rampur","Jhansi","Bijnor","Budaun","Hardoi","Lakhimpur Kheri","Sitapur","Unnao","Fatehpur","Rae Bareli","Banda","Orai","Etawah","Farrukhabad","Hathras","Etah","Mainpuri","Auraiya"],
        "pin_base":  200000, "code": "UP", "gst": 9,
        "lat": (23.9, 30.4), "lon": (77.1, 84.6),
    },
    "Uttarakhand": {
        "districts": ["Dehradun","Haridwar","Nainital","Udham Singh Nagar","Almora","Pauri","Tehri","Chamoli","Pithoragarh","Bageshwar"],
        "cities":    ["Dehradun","Haridwar","Nainital","Rudrapur","Haldwani","Roorkee","Rishikesh","Kashipur","Almora","Srinagar","Kotdwar","Ramnagar","Pauri","Pithoragarh","Champawat"],
        "pin_base":  248000, "code": "UK", "gst": 5,
        "lat": (28.7, 31.5), "lon": (77.6, 81.1),
    },
    "West Bengal": {
        "districts": ["Kolkata","Howrah","Durgapur","Asansol","Siliguri","Bardhaman","Malda","Baharampur","Krishnanagar","Bankura","Purulia","Kharagpur","Haldia","Jalpaiguri","Cooch Behar","North 24 Parganas","South 24 Parganas","Hooghly","Nadia","Murshidabad","Birbhum","West Midnapore","East Midnapore","Paschim Bardhaman"],
        "cities":    ["Kolkata","Howrah","Durgapur","Asansol","Siliguri","Bardhaman","Malda","Baharampur","Krishnanagar","Bankura","Purulia","Kharagpur","Haldia","Jalpaiguri","Cooch Behar","Barasat","Diamond Harbour","Raiganj","Balurghat","Alipurduar","Basirhat","Bongaon","Chakdaha","Nabadwip","Kalna"],
        "pin_base":  700000, "code": "WB", "gst": 19,
        "lat": (21.5, 27.2), "lon": (85.8, 89.9),
    },
}

# ═══════════════════════════════════════════════════════════════════════════════
#  FOOD PRODUCT DEFINITIONS  (20% each category)
# ═══════════════════════════════════════════════════════════════════════════════
CATEGORIES = {
    "Vegetables": {
        "products": [
            # Solanaceae / Common
            "Tomato (Desi)","Tomato (Hybrid F1)","Tomato (Cherry)","Tomato (Roma)","Tomato (Beefsteak)",
            "Potato (Kufri Jyoti)","Potato (Kufri Pukhraj)","Potato (Kufri Bahar)","Potato (Kufri Chandramukhi)","Potato (Kufri Sindhuri)",
            "Brinjal (Round Purple)","Brinjal (Long Green)","Brinjal (White)","Brinjal (Striped)","Brinjal (Baby)",
            "Onion (Nasik Red)","Onion (Puna Fursungi)","Onion (White)","Onion (Shallot / Sambar Onion)","Spring Onion",
            "Capsicum (Green)","Capsicum (Red)","Capsicum (Yellow)","Capsicum (Orange)","Green Chilli (Jwala)",
            "Green Chilli (Guntur)","Green Chilli (Kanthari)","Green Chilli (Bhut Jolokia)","Banana Pepper","Chilli Pepper (Long)",
            # Gourds
            "Okra / Bhindi (Parbhani Kranti)","Okra / Bhindi (Arka Anamika)","Okra / Bhindi (HB-10)","Okra (Baby)","Okra (Red)",
            "Bitter Gourd (Karela – Long)","Bitter Gourd (Karela – Round)","Bitter Gourd (White)","Bitter Gourd (Mini)",
            "Bottle Gourd (Lauki – Long)","Bottle Gourd (Lauki – Round)","Ridge Gourd (Turai)","Sponge Gourd (Galka)",
            "Ash Gourd (Petha)","Snake Gourd (Chichinda)","Ivy Gourd (Tindora / Kundru)","Pointed Gourd (Parwal)",
            "Pumpkin (Orange)","Pumpkin (Green)","Pumpkin (White)","Squash (Green)","Squash (Yellow)",
            # Leafy Greens
            "Spinach (Palak – Desi)","Spinach (Palak – Hybrid)","Fenugreek Leaves (Methi)","Amaranth Leaves (Chaulai)",
            "Mustard Leaves (Sarson Ka Saag)","Bathua Leaves","Drumstick Leaves (Moringa)","Colocasia Leaves (Arbi Patta)",
            "Curry Leaves (Fresh)","Coriander Leaves (Dhaniya)","Mint Leaves (Pudina)","Sorrel Leaves (Khatta Palak)",
            "Cauliflower (White)","Cauliflower (Green / Broccoli Hybrid)","Broccoli","Cabbage (Green)","Cabbage (Red)","Cabbage (Savoy)",
            "Lettuce (Iceberg)","Lettuce (Romaine)","Kale","Bok Choy","Celery","Leek","Dill (Suwa)",
            # Root & Tuber
            "Carrot (Pusa Kesar)","Carrot (Nantes)","Carrot (Purple)","Radish (Mooli – Long White)","Radish (Red Round)",
            "Beetroot (Red)","Beetroot (Golden)","Turnip (Shalgam)","Yam (Suran)","Elephant Foot Yam","Colocasia (Arbi)",
            "Sweet Potato (Shakarkand – Orange)","Sweet Potato (Shakarkand – White)","Cassava (Tapioca)","Lotus Root (Kamal Kakdi)",
            # Legume Vegetables
            "Green Peas (Matar)","Snow Peas","Sugar Snap Peas","French Beans","Cluster Beans (Gawar)",
            "Broad Beans (Sem)","Hyacinth Beans (Val Papdi)","Cowpea (Chawli Pods)","Dolichos Bean (Avarekai)","Lima Beans (Fresh)",
            # Others
            "Sweet Corn (Yellow)","Sweet Corn (White)","Baby Corn","Mushroom (Button)","Mushroom (Oyster)",
            "Mushroom (Shiitake)","Garlic (Desi)","Garlic (Hybrid White)","Ginger (Green)","Turmeric (Raw / Green)",
            "Zucchini (Green)","Zucchini (Yellow)","Artichoke","Asparagus","Fennel Bulb (Saunf)",
            "Cucumber (Desi)","Cucumber (English Long)","Cucumber (Mini/Cocktail)","Drumstick (Moringa Pods)","Water Chestnut (Singhara)",
        ],
        "unit": ["KG","Quintal","MT","Boxes (10 kg)","Crates (20 kg)"],
        "price_range_inr": (5, 150),
        "shelf_days": (2, 30),
        "farm_types": ["Vegetable Farm","Organic Vegetable Farm","Polyhouse Farm","Protected Cultivation","Drip-Irrigated Farm","Kitchen Garden (Commercial)"],
    },
    "Fruits": {
        "products": [
            # Mango Varieties
            "Mango – Alphonso (Hapus)","Mango – Kesar","Mango – Dasheri","Mango – Langra","Mango – Himsagar",
            "Mango – Banganapalli (Safeda)","Mango – Totapuri","Mango – Chausa","Mango – Neelam","Mango – Mallika",
            "Mango – Amrapali","Mango – Sindhura","Mango – Raspuri","Mango – Badami","Mango – Pairi",
            # Banana Varieties
            "Banana – Robusta (Cavendish)","Banana – Nendran (Kerala)","Banana – Red Banana","Banana – Poovan (Yelakki)","Banana – G9",
            "Banana – Karpooravalli","Banana – Monthan (Raw / Cooking)","Banana – Dwarf Cavendish","Banana – Giant Governor","Banana – Basrai",
            # Citrus
            "Orange – Nagpur Mandarin","Orange – Coorg Mandarin","Orange – Valencia","Orange – Navel","Orange – Kinnow",
            "Mosambi (Sweet Lime)","Lemon (Kagzi)","Lemon (Eureka)","Lime (Tahiti)","Grapefruit","Pomelo (Chakotra)","Citron (Bijora)",
            # Apple & Pear
            "Apple – Shimla (Royal Delicious)","Apple – Kashmiri (Ambri)","Apple – Golden Delicious","Apple – Fuji","Apple – Granny Smith",
            "Apple – Kinnaur (Himachali)","Pear (Nashpati – Baggugosha)","Pear – Red Anjou","Pear – Conference","Quince (Bahi)",
            # Grapes
            "Grapes – Thompson Seedless","Grapes – Sharad Seedless","Grapes – Black Muscat","Grapes – Flame Seedless",
            "Grapes – Bangalore Blue","Grapes – Perlette","Grapes – Red Globe","Grapes – Italia (Green)",
            # Tropical
            "Papaya (Pusa Dwarf)","Papaya (Red Lady)","Guava (Allahabad Safeda)","Guava (L-49 Lucknow)","Guava (Red-fleshed)",
            "Pomegranate (Bhagwa)","Pomegranate (Wonderful)","Pomegranate (Mridula)","Pineapple (Kew)","Pineapple (Queen)",
            "Watermelon (Sugar Baby)","Watermelon (Crimson Sweet)","Watermelon (Black Beauty)","Muskmelon (Hara Madhu)","Muskmelon (Punjab Sunehri)",
            "Coconut (Tender Green)","Coconut (Mature Brown)","Jackfruit (Kathal)","Custard Apple (Sitaphal)","Ramphal (Bullock's Heart)",
            # Berries & Stone Fruits
            "Strawberry (Camarosa)","Strawberry (Winter Dawn)","Litchi (Shahi)","Litchi (China)","Jamun (Black Plum)",
            "Plum (Aloo Bukhara – Red)","Plum (Green Gage)","Peach (Sharbati)","Apricot (Chuli / Khurmani)","Cherry (Kashmiri)",
            "Indian Fig (Anjeer – Fresh)","Mulberry (Black)","Mulberry (White)","Falsa (Grewia asiatica)","Karonda",
            # Exotic / Emerging
            "Dragon Fruit (Red-fleshed)","Dragon Fruit (White-fleshed)","Avocado (Hass)","Kiwi (Hayward)","Passion Fruit (Yellow)",
            "Rambuttan","Mangosteen","Longan","Sapodilla (Chikoo – Kalipatti)","Sapodilla (Cricket Ball)",
            "Cape Gooseberry (Rasbhari)","Star Fruit (Kamrakh)","Wood Apple (Bael)","Tamarind (Sweet)","Amla (Indian Gooseberry)",
            "Kokum (Fruit)","Bilimbi","Malay Apple (Jambu)","Langsat","Durian",
        ],
        "unit": ["KG","Quintal","MT","Dozens","Crates (20 kg)","Boxes (10 kg)"],
        "price_range_inr": (10, 1000),
        "shelf_days": (3, 90),
        "farm_types": ["Fruit Orchard","Mango Plantation","Banana Plantation","Citrus Orchard","Tropical Fruit Farm","Apple Orchard (Himachal)","Grape Vineyard"],
    },
    "Daily Essentials": {
        "products": [
            # Milk
            "Full Cream Milk (3.5% fat)","Toned Milk (1.5% fat)","Double Toned Milk (1% fat)","Skimmed Milk (0% fat)","Buffalo Milk (6% fat)",
            "Goat Milk","Camel Milk","Soy Milk (Fortified)","Oat Milk","Coconut Milk (Liquid)",
            # Curd / Yogurt / Fermented
            "Dahi – Cow Curd (Full Fat)","Dahi – Buffalo Curd","Greek Yogurt (Strained)","Mishti Doi (Sweetened Curd)","Hung Curd (Chakka)",
            "Lassi (Plain)","Lassi (Sweet)","Lassi (Salted)","Buttermilk (Chaas)","Kefir",
            # Paneer / Khoa / Cream
            "Paneer (Fresh Block)","Paneer (Crumbled)","Paneer (Low Fat)","Khoa / Mawa (Hard)","Khoa / Mawa (Soft – Chikna)",
            "Cream (25% fat)","Whipping Cream","Malai (Clotted Cream)","Rabri","Condensed Milk (Sweetened)",
            # Ghee / Butter / Cheese
            "Ghee – Cow (A2)","Ghee – Buffalo","Ghee – Mixed","Ghee – Organic Desi","Ghee – Cultured",
            "Butter – Salted (Table)","Butter – Unsalted","Butter – White (Makkhan)","Cheese – Processed Slice","Cheese – Cheddar Block",
            "Cheese – Mozzarella Ball","Cheese – Cottage","Cheese – Gouda","Cheese – Parmesan Grated","Cheese – Cream (Spread)",
            # Oils
            "Groundnut Oil (Filtered)","Groundnut Oil (Refined)","Mustard Oil (Kachi Ghani – Cold Pressed)","Mustard Oil (Refined)",
            "Refined Sunflower Oil","Refined Soybean Oil","Coconut Oil (Virgin Cold Pressed)","Coconut Oil (Refined)",
            "Rice Bran Oil","Palm Olein Oil","Sesame Oil – Til Oil (Cold Pressed)","Sesame Oil (Refined)",
            "Canola Oil","Corn Oil","Blended Vegetable Oil (PVNO)","Flaxseed Oil","Olive Oil (Pomace)","Olive Oil (Extra Virgin)",
            # Sugar / Sweeteners
            "Refined Sugar (S-30 Grade)","Refined Sugar (M-30 Grade)","Jaggery – Gur (Hard Block)","Jaggery – Gur (Soft)","Jaggery Powder",
            "Palm Jaggery (Karuppati)","Coconut Sugar","Brown Sugar (Demerara)","Powdered Sugar (Icing)","Caster Sugar",
            "Honey (Raw Wildflower)","Honey (Ajwain)","Honey (Litchi)","Honey (Mustard)","Date Syrup","Stevia Powder","Mishri (Rock Sugar)",
            # Salt
            "Salt – Iodized (Fine)","Salt – Rock (Sendha Namak)","Salt – Black (Kala Namak)","Salt – Sea Salt","Salt – Pink Himalayan",
            "Salt – Low Sodium","Salt – Kosher","Pickle Salt (Coarse)","Salt – Flaky (Fleur de Sel)","Salt – Smoked",
            # Rice (Staple)
            "Rice – Basmati (1121 Extra Long)","Rice – Basmati (Pusa 1509)","Rice – Basmati (Traditional Dehraduni)",
            "Rice – Sona Masoori","Rice – Ponni (Raw)","Rice – Idli Rice (Boiled)","Rice – Brown Basmati",
            "Rice – Red Rice (Matta)","Rice – Black Rice (Forbidden)","Rice – Parboiled (IR-64)",
        ],
        "unit": ["Litre","KG","MT","Tin (15 L)","Pouch (500 ml)","Packet (1 kg)"],
        "price_range_inr": (20, 600),
        "shelf_days": (1, 730),
        "farm_types": ["Dairy Farm","A2 Cow Farm","Buffalo Dairy","Sugarcane Farm","Oil Seed Farm","Rice Paddy","Mixed Crop Farm"],
    },
    "Grains": {
        "products": [
            # Wheat
            "Wheat – Lok-1 (Dudhiya)","Wheat – PBW-343","Wheat – PBW-621","Wheat – Sharbati (HI-8498)","Wheat – Raj-4120",
            "Wheat – GW-322","Wheat – HD-2781","Wheat – HD-3086 (Pusa Wheat)","Wheat – K-307","Wheat – Durum (Malvi)",
            "Wheat Flour – Atta (Fine Chakki)","Wheat Flour – Atta (Coarse Chakki)","Maida (Refined Wheat Flour)","Suji – Semolina (Fine)","Suji – Semolina (Coarse)",
            "Wheat Bran","Wheat Germ","Whole Wheat Broken (Dalia)","Wheat Starch","Wheat Gluten",
            # Rice (Raw grain)
            "Paddy – Swarna (MTU-7029)","Paddy – IR-36","Paddy – PR-114","Paddy – Pusa-44","Paddy – BPT-5204 (Samba Mahsuri)",
            "Paddy – NDR-359","Paddy – Sarjoo-52","Paddy – Jaya","Paddy – Masuri (MTU-1001)","Paddy – ADT-36",
            "Rice – Flattened (Poha Thin)","Rice – Flattened (Poha Thick)","Rice – Puffed (Murmura)","Rice Flour (Fine)","Rice Starch",
            # Millets
            "Jowar – Sorghum (White)","Jowar – Sorghum (Red)","Jowar Flour","Bajra – Pearl Millet (HHB-67)","Bajra – Pearl Millet (Raj-171)",
            "Bajra Flour","Ragi – Finger Millet (GPU-28)","Ragi – Finger Millet (MR-6)","Ragi Flour","Ragi Malt (Sprouted)",
            "Foxtail Millet (Kangni / Thinai)","Little Millet (Kutki / Samai)","Kodo Millet (Kodra / Varagu)","Barnyard Millet (Jhangora / Kuthiravali)","Proso Millet (Chena / Panivaragu)",
            "Browntop Millet (Korle)","Sorghum Popped","Ragi Cookies (Bulk Ingredient)","Millet Mix (Multi-grain)","Quinoa (Imported)",
            # Maize / Corn
            "Maize – Yellow (Hybrid Dekkalb)","Maize – White Desi","Maize – Sweet Corn (Fresh Cob Grain)","Corn Flour (Makkai Atta)","Corn Starch",
            "Popcorn Maize (Butterfly)","Popcorn Maize (Mushroom)","Tortilla Corn","Waxy Corn","Baby Corn (Dried)",
            # Oats / Barley / Others
            "Oats – Rolled (Flakes)","Oats – Steel Cut","Oats – Instant","Barley (Jau – Whole)","Barley – Pearled",
            "Barley Flour","Barley Malt","Buckwheat (Kuttu)","Buckwheat Flour","Amaranth Grain (Rajgira)",
            "Amaranth Flour","Water Chestnut Flour (Singhara Atta)","Lotus Seed (Makhana)","Sabudana (Tapioca Pearls)","Arrowroot Starch",
            # Pulses / Dals
            "Toor Dal – Pigeon Pea (Whole)","Toor Dal (Split Polished)","Toor Dal – Marathi Mogga","Toor Dal – Lal Toor",
            "Moong Dal – Yellow (Split Dehusked)","Moong Dal – Green Whole","Moong Dal – Black (Sabut)","Moong Dal – Washed",
            "Chana Dal – Bengal Gram (Split)","Chana – Desi (Brown Whole)","Chana – Kabuli (White Chickpea)","Chana – Green Whole",
            "Urad Dal – Black Whole (Sabut Maa)","Urad Dal – White Split (Dhuli)","Urad Dal – Chilka (Split Unhusked)",
            "Masoor Dal – Red (Split Dehusked)","Masoor Dal – Whole Green (Sabut)","Masoor Dal – Pink Whole",
            "Rajma – Red Kidney Bean (Kashmiri)","Rajma – Light Red (Chitra)","Rajma – Black Kidney",
            "Moth Dal – Dew Bean","Lobiya – Black Eye Pea (White)","Lobiya – Red Cowpea","Val Dal – Hyacinth Bean","Kulthi – Horse Gram",
        ],
        "unit": ["KG","Quintal","MT","Bags (50 kg)","Bags (100 kg)","Gunny Bag"],
        "price_range_inr": (20, 350),
        "shelf_days": (90, 730),
        "farm_types": ["Wheat Farm","Rice Paddy","Grain Farm","Millet Farm","Pulse Farm","Mixed Crop Farm","Organic Grain Farm","Dal Mill Outgrower"],
    },
    "Spices & Dry Fruits": {
        "products": [
            # Turmeric
            "Turmeric – Raw Rhizome (Salem)","Turmeric – Raw Rhizome (Erode)","Turmeric – Raw (Alleppey)","Turmeric Powder (High Curcumin)","Turmeric Powder (Low Curcumin)",
            # Chilli
            "Red Chilli – Dry (Guntur Sannam S4)","Red Chilli – Dry (Byadagi / Kaddi)","Red Chilli – Dry (Kashmiri – Mild)","Red Chilli – Dry (Kanthari White)","Red Chilli – Dry (Bhut Jolokia Dry)",
            "Red Chilli Powder (Extra Hot)","Red Chilli Powder (Mild Colour)","Paprika Powder","Chilli Flakes","Chilli Seeds",
            # Pepper
            "Black Pepper – Whole (Malabar Garbled)","Black Pepper – Whole (Tellicherry Extra Bold)","Black Pepper – Ground","White Pepper (Whole)","White Pepper (Ground)",
            "Green Pepper (Brine)","Long Pepper (Pipli)","Cubeb Pepper (Kabab Chini)","Pink Pepper","Szechuan Pepper",
            # Cardamom / Cloves / Cinnamon
            "Green Cardamom (Small – Premium 7mm+)","Green Cardamom (Medium 6mm)","Green Cardamom (Small 4-5mm)","Green Cardamom Powder","Black Cardamom (Badi Elaichi)",
            "Cloves – Whole (Zanzibar Type)","Cloves – Whole (Indian)","Clove Powder","Cinnamon – True Ceylon (Thin Quills)","Cinnamon – Cassia (Thick)",
            "Cinnamon Powder","Cinnamon Sticks (Broken)","Cassia Bark","Mace (Javitri – Whole Blade)","Mace Powder",
            # Cumin / Coriander / Others
            "Cumin Seeds – Jeera (Gujarat Bold)","Cumin Seeds – Jeera (Rajasthan Thin)","Cumin Powder","Black Cumin (Kalonji / Nigella)","Caraway Seeds (Shahjeera)",
            "Coriander Seeds (Eagle)","Coriander Powder","Fennel Seeds (Lucknow Saunf)","Fennel Seeds (Small Madurai)","Fenugreek Seeds (Methi Dana)",
            "Mustard Seeds – Black (Rai)","Mustard Seeds – Yellow","Mustard Powder","Ajwain (Carom Seeds)","Celery Seeds",
            # Exotic Spices
            "Nutmeg (Jaiphal – Whole)","Nutmeg (Ground)","Asafoetida / Hing (Compound)","Asafoetida / Hing (Pure Resin)","Saffron – Kashmiri (Mongra Grade)",
            "Saffron – Kashmiri (Laccha Grade)","Vanilla Pods (Grade A)","Vanilla Powder","Star Anise (Chakri Phool)","Bay Leaves (Tej Patta – Fresh Dry)",
            "Curry Leaves (Dried)","Kaffir Lime Leaves (Dry)","Lemongrass (Dry)","Galangal (Dry)","Tamarind (Imli – Block)",
            "Tamarind (Seedless Paste)","Kokum (Dried Rind)","Amchur Powder (Dried Mango)","Dry Ginger Powder (Saunth)","Pomegranate Seeds (Anardana – Dry)",
            # Blended Masalas
            "Garam Masala","Chaat Masala","Chole / Chana Masala","Biryani Masala","Pav Bhaji Masala",
            "Sambar Masala","Rasam Powder","Meat / Chicken Masala","Fish Curry Masala","Dal Makhani Masala",
            # Dry Fruits
            "Cashew – W180 (Jumbo)","Cashew – W240 (Premium)","Cashew – W320 (Standard)","Cashew – W450 (Small)","Cashew Splits",
            "Almonds – Gurbandi (Desi)","Almonds – Mamra (Iranian Type)","Almonds – California Long","Almond Flour (Blanched)","Almond Oil",
            "Raisins – Green Kishmish (Seedless)","Raisins – Black (Monukka)","Raisins – Golden","Pistachios – Roasted Salted","Pistachios – Raw Shelled",
            "Walnuts – Whole (Kashmiri Light)","Walnut Kernels (Halves & Pieces)","Hazelnuts (Pilu)","Peanuts – Bold (In Shell)","Peanuts – Redskin Kernels",
            "Dates – Medjool (Saudi)","Dates – Kimia (Iranian)","Dates – Piarom","Dates – Ajwa","Dates – Zahidi (Dry)",
            "Figs – Dried (Anjeer – Afghan)","Figs – Dried (Turkish)","Apricot – Dried (Khurmani – Soft)","Apricot – Dried (Hard – Ladakhi)","Prunes (Dried Plum)",
            "Chironji (Charoli) Seeds","Pine Nuts (Chilgoza – Himalayan)","Fox Nuts (Makhana – Grade A)","Fox Nuts (Makhana – Grade B)","Lotus Seeds (Dried)",
        ],
        "unit": ["KG","Quintal","MT","Grams (bulk 25 kg bag)","Bags (25 kg)","Tin (5 kg)"],
        "price_range_inr": (60, 8000),
        "shelf_days": (180, 1095),
        "farm_types": ["Spice Plantation","Chilli Farm","Pepper Estate (Kerala)","Cardamom Estate","Turmeric Farm","Dry Fruit Farm","Cashew Orchard","Mixed Spice Farm"],
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────
def vectorised_dates(start_year, end_year, n):
    """Return n random datetime objects between start and end year."""
    start = datetime(start_year, 1, 1)
    end   = datetime(end_year, 11, 1)
    secs  = int((end - start).total_seconds())
    offsets = rng.integers(0, secs, n)
    return [start + timedelta(seconds=int(o)) for o in offsets]

def fmt(dt): return dt.strftime("%Y-%m-%d") if isinstance(dt, datetime) else str(dt)

def rand_phone_vec(n):
    prefixes = rng.choice(["6","7","8","9"], n)
    suffixes = rng.integers(100000000, 999999999, n)
    return [f"+91-{p}{s}" for p, s in zip(prefixes, suffixes)]

def rand_pin_state(state):
    info = INDIA.get(state, list(INDIA.values())[0])
    base = info["pin_base"]
    return str(base + rng.integers(0, 9999))

def rand_latlon(state):
    info = INDIA.get(state, list(INDIA.values())[0])
    lat = round(float(rng.uniform(info["lat"][0], info["lat"][1])), 5)
    lon = round(float(rng.uniform(info["lon"][0], info["lon"][1])), 5)
    return f"geo:{lat},{lon}"

def gst_num(state, uid):
    gst_code = INDIA.get(state, {}).get("gst", 27)
    h = hashlib.md5(uid.encode()).hexdigest()[:10].upper()
    return f"{gst_code:02d}A{h}Z"

def fssai_num():
    return f"10{rng.integers(10000000000000, 99999999999999)}"

def vehicle_num(state):
    code = INDIA.get(state, {}).get("code", "MH")
    n1 = rng.integers(10,99)
    l1 = chr(rng.integers(65,90))
    l2 = chr(rng.integers(65,90))
    n2 = rng.integers(1000,9999)
    return f"{code}-{n1}-{l1}{l2}-{n2}"

OWNER_NAMES = [
    "Ramesh Kumar","Suresh Patel","Mohan Singh","Ajay Verma","Ravi Sharma","Priya Devi",
    "Sunita Nair","Amit Joshi","Deepak Yadav","Pooja Gupta","Nilesh Shah","Pradeep Jain",
    "Kavita Desai","Arun Nair","Meena Pillai","Santosh Reddy","Harpreet Kaur","Vikas Chopra",
    "Sonal Mehta","Rohit Gupta","Laxmi Devi","Ganesh Iyer","Saroja Krishnan","Murali Babu",
    "Pushpa Pandey","Bhavna Patel","Girish Thakur","Rekha Mishra","Sunil Tiwari","Anita Rao",
    "Vinod Nambiar","Geeta Chaudhary","Prakash Hegde","Manjula Reddy","Arvind Kulkarni",
    "Renu Bhatt","Dinesh Pawar","Kamla Devi","Ashok Tripathi","Sudha Pillai",
]

PROC_PREFIXES = ["National","Bharat","Indo","Sai","Laxmi","Durga","Shakti","Modern","Prime","Pioneer",
                 "Agro","Golden","Green","Royal","Sunrise","Heritage","United","Eastern","Western","Central"]
PROC_SUFFIXES = ["Food Processing Pvt Ltd","Agro Industries Ltd","Food Products Ltd","Cold Storage & Processing",
                 "Grain Millers Ltd","Spice Mills","Dairy Processors","Food Park Unit","Agri Pvt Ltd",
                 "Foods & Beverages Ltd","Milling Corporation","Cooperative Society Ltd","Processors OPC"]

RETAIL_PREFIXES = ["Big","Super","Desi","Fresh","Daily","Smart","City","Lucky","Jai","Shri",
                   "Modern","Nature's","Pure","Green","Organic","Rural","Urban","New","Swadeshi","Apna"]
RETAIL_SUFFIXES = ["Mart","Bazaar","Kirana","Superstores","Grocery","Food World","General Stores",
                   "Supermarket","Traders","Merchants","Hypermarket","Agri Centre","APMC","Mandi","Depot"]

CARRIERS = ["Snowman Logistics","Rivigo Reefer","Safexpress Agri","DHL Supply Chain India",
            "CONCOR Cold Chain","Blue Dart Cargo","Mahindra Logistics","TCI-FRESH","VRL Logistics",
            "Gati KWE","DTDC Express","First Flight Couriers","Delhivery Cold","XpressBees",
            "Ecom Express","Spoton Logistics","Shadowfax","Porter Agri","Flipkart Commerce","Amazon Transport"]

TRANSPORT_MODES = ["Refrigerated Truck","Insulated Van","Railway Wagon","Cold Storage Container",
                   "Tempo (Small)","Tata Ace","Air Cargo","Two-Wheeler (Last Mile)","Container Truck","Mini Truck"]

CERT_STANDARDS = ["FSSAI Licensed","FSSAI Registered","ISO 22000:2018","HACCP","BRC Global Standard v8",
                  "IFS Food v7","SQF Level 2","FSSC 22000 v5","Organic Certification (NPOP)","GlobalGAP","Rainforest Alliance"]

STORE_TYPES = ["Kirana Store","Supermarket","Hypermarket","Mandi (Wholesale Market)","Online (D2C)",
               "Cooperative Society","Cold Store Retail","APMC Market","Modern Trade Outlet","Quick Commerce Hub",
               "Farmer Producer Organisation","Government Fair Price Shop","Hotel & Restaurant Supply","Institution Supply"]

SUPPLY_CHAIN_STAGES = ["Farm Gate","Primary Processing","Secondary Processing","Wholesale Mandi",
                        "Distribution Centre","Cold Storage Hub","Retail","Export Point","Institutional Buyer"]

ALERT_TYPES = ["Temperature Exceedance","Cold Chain Breach","Delay Alert","Quality Failure",
               "Contamination Detected","Quantity Mismatch","Document Irregularity","Expiry Violation",
               "Improper Storage","Pest Infestation Alert","Adulteration Suspected","Moisture Damage",
               "Vehicle Breakdown","Route Deviation","Weight Discrepancy"]

CONTAMINATION_TYPES = ["None","Salmonella","E. coli (STEC)","Listeria monocytogenes","Aspergillus (Aflatoxin B1)",
                        "Pesticide Residue (Organophosphate)","Heavy Metal (Lead)","Heavy Metal (Cadmium)",
                        "Foreign Object","Rodent Contamination","Fungal Mould","Food Adulteration",
                        "Microbial Overgrowth","Insect Infestation","Mycotoxin (Ochratoxin A)","Rancidity (Oxidation)"]

MANDIS = ["Azadpur Mandi (Delhi)","Vashi APMC (Mumbai)","Yeshwanthpur APMC (Bengaluru)",
          "Koyambedu Market (Chennai)","Gaddiannaram APMC (Hyderabad)","Gultekdi Market (Pune)",
          "Lasalgaon Onion Mandi (Nashik)","Unjha Mandi (Gujarat)","Khanna Grain Market (Punjab)",
          "Hapur Grain Market (UP)","Naya Bazaar (Delhi)","Bowbazar (Kolkata)",
          "Maheshwari Market (Bhopal)","Sulthan Bathery (Kerala)","Hubli APMC (Karnataka)"]

STATE_LIST = list(INDIA.keys())

def pick_state_city(n):
    """Pick n (state, city) pairs evenly spread across all states."""
    states, cities = [], []
    per_state = math.ceil(n / len(STATE_LIST))
    for s in STATE_LIST:
        city_pool = INDIA[s]["cities"]
        for _ in range(per_state):
            states.append(s)
            cities.append(random.choice(city_pool))
    # trim / shuffle
    combined = list(zip(states, cities))
    random.shuffle(combined)
    combined = combined[:n]
    return [x[0] for x in combined], [x[1] for x in combined]

# flat product list with category tag (20% each)
flat_products = []
for cat_name, cat_data in CATEGORIES.items():
    for p in cat_data["products"]:
        flat_products.append((cat_name, p, cat_data))

# ═══════════════════════════════════════════════════════════════════════════════
# BUILD TABLES
# ═══════════════════════════════════════════════════════════════════════════════

# ──────────────────────────── 1. FARM ────────────────────────────────────────
print(f"Building FARM ({N_FARMS:,} rows) …")
f_states, f_cities = pick_state_city(N_FARMS)
f_dates  = vectorised_dates(2000, 2023, N_FARMS)
f_phones = rand_phone_vec(N_FARMS)
# Assign categories evenly to farms (so each farm has a specialisation)
cat_names = list(CATEGORIES.keys())
n_per_cat = N_FARMS // len(cat_names)

farm_rows = []
for i in range(N_FARMS):
    state = f_states[i]; city = f_cities[i]
    cat   = cat_names[i // n_per_cat] if i // n_per_cat < len(cat_names) else random.choice(cat_names)
    cat_data = CATEGORIES[cat]
    fid   = f"FARM-{i+1:05d}"
    farm_rows.append({
        "Farm_ID":          fid,
        "Farm_Name":        f"{random.choice(['Shree','Jai','Om','Bharat','Kisaan','Swadeshi','Desi','Sarkar','Dhan','Anaj'])} {random.choice(['Agro Farm','Krishi Kendra','Agriculture Estate','Organic Farms','Kisaan Agri','Produce Pvt Ltd'])}",
        "Farm_Type":        random.choice(cat_data["farm_types"]),
        "Specialisation":   cat,
        "Owner_Name":       random.choice(OWNER_NAMES),
        "Street":           f"Survey No. {rng.integers(1,999)}, {random.choice(['Gram Panchayat','Village','Taluka'])} Road",
        "Village":          city + (" Taluka" if random.random()<0.4 else " Rural"),
        "City":             city,
        "District":         random.choice(INDIA[state]["districts"]),
        "State":            state,
        "PIN_Code":         rand_pin_state(state),
        "Contact_No":       f_phones[i],
        "Alt_Contact_No":   rand_phone_vec(1)[0] if random.random()<0.4 else "",
        "Location_GPS":     rand_latlon(state),
        "Land_Area_Acres":  round(float(rng.uniform(0.5, 800)), 2),
        "Irrigation_Type":  random.choice(["Canal","Borewell","Rainwater Harvesting","Drip Irrigation","Sprinkler","Tank Irrigation","Tube Well","River Lift"]),
        "FSSAI_License":    str(fssai_num()) if random.random()<0.55 else "",
        "GST_No":           gst_num(state, fid) if random.random()<0.45 else "",
        "Registered_Date":  fmt(f_dates[i]),
        "Country":          "India",
    })

df_farm = pd.DataFrame(farm_rows)
print(f"  → {len(df_farm):,} rows × {len(df_farm.columns)} cols")

farm_id_list = df_farm["Farm_ID"].tolist()

# ──────────────────────────── 2. PROCESSING_FACILITY ──────────────────────────
print(f"Building PROCESSING_FACILITY ({N_PROC:,} rows) …")
p_states, p_cities = pick_state_city(N_PROC)
proc_rows = []
for i in range(N_PROC):
    state = p_states[i]; city = p_cities[i]
    fid   = f"FAC-{i+1:04d}"
    proc_rows.append({
        "Facility_ID":       fid,
        "Facility_Name":     f"{random.choice(PROC_PREFIXES)} {random.choice(PROC_SUFFIXES)}",
        "Facility_Type":     random.choice(["Flour Mill","Rice Mill","Dal Mill","Oil Mill","Cold Storage (CA)","Spice Processing","Dairy Plant","Canning Unit","Packaging Unit","Multi-Product Plant","Pulses Processing","Grain Dryer","Sorting & Grading"]),
        "Owner_Name":        random.choice(OWNER_NAMES),
        "Street":            f"Plot No. {rng.integers(1,500)}, {random.choice(['Industrial Area','MIDC','GIDC','SIDCO','Food Park'])}",
        "City":              city,
        "District":          random.choice(INDIA[state]["districts"]),
        "State":             state,
        "PIN_Code":          rand_pin_state(state),
        "Contact_No":        rand_phone_vec(1)[0],
        "Location_GPS":      rand_latlon(state),
        "Capacity_MT_Day":   round(float(rng.uniform(2, 2000)), 1),
        "Cold_Storage_MT":   round(float(rng.uniform(0, 10000)), 1) if random.random()<0.55 else 0,
        "Cert_Standard":     random.choice(CERT_STANDARDS),
        "FSSAI_License":     str(fssai_num()),
        "GST_No":            gst_num(state, fid),
        "Year_Established":  int(rng.integers(1975, 2024)),
        "Num_Employees":     int(rng.integers(5, 5000)),
        "Country":           "India",
    })

df_proc = pd.DataFrame(proc_rows)
proc_id_list = df_proc["Facility_ID"].tolist()
print(f"  → {len(df_proc):,} rows × {len(df_proc.columns)} cols")

# ──────────────────────────── 3. RETAILER ────────────────────────────────────
print(f"Building RETAILER ({N_RETAIL:,} rows) …")
r_states, r_cities = pick_state_city(N_RETAIL)
ret_rows = []
for i in range(N_RETAIL):
    state = r_states[i]; city = r_cities[i]
    rid   = f"RET-{i+1:05d}"
    ret_rows.append({
        "Retailer_ID":    rid,
        "Retailer_Name":  f"{random.choice(RETAIL_PREFIXES)} {city} {random.choice(RETAIL_SUFFIXES)}",
        "Store_Type":     random.choice(STORE_TYPES),
        "Owner_Name":     random.choice(OWNER_NAMES),
        "Street":         f"Shop No. {rng.integers(1,200)}, {random.choice(['Main Road','Market Road','Station Road','Bazaar Lane','Gandhi Chowk'])}",
        "City":           city,
        "District":       random.choice(INDIA[state]["districts"]),
        "State":          state,
        "PIN_Code":       rand_pin_state(state),
        "Contact_No":     rand_phone_vec(1)[0],
        "Location_GPS":   rand_latlon(state),
        "FSSAI_License":  str(fssai_num()) if random.random()<0.78 else "",
        "GST_No":         gst_num(state, rid) if random.random()<0.65 else "",
        "Avg_Daily_Sales_INR": round(float(rng.uniform(500, 500000)), 2),
        "Country":        "India",
    })

df_ret = pd.DataFrame(ret_rows)
ret_id_list = df_ret["Retailer_ID"].tolist()
print(f"  → {len(df_ret):,} rows × {len(df_ret.columns)} cols")

# ──────────────────────────── 4. BATCH ───────────────────────────────────────
print(f"Building BATCH ({N_BATCHES:,} rows) …")
# 20% each category — cycle through categories
cat_items = []
for cat_name, cat_data in CATEGORIES.items():
    n_cat = N_BATCHES // len(CATEGORIES)
    prod_cycle = cat_data["products"] * (n_cat // len(cat_data["products"]) + 2)
    for j in range(n_cat):
        cat_items.append((cat_name, prod_cycle[j], cat_data))
# top up to N_BATCHES
while len(cat_items) < N_BATCHES:
    cat_name, cat_data = random.choice(list(CATEGORIES.items()))
    cat_items.append((cat_name, random.choice(cat_data["products"]), cat_data))
random.shuffle(cat_items)

prod_dates  = vectorised_dates(2021, 2026, N_BATCHES)
batch_rows  = []

for i, (cat_name, prod_name, cat_data) in enumerate(cat_items[:N_BATCHES]):
    prod_date  = prod_dates[i]
    shelf_days = rng.integers(cat_data["shelf_days"][0], cat_data["shelf_days"][1])
    exp_date   = prod_date + timedelta(days=int(shelf_days))
    now        = datetime(2026, 11, 23)
    shelf_rem  = max(0, (exp_date - now).days)
    qty        = round(float(rng.uniform(0.5, 1000)), 2)
    unit       = random.choice(cat_data["unit"])
    bid        = f"BATCH-{i+1:05d}"
    batch_rows.append({
        "Batch_ID":              bid,
        "Product_Name":          prod_name,
        "Category":              cat_name,
        "Production_Date":       fmt(prod_date),
        "Expiry_Date":           fmt(exp_date),
        "Shelf_Life_Days":       int(shelf_days),
        "Shelf_Life_Remaining":  int(shelf_rem),
        "Quantity":              qty,
        "Unit":                  unit,
        "Grade":                 random.choice(["A+ (Premium)","A (Good)","B (Standard)","C (Economy)","Export Quality","FAQ (Fair Average Quality)"]),
        "Lot_Number":            f"LOT{prod_date.year}-{i+1:05d}",
        "FSSAI_Approved":        random.choices([True,False],[85,15])[0],
        "Moisture_Pct":          round(float(rng.uniform(7, 22)), 2),
        "Foreign_Matter_Pct":    round(float(rng.uniform(0, 2)), 3),
        "Origin_Farm_ID":        random.choice(farm_id_list),
        "Processed_By_Fac_ID":   random.choice(proc_id_list),
        "Season":                random.choice(["Kharif","Rabi","Zaid","Year-Round","Pre-Kharif"]),
        "Input_Batch_ID":        f"BATCH-{rng.integers(1,i+1):05d}" if i>10 and random.random()<0.25 else "",
        "Output_Batch_ID":       "",
    })

df_batch = pd.DataFrame(batch_rows)
batch_id_list = df_batch["Batch_ID"].tolist()
print(f"  → {len(df_batch):,} rows × {len(df_batch.columns)} cols")
print(f"  Category breakdown: {df_batch['Category'].value_counts().to_dict()}")

# ──────────────────────────── 5. QUALITY_CHECK ───────────────────────────────
print(f"Building QUALITY_CHECK ({N_QC:,} rows) …")
qc_dates = vectorised_dates(2021, 2026, N_QC)
qc_rows  = []

# assign QC rows to batches (some batches get 1, some 2, some 3)
batch_qc_assign = []
for bid in batch_id_list:
    n = random.choices([1,2,3], weights=[55,35,10])[0]
    batch_qc_assign.extend([bid]*n)
batch_qc_assign = batch_qc_assign[:N_QC]
while len(batch_qc_assign) < N_QC:
    batch_qc_assign.append(random.choice(batch_id_list))
random.shuffle(batch_qc_assign)

for i, bid in enumerate(batch_qc_assign):
    status    = random.choices(["Pass","Fail","Conditional Pass","Pending Review"],[60,15,17,8])[0]
    cont_type = "None" if status in ("Pass","Pending Review") else random.choice(CONTAMINATION_TYPES[1:])
    chk_dt    = qc_dates[i]
    qc_rows.append({
        "Check_ID":           f"QC-{i+1:06d}",
        "Batch_ID":           bid,
        "Check_Date":         fmt(chk_dt),
        "Inspector_ID":       f"INS-{rng.integers(1,250):03d}",
        "Facility_ID":        random.choice(proc_id_list),
        "Status":             status,
        "Contamination_Type": cont_type,
        "Temperature_C":      round(float(rng.uniform(-5, 40)), 1),
        "Humidity_Pct":       round(float(rng.uniform(20, 98)), 1),
        "pH_Level":           round(float(rng.uniform(3.0, 9.0)), 2),
        "Moisture_Pct":       round(float(rng.uniform(6, 24)), 2),
        "Lab_Test_Code":      f"NABL-{rng.integers(100000,999999)}",
        "Remarks":            (
            "Batch approved. All parameters within FSSAI limits." if status=="Pass"
            else f"REJECTED: {cont_type} detected above permissible limit. Batch quarantined pending disposal." if status=="Fail"
            else f"Conditionally approved. Trace of {cont_type} found within tolerable limit. Re-test in 48 hrs." if status=="Conditional Pass"
            else "Lab test dispatched to NABL-accredited lab. Result awaited within 72 hours."
        ),
    })

df_qc = pd.DataFrame(qc_rows)
print(f"  → {len(df_qc):,} rows × {len(df_qc.columns)} cols")

# ──────────────────────────── 6. SHIPMENT ────────────────────────────────────
print(f"Building SHIPMENT ({N_SHIP:,} rows) …")
s_dates  = vectorised_dates(2021, 2026, N_SHIP)
ship_rows = []

for i in range(N_SHIP):
    src_state = random.choice(STATE_LIST)
    dst_state = random.choice(STATE_LIST)
    src_city  = random.choice(INDIA[src_state]["cities"])
    dst_city  = random.choice(INDIA[dst_state]["cities"])
    ship_dt   = s_dates[i]
    exp_days  = rng.integers(1, 15)
    act_days  = int(exp_days) + rng.integers(-1, 5) if random.random()<0.82 else None
    n_batches = random.choices([1,2,3,4],[50,30,15,5])[0]
    picked_b  = random.sample(batch_id_list, min(n_batches, len(batch_id_list)))
    qty       = round(float(rng.uniform(10, 10000)), 2)
    sid       = f"SHIP-{i+1:05d}"
    dist_km   = float(rng.uniform(50, 3000))
    ship_rows.append({
        "Shipment_ID":               sid,
        "Shipment_Date":             fmt(ship_dt),
        "Expected_Delivery_Date":    fmt(ship_dt + timedelta(days=int(exp_days))),
        "Actual_Delivery_Date":      fmt(ship_dt + timedelta(days=int(act_days))) if act_days is not None else "Pending",
        "Source_City":               src_city,
        "Source_District":           random.choice(INDIA[src_state]["districts"]),
        "Source_State":              src_state,
        "Source_PIN":                rand_pin_state(src_state),
        "Destination_City":          dst_city,
        "Destination_District":      random.choice(INDIA[dst_state]["districts"]),
        "Destination_State":         dst_state,
        "Destination_PIN":           rand_pin_state(dst_state),
        "Distance_KM":               round(dist_km, 1),
        "Quantity_Shipped":          qty,
        "Unit":                      random.choice(["KG","MT","Quintal","Bags (50kg)","Crates","Boxes"]),
        "Transportation_Cost_INR":   round(dist_km * float(rng.uniform(10, 60)) / 100 * qty * 0.01, 2),
        "Transport_Mode":            random.choice(TRANSPORT_MODES),
        "Carrier_Name":              random.choice(CARRIERS),
        "Vehicle_No":                vehicle_num(src_state),
        "Batch_IDs":                 "; ".join(picked_b),
        "Retailer_ID":               random.choice(ret_id_list),
        "Supply_Chain_Stage":        random.choice(SUPPLY_CHAIN_STAGES),
        "Cold_Chain_Maintained":     random.choices([True,False],[75,25])[0],
        "Temp_During_Transit_C":     round(float(rng.uniform(-5, 30)), 1),
        "Status":                    random.choices(["Delivered","In Transit","Delayed","Partial Delivery","Returned","Lost in Transit"],[58,18,12,7,4,1])[0],
        "Track_Shipment_Qty":        qty,
    })

df_ship = pd.DataFrame(ship_rows)
ship_id_list = df_ship["Shipment_ID"].tolist()
print(f"  → {len(df_ship):,} rows × {len(df_ship.columns)} cols")

# ──────────────────────────── 7. ANOMALY_ALERT ───────────────────────────────
print(f"Building ANOMALY_ALERT ({N_ALERT:,} rows) …")
failed_qc_rows = df_qc[df_qc["Status"].isin(["Fail","Conditional Pass"])].to_dict("records")
alert_rows     = []
a_dates        = vectorised_dates(2021, 2026, N_ALERT)

n_qc_alerts   = int(N_ALERT * 0.6)
n_ship_alerts = N_ALERT - n_qc_alerts

qc_sample = random.sample(failed_qc_rows, min(n_qc_alerts, len(failed_qc_rows)))
for idx, qrow in enumerate(qc_sample):
    score = round(float(rng.uniform(0.55,1.0)),3) if qrow["Status"]=="Fail" else round(float(rng.uniform(0.25,0.65)),3)
    alert_rows.append({
        "Alert_ID":               f"ALT-{idx+1:06d}",
        "Alert_Date":             fmt(datetime.strptime(qrow["Check_Date"],"%Y-%m-%d") + timedelta(days=int(rng.integers(0,4)))),
        "Alert_Type":             "Quality Failure" if qrow["Status"]=="Fail" else "Contamination Detected",
        "Anomaly_Score":          score,
        "Severity":               "Critical" if score>0.85 else "High" if score>0.7 else "Medium" if score>0.5 else "Low",
        "Description":            f"QC {qrow['Check_ID']}: Batch {qrow['Batch_ID']} — {qrow['Remarks'][:120]}",
        "Batch_ID":               qrow["Batch_ID"],
        "Check_ID":               qrow["Check_ID"],
        "Triggered_Shipment_ID":  random.choice(ship_id_list),
        "Assigned_To":            f"INS-{rng.integers(1,250):03d}",
        "Resolved":               random.choices([True,False],[60,40])[0],
        "Resolution_Date":        fmt(datetime.strptime(qrow["Check_Date"],"%Y-%m-%d") + timedelta(days=int(rng.integers(1,45)))) if random.random()<0.6 else "",
        "Action_Taken":           random.choice(["Batch recalled","Quarantine extended","Re-test ordered","Supplier warned","Batch destroyed","Re-process approved","Investigation opened","FSSAI notified","Penalty imposed","Recall from retail shelves"]),
    })

for jdx in range(n_ship_alerts):
    srow  = random.choice(ship_rows)
    score = round(float(rng.uniform(0.1,0.98)),3)
    atype = random.choice(ALERT_TYPES)
    adx   = len(qc_sample) + jdx
    alert_rows.append({
        "Alert_ID":               f"ALT-{adx+1:06d}",
        "Alert_Date":             fmt(a_dates[jdx]),
        "Alert_Type":             atype,
        "Anomaly_Score":          score,
        "Severity":               "Critical" if score>0.85 else "High" if score>0.7 else "Medium" if score>0.5 else "Low",
        "Description":            f"Shipment {srow['Shipment_ID']} ({srow['Source_City']} → {srow['Destination_City']}): {atype} reported by {srow['Carrier_Name']}.",
        "Batch_ID":               "",
        "Check_ID":               "",
        "Triggered_Shipment_ID":  srow["Shipment_ID"],
        "Assigned_To":            f"INS-{rng.integers(1,250):03d}",
        "Resolved":               random.choices([True,False],[55,45])[0],
        "Resolution_Date":        fmt(a_dates[jdx] + timedelta(days=int(rng.integers(1,25)))) if random.random()<0.55 else "",
        "Action_Taken":           random.choice(["Shipment held at checkpoint","Driver re-routed","Cold chain restored","Cargo inspected by FSSAI","Penalty issued to carrier","Insurance claim filed","Cargo redirected to nearest cold store"]),
    })

df_alert = pd.DataFrame(alert_rows)
print(f"  → {len(df_alert):,} rows × {len(df_alert.columns)} cols")

# ──────────────────────────── 8. PRICE_RECORD ────────────────────────────────
print(f"Building PRICE_RECORD ({N_PRICE:,} rows) …")
# use same length as BATCH (1:1)
pr_dates  = vectorised_dates(2021, 2026, N_PRICE)
price_rows = []

batch_sample = df_batch.to_dict("records")
random.shuffle(batch_sample)
batch_sample = batch_sample[:N_PRICE]

for i, brow in enumerate(batch_sample):
    cat_data   = CATEGORIES.get(brow["Category"], list(CATEGORIES.values())[0])
    rng_p      = cat_data["price_range_inr"]
    farm_price = round(float(rng.uniform(rng_p[0], rng_p[0]+(rng_p[1]-rng_p[0])*0.45)), 2)
    sell_price = round(farm_price * float(rng.uniform(1.1, 3.0)), 2)
    msp        = round(farm_price * float(rng.uniform(0.80, 1.05)), 2)
    state      = random.choice(STATE_LIST)
    city       = random.choice(INDIA[state]["cities"])
    price_rows.append({
        "Price_ID":              f"PRC-{i+1:06d}",
        "Batch_ID":              brow["Batch_ID"],
        "Product_Name":          brow["Product_Name"],
        "Category":              brow["Category"],
        "Price_Date":            fmt(pr_dates[i]),
        "Supply_Chain_Stage":    random.choice(SUPPLY_CHAIN_STAGES),
        "Market_Location":       f"{city}, {state}",
        "Mandi_Name":            random.choice(MANDIS),
        "Cost_Per_Unit_INR":     farm_price,
        "MSP_Per_Unit_INR":      msp,
        "Selling_Price_INR":     sell_price,
        "Price_Change_Pct":      round((sell_price-farm_price)/farm_price*100, 2),
        "Wholesale_Price_INR":   round(farm_price * float(rng.uniform(1.05, 1.5)), 2),
        "Currency":              "INR",
        "Unit":                  brow["Unit"],
        "Season":                brow["Season"],
    })

df_price = pd.DataFrame(price_rows)
print(f"  → {len(df_price):,} rows × {len(df_price.columns)} cols")

# ──────────────────────────── 9. BATCH_SHIPMENT bridge ───────────────────────
print("Building BATCH_SHIPMENT bridge …")
bs_rows = []
for srow in ship_rows:
    for bid in str(srow["Batch_IDs"]).split(";"):
        bid = bid.strip()
        if bid:
            bs_rows.append({"Batch_ID": bid, "Shipment_ID": srow["Shipment_ID"]})
df_bs = pd.DataFrame(bs_rows).drop_duplicates()
print(f"  → {len(df_bs):,} rows")

# ═══════════════════════════════════════════════════════════════════════════════
# WRITE EXCEL
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

total = sum(len(d) for _,d in SHEET_ORDER)
print(f"\nTotal rows: {total:,}")
print(f"Writing → {OUT} …")

with pd.ExcelWriter(OUT, engine="openpyxl") as writer:
    for sheet_name, df in SHEET_ORDER:
        df.to_excel(writer, sheet_name=sheet_name, index=False)
        ws = writer.sheets[sheet_name]
        for col_cells in ws.columns:
            mx = max((len(str(c.value)) for c in col_cells if c.value is not None), default=8)
            ws.column_dimensions[col_cells[0].column_letter].width = min(mx + 2, 55)

print("\n✓ All done!")
print(f"\n{'Sheet':<25} {'Rows':>9}  {'Cols':>5}")
print("─" * 44)
for name, df in SHEET_ORDER:
    print(f"  {name:<23} {len(df):>9,}  {len(df.columns):>5}")
print("─" * 44)
print(f"  {'TOTAL':<23} {total:>9,}")
print(f"\nSaved: {OUT}")
