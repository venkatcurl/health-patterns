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

from collections import namedtuple
from typing import Iterable
from typing import List
from typing import Optional

from fhir.resources.codeableconcept import CodeableConcept
from fhir.resources.condition import Condition
from fhir.resources.resource import Resource
from ibm_whcs_sdk.annotator_for_clinical_data import (
    annotator_for_clinical_data_v1 as acd,
)
from ibm_whcs_sdk.annotator_for_clinical_data import ContainerAnnotation

from text_analytics import fhir_object_utils
from text_analytics.acd.fhir_enrichment.insights.insight_constants import (
    INSIGHT_ID_SYSTEM_URN,
)
from text_analytics.acd.fhir_enrichment.utils import fhir_object_utils as acd_fhir_utils
from text_analytics.acd.fhir_enrichment.utils.acd_utils import filter_attribute_values
from text_analytics.acd.fhir_enrichment.utils.enrichment_constants import (
    ANNOTATION_TYPE_CONDITION,
)
from text_analytics.acd.fhir_enrichment.utils.fhir_object_utils import (
    create_ACD_output_extension,
)
from text_analytics.acd.fhir_enrichment.utils.fhir_object_utils import (
    get_diagnosis_confidences,
)
from text_analytics.fhir_object_utils import (
    create_unstructured_insight_detail_extension,
    create_insight_id_extension,
    add_unstructured_insight_to_meta,
)
from text_analytics.insight_id import insight_id_maker
from text_analytics.insight_source import UnstructuredSource
from text_analytics.span import Span
from text_analytics.types import UnstructuredFhirResourceType


def create_conditions_from_insights(
    source_resource: UnstructuredFhirResourceType, acd_output: ContainerAnnotation
) -> Optional[List[Condition]]:
    """For the provided resource, and ACD output, create FHIR condition resources

    Args:
        source-resource - the resource that NLP was run over (must be unstructured)
        acd_output - the acd output

    Returns conditions derived by NLP, or None if there are no conditions
    """
    acd_attrs: List[acd.AttributeValueAnnotation] = acd_output.attribute_values
    TrackerEntry = namedtuple("TrackerEntry", ["fhir_resource", "id_maker"])
    condition_tracker = {}  # key is UMLS ID, value is TrackerEntry

    acd_concepts: List[acd.Concept] = acd_output.concepts
    if acd_attrs and acd_concepts:
        for attr in filter_attribute_values(acd_attrs, ANNOTATION_TYPE_CONDITION):
            concept: acd.Concept = _get_concept_for_attribute(attr, acd_concepts)
            if concept.cui not in condition_tracker:
                condition_tracker[concept.cui] = TrackerEntry(
                    fhir_resource=Condition.construct(subject=source_resource.subject),
                    id_maker=insight_id_maker(),
                )

            condition, id_maker = condition_tracker[concept.cui]

            _add_insight_to_condition(
                source_resource, condition, attr, concept, acd_output, next(id_maker)
            )

    if not condition_tracker:
        return None

    conditions = [entry.fhir_resource for entry in condition_tracker.values()]

    for condition in conditions:
        fhir_object_utils.append_derived_by_nlp_extension(condition)

    return conditions


def _get_concept_for_attribute(
    attr: acd.AttributeValueAnnotation, concepts: Iterable[acd.Concept]
) -> acd.Concept:
    """Finds the concept associated with the ACD attribute

    The "associated" concept is the one with the uid indicated by the attribute.
    This will be the "source" for the attribute (eg the annotation used to create the attribute).

     Args:
        attr - the ACD attribute value
        acd_annotations - the list of acd concepts to search

     Returns:
        The concept that was used to create the attribute."""
    concept = attr.concept
    uid = concept.uid
    for concept in concepts:
        if concept.uid == uid:
            return concept

    return None


def _add_insight_to_condition(
    source_resource: Resource,
    condition: Condition,
    attr: acd.AttributeValueAnnotation,
    concept: acd.Concept,
    acd_output: acd.ContainerAnnotation,
    insight_id_string: str,
):
    """Adds data from the insight to the condition"""
    insight_id_ext = create_insight_id_extension(
        insight_id_string, INSIGHT_ID_SYSTEM_URN
    )

    source = UnstructuredSource(
        resource=source_resource,
        span=Span(begin=attr.begin, end=attr.end, covered_text=attr.covered_text),
    )

    if attr.insight_model_data:
        confidences = get_diagnosis_confidences(attr.insight_model_data)
    else:
        confidences = None

    unstructured_insight_detail = create_unstructured_insight_detail_extension(
        source=source,
        confidences=confidences,
        nlp_extensions=[create_ACD_output_extension(acd_output)],
    )

    add_unstructured_insight_to_meta(
        condition, insight_id_ext, unstructured_insight_detail
    )

    _add_insight_codings_to_condition(condition, concept)


def _add_insight_codings_to_condition(
    condition: Condition, concept: acd.Concept
) -> None:
    """Adds informatino from the insight's concept to a condition

    Args:
        Condition - condition to update
        Concept   - concept with data to update the condition with
    """
    if condition.code is None:
        codeable_concept = CodeableConcept.construct()
        codeable_concept.text = concept.preferred_name
        condition.code = codeable_concept
        codeable_concept.coding = []

    acd_fhir_utils.add_codings(concept, condition.code)
