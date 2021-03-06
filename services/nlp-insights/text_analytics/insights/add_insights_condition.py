from fhir.resources.codeableconcept import CodeableConcept
from fhir.resources.condition import Condition
from fhir.resources.extension import Extension

from text_analytics.insights import insight_constants
from text_analytics.utils import fhir_object_utils


def _build_resource(nlp, diagnostic_report, nlp_output):
    nlp_name = type(nlp).__name__
    nlp_concepts = nlp_output.get('concepts')
    conditions_found = {}            # key is UMLS ID, value is the FHIR resource
    conditions_insight_counter = {}  # key is UMLS ID, value is the current insight_id_num
    for concept in nlp_concepts:
        the_type = concept['type']
        if isinstance(the_type, str):
            the_type = [the_type]
        if len(set(the_type) & set(["ICDiagnosis", 'umls.DiseaseOrSyndrome', 'umls.PathologicFunction', 'umls.SignOrSymptom', 'umls.NeoplasticProcess',
        'umls.CellOrMolecularDysfunction', 'umls.MentalOrBehavioralDysfunction'])) > 0:
            condition = conditions_found.get(concept["cui"])
            if condition is None:
                condition = Condition.construct()
                condition.meta = fhir_object_utils.add_resource_meta_unstructured(nlp, diagnostic_report)
                conditions_found[concept["cui"]] = condition
                insight_id_num = 1
            else:
                insight_id_num = conditions_insight_counter[concept["cui"]] + 1
            conditions_insight_counter[concept["cui"]] = insight_id_num
            insight_id_string = "insight-" + str(insight_id_num)
            _build_resource_data(condition, concept, insight_id_string)

            insight = Extension.construct()
            insight.url = insight_constants.INSIGHT_INSIGHT_ENTRY_URL

            insight_id_ext = fhir_object_utils.create_insight_extension(insight_id_string, insight_constants.INSIGHT_ID_UNSTRUCTURED_SYSTEM)
            insight.extension = [insight_id_ext]
            insight_detail = fhir_object_utils.create_insight_detail_extension(nlp_output)
            insight.extension.append(insight_detail)
            insight_span = fhir_object_utils.create_insight_span_extension(concept)
            insight.extension.append(insight_span)
            if "insightModelData" in concept:
                fhir_object_utils.add_diagnosis_confidences(insight.extension, concept["insightModelData"])
            result_extension = condition.meta.extension[0]
            result_extension.extension.append(insight)

    if len(conditions_found) == 0:
        return None
    return list(conditions_found.values())


def _build_resource_data(condition, concept, insight_id):
    if condition.code is None:
        codeable_concept = CodeableConcept.construct()
        codeable_concept.text = concept["preferredName"]
        condition.code = codeable_concept
        codeable_concept.coding = []
    fhir_object_utils.add_codings(concept, condition.code, insight_id, insight_constants.INSIGHT_ID_UNSTRUCTURED_SYSTEM)


def create_conditions_from_insights(nlp, diagnostic_report, nlp_output):
    conditions = _build_resource(nlp, diagnostic_report, nlp_output)
    if conditions is not None:
        for condition in conditions:
            condition.subject = diagnostic_report.subject
            fhir_object_utils.create_derived_resource_extension(condition)
    return conditions
