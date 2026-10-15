SERVICE_URL = "https://gis.co.isanti.mn.us/arcgis/rest/services/LandRecords/TaxParcels_Public/FeatureServer"
LAYER_ID = 0
DATASET = "TaxParcels_Public"

SOURCE_FIELDS = {
    "object_id": "OBJECTID",
    "parcel_id": "PARCELID",
    "owner_name": "OWNERNME1",
    "deeded_acres": "DEEDEDACRES",
    "previous_taxes_owed": "TOTPRVTXTOD",
    "current_tax_amount": "TOTCNTTXOD",
    "land_value": "LNDVALUE",
    "improvement_value": "IMPRVALUE",
    "assessed_value": "CNTASSDVAL",
    "property_classification": "PRIMARYCLASS",
    "legal_description": "LEGALDESCRIPT",
    "source_reference": "PARCEL_REPORT",
}

MAILING_FIELDS = (
    "PSTLADDRESS",
    "PSTLADDRESS2",
    "PSTLCITY",
    "PSTLSTATE",
    "PSTLZIP5",
    "PSTLZIP4",
)

QUERY_FIELDS = tuple(dict.fromkeys((*SOURCE_FIELDS.values(), *MAILING_FIELDS)))

# The official alias says only "Total Previous Taxes Owed". It does not define
# this as delinquent/past-due, so strict candidate classification stays disabled.
PAST_DUE_TAX_SEMANTICS_VERIFIED = False
