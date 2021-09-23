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

from typing import List
from typing import List

from fhir.resources.codeableconcept import CodeableConcept
from fhir.resources.condition import Condition
from fhir.resources.diagnosticreport import DiagnosticReport
from fhir.resources.documentreference import DocumentReference
from fhir.resources.resource import Resource
from ibm_whcs_sdk.annotator_for_clinical_data import ContainerAnnotation

from text_analytics import fhir_object_utils
from text_analytics.acd.fhir_enrichment.utils import acd_utils
from text_analytics.acd.fhir_enrichment.utils import enrichment_constants
from text_analytics.acd.fhir_enrichment.utils import fhir_object_utils as acd_fhir_utils
from text_analytics.types import UnstructuredFhirResourceType


def create_conditions_from_insights(
    resource: UnstructuredFhirResourceType, acd_output: ContainerAnnotation
) -> List[Condition]:
    """For the provided resource, and ACD output, create FHIR condition resources"""
    # build insight set from ACD output
    acd_attrs = acd_output.attribute_values
    conditions_found = {}  # key is UMLS ID, value is the FHIR resource
    conditions_insight_counter = (
        {}
    )  # key is UMLS ID, value is the current insight_id_num
    if acd_attrs:
        acd_concepts = acd_output.concepts
        for attr in acd_attrs:
            if attr.name in enrichment_constants.annotation_type_condition:
                concept = acd_utils.get_source_for_attribute(attr, acd_concepts)
                cui = concept.cui
                if cui not in conditions_found:
                    condition = Condition.construct()
                    conditions_found[cui] = condition
                    insight_id_num = 1
                else:
                    insight_id_num = conditions_insight_counter[cui] + 1

                insight_ext = fhir_object_utils.create_insight_extension_in_meta(
                    condition
                )

                conditions_insight_counter[cui] = insight_id_num
                insight_id_string = "insight-" + str(insight_id_num)
                _build_resource_data(condition, concept)

                insight_span_ext = acd_fhir_utils.create_unstructured_insight_detail(
                    insight_ext, insight_id_string, acd_output, diagnostic_report, attr
                )
                # Add confidences 
                insight_model_data = attr.insight_model_data
                if insight_model_data is not None:
                    acd_fhir_utils.add_diagnosis_confidences(
                        insight_span_ext.extension, insight_model_data
                    )

    if conditions_found:
        return None

    conditions = list(conditions_found.values())
    for condition in conditions:
        condition.subject = resource.subject
        fhir_object_utils.append_derived_by_nlp_extension(condition)
    return conditions


"""
def create_conditions_from_insights2(diagnostic_report, acd_output):
    # build insight set from ACD output
    acd_attrs = acd_output.attribute_values
    conditions_found = {}  # key is UMLS ID, value is the FHIR resource
    conditions_insight_counter = (
        {}
    )  # key is UMLS ID, value is the current insight_id_num
    if acd_attrs is not None:
        acd_concepts = acd_output.concepts
        for attr in acd_attrs:
            if attr.name in enrichment_constants.annotation_type_condition:
                concept = acd_utils.get_source_for_attribute(attr, acd_concepts)
                cui = concept.cui
                condition = conditions_found.get(cui)
                if condition is None:
                    condition = Condition.construct()
                    conditions_found[cui] = condition
                    insight_id_num = 1
                else:
                    insight_id_num = conditions_insight_counter[cui] + 1

                insight_ext = fhir_object_utils.create_insight_extension_in_meta(
                    condition
                )

                conditions_insight_counter[cui] = insight_id_num
                insight_id_string = "insight-" + str(insight_id_num)
                _build_resource_data(condition, concept)

                insight_span_ext = acd_fhir_utils.create_unstructured_insight_detail(
                    insight_ext, insight_id_string, acd_output, diagnostic_report, attr
                )
                # Add confidences
                insight_model_data = attr.insight_model_data
                if insight_model_data is not None:
                    acd_fhir_utils.add_diagnosis_confidences(
                        insight_span_ext.extension, insight_model_data
                    )

    if conditions_found:
        return None

    conditions = list(conditions_found.values())
    for condition in conditions:
        condition.subject = diagnostic_report.subject
        fhir_object_utils.append_derived_by_nlp_extension(condition)
    return conditions
"""


def _build_resource_data(condition : Condition, concept):
    if condition.code is None:
        codeable_concept = CodeableConcept.construct()
        codeable_concept.text = concept.preferred_name
        condition.code = codeable_concept
        codeable_concept.coding = []
    acd_fhir_utils.add_codings(concept, condition.code)
