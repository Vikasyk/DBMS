import re


EXAMPLES = [
    "Where did batch B103 originate?",
    "Which batches were derived from B101?",
    "What went into B105?",
    "Which retailers received products derived from B101?",
    "Show all batches that failed quality checks.",
    "Which batches have unusual quantity discrepancies?",
    "How did tomato prices change over the last six months?",
    "Show the price history of batch B103.",
    "Which shipments carried B103?",
    "Which batches expire within 7 days?",
    "What would happen if batch B101 were contaminated?",
]

BATCH = re.compile(r"\bB[0-9]{1,11}\b", re.IGNORECASE)
PRODUCT_NAMES = {
    "Tomato Onion Masala": r"tomato onion masala",
    "Tomato Puree": r"tomato puree",
    "Potato Chips": r"potato chips",
    "Mango Pulp": r"mango pulp",
    "Tomato": r"tomato(?:es)?",
    "Onion": r"onions?",
    "Potato": r"potato(?:es)?",
    "Mango": r"mango(?:es|s)?",
}
MONTHS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
          "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12}


def route(question: str):
    words = " ".join(question.lower().split())
    ids = {batch_id.upper() for batch_id in BATCH.findall(question)}
    if len(ids) > 1:
        return "unsupported", {}
    if ids:
        parameters = {"batch_id": next(iter(ids))}
        if "contaminat" in words and any(phrase in words for phrase in
                                          ("what if", "what would happen", "simulate", "suppose")):
            return "simulate", parameters
        if "retailer" in words:
            return "retailers_of_derived", parameters
        if any(phrase in words for phrase in ("origin", "come from", "source")):
            return "origin", parameters
        if any(phrase in words for phrase in ("went into", "inputs of", "upstream", "made of")):
            return "upstream", parameters
        if any(phrase in words for phrase in ("derived from", "made from", "downstream")):
            return "downstream", parameters
        if "shipment" in words:
            return "shipments_of_batch", parameters
        if "price" in words:
            return "batch_prices", parameters
    if "fail" in words and ("quality" in words or "check" in words):
        return "failed_checks", {}
    if "discrepanc" in words or ("unusual" in words and "quantit" in words):
        return "quantity_anomalies", {}
    if "price" in words and any(phrase in words for phrase in ("trend", "change", "last", "over")):
        for product, pattern in PRODUCT_NAMES.items():
            if re.search(rf"\b{pattern}\b", words):
                period = re.search(r"\b(?:last|past) ([0-9]{1,3}|[a-z]+) months?\b", words)
                months = None
                if period:
                    token = period.group(1)
                    months = int(token) if token.isdecimal() else MONTHS.get(token)
                    if not months:
                        return "unsupported", {}
                return "product_trend", {"product": product, "months": months}
    if "expir" in words:
        days = re.search(r"\b([0-9]{1,4}) days?\b", words)
        return "expiring", {"days": int(days.group(1)) if days else 7}
    return "unsupported", {}
