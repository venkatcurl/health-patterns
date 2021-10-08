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
""""
Process ACD output and derive conditions
"""

from collections import namedtuple
from typing import Iterable
from typing import List
from typing import Optional

from fhir.resources.codeableconcept import CodeableConcept
from fhir.resources.condition import Condition
from fhir.resources.extension import Extension
from ibm_whcs_sdk.annotator_for_clinical_data import (
    annotator_for_clinical_data_v1 as acd,
)
from ibm_whcs_sdk.annotator_for_clinical_data import ContainerAnnotation
from ibm_whcs_sdk.annotator_for_clinical_data.annotator_for_clinical_data_v1 import (
    InsightModelData,
)

from text_analytics.fhir.fhir_object_utils import (
    create_derived_from_unstructured_insight_detail_extension,
    create_insight_id_extension,
    add_insight_to_meta,
    append_derived_by_nlp_extension,
    append_coding,
    create_confidence_extension,
)
from text_analytics.insight import insight_constants
from text_analytics.insight.insight_id import insight_id_maker
from text_analytics.insight.span import Span
from text_analytics.insight.text_fragment import TextFragment
from text_analytics.insight_source.unstructured_text import UnstructuredText
from text_analytics.nlp.acd.fhir_enrichment.insights.enrichment_constants import (
    ANNOTATION_TYPE_CONDITION,
)
from text_analytics.nlp.acd.fhir_enrichment.utils.acd_utils import (
    filter_attribute_values,
)
from text_analytics.nlp.nlp_config import NlpConfig


def create_conditions_from_insights(
    text_source: UnstructuredText,
    acd_output: ContainerAnnotation,
    nlp_config: NlpConfig,
) -> Optional[List[Condition]]:
    """For the provided source and ACD output, create FHIR condition resources

    Args:
        text_source - the text that NLP was run over
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
                            subject=text_source.source_resource.subject
                        ),
                        id_maker=insight_id_maker(start=nlp_config.insight_id_start),
                    )

                condition, id_maker = condition_tracker[concept.cui]

                _add_insight_to_condition(
                    text_source,
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
        append_derived_by_nlp_extension(condition)

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


def _add_insight_to_condition(  # pylint: disable=too-many-arguments;
    text_source: UnstructuredText,
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

    source = TextFragment(
        text_source=text_source,
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

    add_codings(concept, condition.code)


def add_codings(concept: acd.Concept, codeable_concept: CodeableConcept) -> None:
    """
    Adds codes from the concept to the codeable_concept.

    Does not add an extension indicating the code is derived.
    Parameters:
        concept - ACD concept
        codeable_concept - FHIR codeable concept the codes will be added to
    """
    if concept.cui is not None:
        # For CUIs, we do not handle comma-delimited values (have not seen that we ever have more than one value)
        append_coding(
            codeable_concept,
            insight_constants.UMLS_URL,
            concept.cui,
            concept.preferred_name,
        )

    if concept.snomed_concept_id:
        _append_coding_entries(
            codeable_concept, insight_constants.SNOMED_URL, concept.snomed_concept_id
        )
    if concept.nci_code:
        _append_coding_entries(
            codeable_concept, insight_constants.NCI_URL, concept.nci_code
        )
    if concept.loinc_id:
        _append_coding_entries(
            codeable_concept, insight_constants.LOINC_URL, concept.loinc_id
        )
    if concept.mesh_id:
        _append_coding_entries(
            codeable_concept, insight_constants.MESH_URL, concept.mesh_id
        )
    if concept.icd9_code:
        _append_coding_entries(
            codeable_concept, insight_constants.ICD9_URL, concept.icd9_code
        )
    if concept.icd10_code:
        _append_coding_entries(
            codeable_concept, insight_constants.ICD10_URL, concept.icd10_code
        )
    if concept.rx_norm_id:
        _append_coding_entries(
            codeable_concept, insight_constants.RXNORM_URL, concept.rx_norm_id
        )


def _append_coding_entries(
    codeable_concept: CodeableConcept, system: str, csv_ids: str
) -> None:
    """Appends multiple codings when the id may be a csv list of codes

    An NLP derived extension is NOT added.
    A code will not be added if a code with the same system and id already exists

    Args:
        codeable_concept - concept to add code to
        system - system for the code
        id - and id for csv of ids to add codings for
    """
    for code_id in csv_ids.split(","):
        append_coding(codeable_concept, system, code_id)


def get_diagnosis_confidences(
    insight_model_data: InsightModelData,
) -> Optional[List[Extension]]:
    if not insight_model_data:
        return None

    confidence_list = []

    try:
        confidence_list.append(
            create_confidence_extension(
                insight_constants.CONFIDENCE_SCORE_EXPLICIT,
                insight_model_data.diagnosis.usage.explicit_score,
            )
        )
    except AttributeError:
        pass

    try:
        confidence_list.append(
            create_confidence_extension(
                insight_constants.CONFIDENCE_SCORE_PATIENT_REPORTED,
                insight_model_data.diagnosis.usage.patient_reported_score,
            )
        )
    except AttributeError:
        pass

    try:
        confidence_list.append(
            create_confidence_extension(
                insight_constants.CONFIDENCE_SCORE_DISCUSSED,
                insight_model_data.diagnosis.usage.discussed_score,
            )
        )
    except AttributeError:
        pass

    try:
        confidence_list.append(
            create_confidence_extension(
                insight_constants.CONFIDENCE_SCORE_FAMILY_HISTORY,
                insight_model_data.diagnosis.family_history_score,
            )
        )
    except AttributeError:
        pass

    try:
        confidence_list.append(
            create_confidence_extension(
                insight_constants.CONFIDENCE_SCORE_SUSPECTED,
                insight_model_data.diagnosis.suspected_score,
            )
        )
    except AttributeError:
        pass

    return confidence_list if confidence_list else None