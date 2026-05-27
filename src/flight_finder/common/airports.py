"""Airport region lookup used for route-coverage filtering.

EU region covers Europe, Turkey, and Cyprus.
MEA covers Middle East and North Africa (where Wizz Air also operates).
"""

from __future__ import annotations

# Maps IATA code → broad region string
_AIRPORT_REGIONS: dict[str, str] = {
    # North America
    "JFK": "NA", "LAX": "NA", "SFO": "NA", "ORD": "NA", "MIA": "NA",
    "BOS": "NA", "SEA": "NA", "DFW": "NA", "ATL": "NA", "DEN": "NA",
    "LAS": "NA", "PHX": "NA", "IAH": "NA", "EWR": "NA", "DTW": "NA",
    "YYZ": "NA", "YVR": "NA", "YUL": "NA", "YYC": "NA",
    "MEX": "NA", "CUN": "NA", "GDL": "NA",
    # Europe (EU + Turkey + Cyprus)
    "LHR": "EU", "LGW": "EU", "LTN": "EU", "STN": "EU", "MAN": "EU",
    "BHX": "EU", "EDI": "EU", "BRS": "EU", "GLA": "EU", "NCL": "EU",
    "CDG": "EU", "ORY": "EU", "NCE": "EU", "LYS": "EU", "MRS": "EU",
    "BOD": "EU", "TLS": "EU", "NTE": "EU", "LIL": "EU",
    "FRA": "EU", "MUC": "EU", "BER": "EU", "DUS": "EU", "HAM": "EU",
    "STR": "EU", "CGN": "EU", "NUE": "EU", "HAJ": "EU",
    "AMS": "EU", "EIN": "EU", "RTM": "EU",
    "BRU": "EU", "CRL": "EU", "LGG": "EU",
    "VIE": "EU", "GRZ": "EU", "SZG": "EU", "INN": "EU", "LNZ": "EU",
    "ZRH": "EU", "GVA": "EU", "BSL": "EU",
    "LIS": "EU", "OPO": "EU", "FAO": "EU",
    "MAD": "EU", "BCN": "EU", "AGP": "EU", "PMI": "EU", "ALC": "EU",
    "VLC": "EU", "SVQ": "EU", "ACE": "EU", "TFS": "EU", "LPA": "EU",
    "FCO": "EU", "MXP": "EU", "BGY": "EU", "TSF": "EU", "VCE": "EU",
    "PSA": "EU", "NAP": "EU", "PMO": "EU", "CTA": "EU", "BRI": "EU",
    "ATH": "EU", "SKG": "EU", "HER": "EU", "CFU": "EU", "RHO": "EU",
    "KOS": "EU", "MYK": "EU", "JSI": "EU", "CHQ": "EU", "ZTH": "EU",
    "PRG": "EU", "OSR": "EU", "BRQ": "EU",
    "BUD": "EU",
    "WAW": "EU", "KRK": "EU", "WRO": "EU", "POZ": "EU", "KTW": "EU",
    "GDN": "EU", "LUZ": "EU", "RZE": "EU",
    "OTP": "EU", "CLJ": "EU", "TSR": "EU", "SBZ": "EU", "IAS": "EU",
    "SOF": "EU", "VAR": "EU", "BOJ": "EU", "PDV": "EU",
    "BEG": "EU",
    "VNO": "EU", "KUN": "EU",
    "RIX": "EU",
    "TLL": "EU",
    "HEL": "EU", "TMP": "EU",
    "ARN": "EU", "GOT": "EU", "MMX": "EU",
    "OSL": "EU", "BGO": "EU",
    "CPH": "EU",
    "DUB": "EU", "ORK": "EU", "SNN": "EU",
    "LJU": "EU", "MBX": "EU",
    "ZAG": "EU", "SPU": "EU", "DBV": "EU",
    "SKP": "EU", "TGD": "EU", "PRN": "EU",
    "TIA": "EU", "OHD": "EU",
    "BTS": "EU",
    "KBP": "EU", "LWO": "EU", "IEV": "EU", "HRK": "EU",
    "MSQ": "EU",
    "TBS": "EU", "KUT": "EU",
    "EVN": "EU",
    "LCA": "EU", "PFO": "EU",
    "IST": "EU", "SAW": "EU", "ADB": "EU", "AYT": "EU", "BJV": "EU",
    "ANK": "EU", "ESB": "EU",
    # Asia-Pacific
    "NRT": "APAC", "HND": "APAC", "KIX": "APAC", "CTS": "APAC",
    "HKG": "APAC", "SIN": "APAC", "KUL": "APAC", "BKK": "APAC",
    "DMK": "APAC", "CGK": "APAC", "MNL": "APAC",
    "SYD": "APAC", "MEL": "APAC", "BNE": "APAC", "PER": "APAC",
    "AKL": "APAC",
    "PEK": "APAC", "PKX": "APAC", "PVG": "APAC", "SHA": "APAC",
    "CAN": "APAC", "CTU": "APAC", "SZX": "APAC",
    "ICN": "APAC", "GMP": "APAC",
    "DEL": "APAC", "BOM": "APAC", "MAA": "APAC", "BLR": "APAC",
    "HYD": "APAC",
    # Latin America
    "GRU": "LATAM", "GIG": "LATAM", "BSB": "LATAM", "SSA": "LATAM",
    "EZE": "LATAM", "AEP": "LATAM",
    "BOG": "LATAM", "MDE": "LATAM",
    "LIM": "LATAM",
    "SCL": "LATAM",
    "UIO": "LATAM", "GYE": "LATAM",
    "PTY": "LATAM",
    "HAV": "LATAM",
    # Middle East & North Africa
    "DXB": "MEA", "AUH": "MEA", "SHJ": "MEA",
    "DOH": "MEA",
    "RUH": "MEA", "JED": "MEA", "DMM": "MEA",
    "KWI": "MEA",
    "BAH": "MEA",
    "MCT": "MEA",
    "TLV": "MEA", "ETH": "MEA",
    "AMM": "MEA",
    "BEY": "MEA",
    "CAI": "MEA", "HRG": "MEA", "SSH": "MEA", "LXR": "MEA",
    "CMN": "MEA", "RAK": "MEA", "AGA": "MEA", "NDR": "MEA",
    "TUN": "MEA", "SFA": "MEA",
    "ALG": "MEA",
    # Sub-Saharan Africa
    "JNB": "AF", "CPT": "AF", "DUR": "AF",
    "NBO": "AF", "MBA": "AF",
    "LOS": "AF", "ABV": "AF", "KAN": "AF",
    "ADD": "AF",
    "ACC": "AF",
    "DAR": "AF",
    "CMB": "AF",
}


def route_region(origin: str, destination: str) -> frozenset[str]:
    """Return the set of regions touched by origin and destination."""
    regions: set[str] = set()
    for code in (origin, destination):
        r = _AIRPORT_REGIONS.get(code)
        if r:
            regions.add(r)
    return frozenset(regions)


def adapter_covers_route(
    supported_regions: list[str],
    origin: str,
    destination: str,
) -> bool:
    """Return True if the adapter supports both endpoints of the route.

    An empty supported_regions list means the adapter is global (covers all routes).
    Otherwise, both origin and destination must map to a supported region.
    Unknown IATA codes fail the check conservatively.
    """
    if not supported_regions:
        return True
    regions_set = set(supported_regions)
    o = _AIRPORT_REGIONS.get(origin)
    d = _AIRPORT_REGIONS.get(destination)
    return (o in regions_set) and (d in regions_set)
