# *******************************************************************************
# IBM Confidential                                                            *
#                                                                             *
# OCO Source Materials                                                        *
#                                                                             *
# (C) Copyright IBM Corp. 2021                                                *
#                                                                             *
# The source code for this program is not published or otherwise              *
# divested of its trade secrets, irrespective of what has been                *
# deposited with the U.S. Copyright Office.                                   *
# ******************************************************************************/

# Extension URL used in standard FHIR resource extension (extension directly under the resource type)
INSIGHT_REFERENCE_URL = "http://ibm.com/fhir/cdm/insight/reference"               # general extension for a resource
INSIGHT_CATEGORY_URL = "http://ibm.com/fhir/cdm/StructureDefinition/category"     # indicates how derivation was done, eg from NLP

# Extension URLs used in meta extensions (extensions in the meta section of a FHIR resource)
# also see INSIGHT_CATEGORY_URL
INSIGHT_URL = "http://ibm.com/fhir/cdm/StructureDefinition/insight"                # insight top level for confidences and spans (unstructured only)
INSIGHT_BASED_ON_URL = "http://ibm.com/fhir/cdm/StructureDefinition/reference"     # link to the unstructured report (FHIR DiagnosticReport)
INSIGHT_DETAIL_URL = "http://ibm.com/fhir/cdm/StructureDefinition/insight-detail"  # a derived insight (general, complex extension)
INSIGHT_ID_URL = "http://ibm.com/fhir/cdm/StructureDefinition/insight-id"  # ID of the insight entry
INSIGHT_ACD_OUTPUT_URL = "http://ibm.com/fhir/cdm/StructureDefinition/evaluated-output"     # full ACD output
INSIGHT_REFERENCE_PATH_URL = "http://ibm.com/fhir/cdm/StructureDefinition/reference-path"   # path in resource insight was used for

INSIGHT_RESULT_URL = "http://ibm.com/fhir/cdm/StructureDefinition/insight-result"  # insight result
INSIGHT_SPAN_URL = "http://ibm.com/fhir/cdm/StructureDefinition/span"              # span information (general, complex extension)
INSIGHT_SPAN_OFFSET_BEGIN_URL = "http://ibm.com/fhir/cdm/StructureDefinition/offset-begin"  # beginning offset of NLP annotation
INSIGHT_SPAN_OFFSET_END_URL = "http://ibm.com/fhir/cdm/StructureDefinition/offset-end"      # ending offset of NLP annotation
INSIGHT_SPAN_COVERED_TEXT_URL = "http://ibm.com/fhir/cdm/StructureDefinition/covered-text"  # text covered by the NLP annotation
INSIGHT_CONFIDENCE_URL = "http://ibm.com/fhir/cdm/StructureDefinition/insight-confidence"   # confidence (general, complex extension)
INSIGHT_CONFIDENCE_SCORE_URL = "http://ibm.com/fhir/cdm/StructureDefinition/score"  # confidence score for the insight
INSIGHT_CONFIDENCE_NAME_URL = "http://ibm.com/fhir/cdm/StructureDefinition/description"     # name of the specific confidence score

# non-insight URLS
SNOMED_URL = "http://snomed.info/sct"
UMLS_URL = "http://terminology.hl7.org/CodeSystem/umls"
LOINC_URL = "http://loinc.org"
MESH_URL = "http://www.nlm.nih.gov/mesh/meshhome.html"
NCI_URL = "http://ncithesaurus.nci.nih.gov/ncitbrowser/"
ICD9_URL = "http://terminology.hl7.org/CodeSystem/icd9"
ICD10_URL = "https://terminology.hl7.org/CodeSystem/icd10"
RXNORM_URL = "http://www.nlm.nih.gov/research/umls/rxnorm"
TIMING_URL = "http://hl7.org/fhir/ValueSet/timing-abbreviation"

# category coding system values
CLASSIFICATION_DERIVED_CODE = "natural-language-processing"
CLASSIFICATION_DERIVED_DISPLAY = "NLP"
CLASSIFICATION_DERIVED_SYSTEM = "http://ibm.com/fhir/cdm/CodeSystem/insight-category-code-system"

INSIGHT_ID_SYSTEM_URN = "urn:id:COM.IBM.WH.PA.CDP.CDE/1.0.0"

CONFIDENCE_SCORE_EXPLICIT = "Explicit Score"
CONFIDENCE_SCORE_PATIENT_REPORTED = "Patient Reported Score"
CONFIDENCE_SCORE_DISCUSSED = "Discussed Score"
CONFIDENCE_SCORE_SUSPECTED = "Suspected Score"
CONFIDENCE_SCORE_FAMILY_HISTORY = "Family History Score"

CONFIDENCE_SCORE_MEDICATION_TAKEN = "Medication Taken Score"
CONFIDENCE_SCORE_MEDICATION_CONSIDERING = "Medication Considering Score"
CONFIDENCE_SCORE_MEDICATION_DISCUSSED = "Medication Discussed Score"
CONFIDENCE_SCORE_MEDICATION_MEASUREMENT = "Medication Lab Measurement Score"
