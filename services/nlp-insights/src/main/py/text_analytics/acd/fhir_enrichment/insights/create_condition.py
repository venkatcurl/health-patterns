# Copyright 2021 IBM All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

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
from text_analytics.acd.fhir_enrichment.utils import fhir_object_utils as acd_fhir_utils
from text_analytics.acd.fhir_enrichment.utils.acd_utils import filter_attribute_values
from text_analytics.acd.fhir_enrichment.utils.enrichment_constants import (
    ANNOTATION_TYPE_CONDITION,
)
from text_analytics.acd.fhir_enrichment.utils.fhir_object_utils import (
    get_diagnosis_confidences,
)
from text_analytics.fhir_object_utils import (
    create_derived_from_unstructured_insight_detail_extension,
    create_insight_id_extension,
    add_insight_to_meta,
)
from text_analytics.insight_id import insight_id_maker
from text_analytics.insight_source import UnstructuredSource
from text_analytics.nlp_config import NlpConfig
from text_analytics.span import Span
from text_analytics.types import UnstructuredFhirResourceType


def create_conditions_from_insights(
    source_resource: UnstructuredFhirResourceType,
    acd_output: ContainerAnnotation,
    nlp_config: NlpConfig,
) -> Optional[List[Condition]]:
    """For the provided resource, and ACD output, create FHIR condition resources

    Args:
        source-resource - the resource that NLP was run over (must be unstructured)
        acd_output - the acd output
        nlp_config - nlp configuration

    Returns conditions derived by NLP, or None if there are no conditions
    """
    acd_attrs: List[acd.AttributeValueAnnotation] = acd_output.attribute_values
    TrackerEntry = namedtuple("TrackerEntry", ["fhir_resource", "id_maker"])
    condition_tracker = {}  # key is UMLS ID, value is TrackerEntry

    acd_concepts: List[acd.Concept] = acd_output.concepts
    if acd_attrs and acd_concepts:
        for attr in filter_attribute_values(acd_attrs, ANNOTATION_TYPE_CONDITION):
            concept = _get_concept_for_attribute(attr, acd_concepts)
            if concept:
                if concept.cui not in condition_tracker:
                    condition_tracker[concept.cui] = TrackerEntry(
                        fhir_resource=Condition.construct(
                            subject=source_resource.subject
                        ),
                        id_maker=insight_id_maker(),
                    )

                condition, id_maker = condition_tracker[concept.cui]

                _add_insight_to_condition(
                    source_resource,
                    condition,
                    attr,
                    concept,
                    acd_output,
                    next(id_maker),
                    nlp_config,
                )

    if not condition_tracker:
        return None

    conditions = [entry.fhir_resource for entry in condition_tracker.values()]

    for condition in conditions:
        fhir_object_utils.append_derived_by_nlp_extension(condition)

    return conditions


def _get_concept_for_attribute(
    attr: acd.AttributeValueAnnotation, concepts: Iterable[acd.Concept]
) -> Optional[acd.Concept]:
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
    nlp_config: NlpConfig,
) -> None:
    """Adds data from the insight to the condition"""
    insight_id_ext = create_insight_id_extension(
        insight_id_string, nlp_config.nlp_system
    )

    source = UnstructuredSource(
        resource=source_resource,
        text_span=Span(begin=attr.begin, end=attr.end, covered_text=attr.covered_text),
    )

    confidences = get_diagnosis_confidences(attr.insight_model_data)

    nlp_output_ext = nlp_config.create_nlp_output_extension(acd_output)

    unstructured_insight_detail = (
        create_derived_from_unstructured_insight_detail_extension(
            source=source,
            confidences=confidences,
            nlp_extensions=[nlp_output_ext] if nlp_output_ext else None,
        )
    )

    add_insight_to_meta(condition, insight_id_ext, unstructured_insight_detail)

    _add_insight_codings_to_condition(condition, concept)


def _add_insight_codings_to_condition(
    condition: Condition, concept: acd.Concept
) -> None:
    """Adds information from the insight's concept to a condition

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
