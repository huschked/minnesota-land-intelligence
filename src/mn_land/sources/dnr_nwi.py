"""DNR NWI and independent project footprints; no federal/county substitution."""

import re

from mn_land.ingestion.spatial_layers import PolygonLayer

SERVICE = "https://enterprise.gisdata.mn.gov/aghost/rest/services/us_mn_state_dnr/water_nat_wetlands_inv_2009_2014/FeatureServer"
NWI = PolygonLayer(SERVICE + "/0", 0, "Statewide NWI", (
    ("objectid", "esriFieldTypeOID"), ("attribute", "esriFieldTypeString"),
    ("wetland_type", "esriFieldTypeString"), ("acres", "esriFieldTypeDouble"),
    ("hgm_code", "esriFieldTypeString"), ("hgm_desc", "esriFieldTypeString"),
    ("spcc_desc", "esriFieldTypeString"), ("cow_class1", "esriFieldTypeString"),
    ("circ39_class", "esriFieldTypeSmallInteger"), ("hgm_symbol", "esriFieldTypeString"),
), 26915)
PROJECTS = PolygonLayer(SERVICE + "/1", 1, "Project Boundary", (
    ("objectid", "esriFieldTypeOID"), ("project_area", "esriFieldTypeString"),
    ("project_area_name", "esriFieldTypeString"), ("project_partner", "esriFieldTypeString"),
    ("delivery_date", "esriFieldTypeDate"), ("spring_imagery_year", "esriFieldTypeString"),
), 26915)

LEGACY_INCLUSION_POLICY = {
    "version": "dnr-nwi-cowardin-screen-v1",
    "wetland_numerator": ["vegetated_or_other_wetland", "open_water_wetland"],
    "separate_not_in_wetland_numerator": ["deepwater", "riverine_mixed"],
    "unknown": "null overall metrics when positive-area unknown/conflicting classification",
    "interpretation": "mapped classes only; not total jurisdictional wetlands or dry/buildable land",
}
INCLUSION_POLICY = {**LEGACY_INCLUSION_POLICY, "version": "dnr-nwi-cowardin-screen-v2"}
INCLUSION_POLICIES = {p["version"]: p for p in (LEGACY_INCLUSION_POLICY, INCLUSION_POLICY)}


def category(attributes: dict, policy: dict = INCLUSION_POLICY) -> str:
    if INCLUSION_POLICIES.get(policy.get("version")) != policy:
        raise ValueError("Unrecognized wetland inclusion policy")
    label, code = attributes.get("wetland_type"), attributes.get("attribute")
    if not isinstance(code, str) or not isinstance(label, str):
        return "unknown"
    # Deliberately bounded recognized syntax; unsupported/old/future codes remain
    # unknown rather than guessing from a label or a partial string prefix.
    if not re.fullmatch(
        r"(?:P|L[12]|R[1-5])(?:FO|SS|EM|UB|AB|US|RS|ML|RB|SB)[1-9]?"
        r"(?:/(?:FO|SS|EM|UB|AB|US|RS|ML|RB|SB)[1-9]?)*[A-Z][a-z]{0,3}", code,
    ):
        return "unknown"
    if label == "Freshwater Forested/Shrub Wetland" and code.startswith(("PFO", "PSS")):
        return "vegetated_or_other_wetland"
    if label == "Freshwater Emergent Wetland" and code.startswith("PEM"):
        return "vegetated_or_other_wetland"
    if policy == INCLUSION_POLICY:
        # DNR's observed detailed labels, independently paired with full native
        # Cowardin codes. Keep v1 replayable rather than rewriting old results.
        if label == "Freshwater Forested Wetland" and code.startswith("PFO"):
            return "vegetated_or_other_wetland"
        if label == "Freshwater Shrub Wetland" and code.startswith("PSS"):
            return "vegetated_or_other_wetland"
        if label == "Freshwater Shrub/Emergent Wetland" and re.fullmatch(
            r"PSS[1-9]?/EM[1-9]?[A-Z][a-z]{0,3}", code,
        ):
            return "vegetated_or_other_wetland"
    if label == "Freshwater Pond" and code.startswith(("PUB", "PAB")):
        return "open_water_wetland"
    if label == "Lake":
        if code.startswith("L1"):
            return "deepwater"
        if code.startswith(("L2UB", "L2AB")):
            return "open_water_wetland"
        if code.startswith(("L2EM", "L2US", "L2RS")):
            return "vegetated_or_other_wetland"
    if label == "Riverine" and code.startswith(("R1", "R2", "R3", "R4", "R5")):
        return "riverine_mixed"
    return "unknown"
