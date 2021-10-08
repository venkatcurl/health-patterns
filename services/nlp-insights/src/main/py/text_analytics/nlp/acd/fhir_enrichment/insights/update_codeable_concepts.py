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

from typing import Generator
from typing import Iterable
from typing import List
from typing import NamedTuple
from typing import Optional

from fhir.resources.allergyintolerance import AllergyIntolerance
from fhir.resources.codeableconcept import CodeableConcept
from fhir.resources.condition import Condition
from fhir.resources.immunization import Immunization
from fhir.resources.resource import Resource
from ibm_whcs_sdk.annotator_for_clinical_data import (
    annotator_for_clinical_data_v1 as acd,
)

from text_analytics.fhir import fhir_object_utils
from text_analytics.insight import insight_constants
from text_analytics.insight.insight_id import insight_id_maker
from text_analytics.insight_source.concept_text_adjustment import AdjustedConceptRef
from text_analytics.nlp.acd.fhir_enrichment.insights import enrichment_constants
from text_analytics.nlp.acd.fhir_enrichment.utils.acd_utils import (
    filter_attribute_values,
)
from text_analytics.nlp.nlp_config import NlpConfig


class AcdConceptRef(NamedTuple):
    """Binding between reference to a codeable concept with adjusted text, and an ACD NLP Response"""

    adjusted_concept: AdjustedConceptRef
    acd_response: acd.ContainerAnnotation


def _get_acd_attr_types(fhir_resource: Resource) -> Optional[Iterable[str]]:
    """Given a resource to enrich, returns ACD attribute names that are relevant insights"""
    if isinstance(fhir_resource, AllergyIntolerance):
        return enrichment_constants.ANNOTATION_TYPE_ALLERGY

    if isinstance(fhir_resource, Condition):
        return enrichment_constants.ANNOTATION_TYPE_CONDITION

    if isinstance(fhir_resource, Immunization):
        return enrichment_constants.ANNOTATION_TYPE_IMMUNIZATION

    return None


def _get_source_for_attribute(
    attr: acd.AttributeValueAnnotation, concepts: List[acd.Concept]
) -> Optional[acd.Concept]:
    """Searches the list of concepts for the concept that is associated with that value annotation

    Args: attr - the attribute to find associated concept
          concepts - list of candidate concepts

    Returns: The concept, or none if concept was not found.
    """
    concept = attr.concept
    uid = concept.uid
    for concept in concepts:
        if concept.uid == uid:
            return concept
    return None


def _add_codeable_concept_insight(
    fhir_resource: Resource,
    insight: AcdConceptRef,
    id_maker: Generator[str, None, None],
    nlp_config: NlpConfig,
) -> int:
    """Updates a codeable concept and resource meta with ACD insights.

    The codeable concept referenced by the insight is updated with codings that were
    derived from the text.

    The meta extension for the supplied resource is updated with the insight id and
    reference path.

    Args:
        fhir_resource - the resource to update the meta with the new insight
        insight - binding between the concept text that was analyzed by ACD-NLP and the
                  ACD response for that analysis.
        id_maker - generator for producing ids for insights
        nlp_config - nlp configuration

    Returns: the number of codings added to the codeable concept.
    """
    concepts: List[acd.Concept] = insight.acd_response.concepts
    concept_ref = insight.adjusted_concept.concept_ref
    acd_attr_types = _get_acd_attr_types(fhir_resource)
    total_num_codes_added: int = 0

    if acd_attr_types and insight.acd_response.attribute_values:
        for attr in filter_attribute_values(
            insight.acd_response.attribute_values, acd_attr_types
        ):
            acd_concept: acd.Concept = _get_source_for_attribute(attr, concepts)

            num_codes_appended: int = _append_codings_with_nlp_derived_extension(
                acd_concept, concept_ref.code_ref
            )

            if num_codes_appended > 0:
                total_num_codes_added += num_codes_appended
                fhir_object_utils.append_insight_with_path_expr_to_resource_meta(
                    fhir_resource=fhir_resource,
                    insight_id=next(id_maker),
                    system=nlp_config.nlp_system,
                    fhir_path=insight.adjusted_concept.concept_ref.fhir_path,
                    nlp_output_uri=nlp_config.get_nlp_output_loc(insight.acd_response),
                )

    return total_num_codes_added


def _append_coding_entries_with_extension(
    codeable_concept: CodeableConcept, system: str, csv_code_id: str
) -> int:
    """Separates each code from a csv string and appends the code to the codeable concept

    Args:
        codeable_concept - concept to update
        system - system to use for the code(s)
        csv_code_id - code(s) to append
    Returns: number of codes added
    """
    codes_added = 0
    for code_id in csv_code_id.split(","):
        codes_added += fhir_object_utils.append_derived_by_nlp_coding(
            codeable_concept, system, code_id
        )

    return codes_added


def _append_codings_with_nlp_derived_extension(
    acd_concept: acd.Concept, codeable_concept: CodeableConcept
) -> int:
    """
     Adds codes from the concept to the codeable_concept.
     Adds extension indicating the code is derived.
     Parameters:
        concept - ACD concept
        codeable_concept - FHIR codeable concept the codes will be added to

    Returns:
        number of codes added
    """
    codes_added : int = 0
    
    if acd_concept.cui is not None:
        # For CUIs, we do not handle comma-delimited values (have not seen that we ever have more than one value)
        # We use the preferred name from UMLS for the display text
        codes_added += fhir_object_utils.append_derived_by_nlp_coding(
            codeable_concept,
            insight_constants.UMLS_URL,
            acd_concept.cui,
            acd_concept.preferred_name,
        )

    if acd_concept.snomed_concept_id is not None:
        codes_added += _append_coding_entries_with_extension(
            codeable_concept,
            insight_constants.SNOMED_URL,
            acd_concept.snomed_concept_id,
        )
    if acd_concept.nci_code is not None:
        codes_added += _append_coding_entries_with_extension(
            codeable_concept, insight_constants.NCI_URL, acd_concept.nci_code
        )
    if acd_concept.loinc_id is not None:
        codes_added += _append_coding_entries_with_extension(
            codeable_concept, insight_constants.LOINC_URL, acd_concept.loinc_id
        )
    if acd_concept.mesh_id is not None:
        codes_added += _append_coding_entries_with_extension(
            codeable_concept, insight_constants.MESH_URL, acd_concept.mesh_id
        )
    if acd_concept.icd9_code is not None:
        codes_added += _append_coding_entries_with_extension(
            codeable_concept, insight_constants.ICD9_URL, acd_concept.icd9_code
        )
    if acd_concept.icd10_code is not None:
        codes_added += _append_coding_entries_with_extension(
            codeable_concept, insight_constants.ICD10_URL, acd_concept.icd10_code
        )
    if acd_concept.rx_norm_id is not None:
        codes_added += _append_coding_entries_with_extension(
            codeable_concept, insight_constants.RXNORM_URL, acd_concept.rx_norm_id
        )

    return codes_added


def update_codeable_concepts_and_meta_with_insights(
    fhir_resource: Resource,
    concept_insights: List[AcdConceptRef],
    nlp_config: NlpConfig,
) -> int:
    """Updates the resource with derived insights

    Each element in concept insights contains a reference a codeable concept within the resource to
    enrich, as well as the adjusted text and ACD response for the NLP.

    The codings are updated with additional codings derived by ACD.
    The meta of the FHIR resource is updated with the insight details extension.

    Args:
        fhir_resource - the fhir resource to update the meta
        concept_insights - collection of concepts to enrich with insights.
                           These concepts should be contained within the FHIR resource.
        nlp_config - NLP configuration

    Returns: total number of derived codings added to the resource, across all provided
             codeable concepts.
    """
    id_maker = insight_id_maker(start=nlp_config.insight_id_start)

    num_codes_added: int = 0

    for concept_insight in concept_insights:
        num_codes_added += _add_codeable_concept_insight(
            fhir_resource, concept_insight, id_maker, nlp_config
        )

    return num_codes_added
