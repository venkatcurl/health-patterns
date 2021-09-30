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

from typing import Generator
from typing import Iterable
from typing import List
from typing import NamedTuple
from typing import Optional

from fhir.resources.allergyintolerance import AllergyIntolerance
from fhir.resources.condition import Condition
from fhir.resources.immunization import Immunization
from fhir.resources.resource import Resource
from ibm_whcs_sdk.annotator_for_clinical_data import (
    annotator_for_clinical_data_v1 as acd,
)

from text_analytics import fhir_object_utils
from text_analytics.acd.fhir_enrichment.utils import enrichment_constants
from text_analytics.acd.fhir_enrichment.utils import fhir_object_utils as acd_fhir_utils
from text_analytics.acd.fhir_enrichment.utils.acd_utils import filter_attribute_values
from text_analytics.acd.insight_constants import INSIGHT_ID_SYSTEM_URN
from text_analytics.concept_text_adjustment import AdjustedConceptRef
from text_analytics.insight_id import insight_id_maker


class CodeableConceptAcdInsight(NamedTuple):
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
    for c in concepts:
        if c.uid == uid:
            return c
    return None


def _add_insight_to_resource_meta(
    fhir_resource: Resource,
    insight: CodeableConceptAcdInsight,
    insight_id_str: str,
    system: str = INSIGHT_ID_SYSTEM_URN,
) -> None:
    """Updates the meta section of a resource with extensions for the insight

    Args:
        fhir_resource - resource to update meta
        insight - the new insight
        insight_id_str - identifier for the new insight
    """

    insight_id_ext = fhir_object_utils.create_insight_id_extension(
        insight_id_str, system
    )

    reference_path_ext = fhir_object_utils.create_reference_path_extension(
        insight.adjusted_concept.concept_ref.fhir_path
    )

    evaluated_output_ext = acd_fhir_utils.create_ACD_output_extension(
        insight.acd_response
    )

    insight_detail = (
        fhir_object_utils.create_derived_from_concept_insight_detail_extension(
            reference_path_ext, [evaluated_output_ext]
        )
    )

    fhir_object_utils.add_insight_to_meta(fhir_resource, insight_id_ext, insight_detail)


def _add_codeable_concept_insight(
    fhir_resource: Resource,
    insight: CodeableConceptAcdInsight,
    id_maker: Generator[str, None, None],
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

    Returns: the number of codings added to the codeable concept.
    """
    concepts: List[acd.Concept] = insight.acd_response.concepts
    concept_ref = insight.adjusted_concept.concept_ref
    acd_attr_types = _get_acd_attr_types(fhir_resource)
    total_num_codes_added: int = 0

    if insight.acd_response.attribute_values:
        for attr in filter_attribute_values(
            insight.acd_response.attribute_values, acd_attr_types
        ):
            acd_concept: acd.Concept = _get_source_for_attribute(attr, concepts)

            num_codes_appended: int = (
                acd_fhir_utils.append_codings_with_nlp_derived_extension(
                    acd_concept, concept_ref.code_ref
                )
            )

            if num_codes_appended > 0:
                total_num_codes_added += num_codes_appended
                _add_insight_to_resource_meta(fhir_resource, insight, next(id_maker))

    return total_num_codes_added


def update_codeable_concepts_and_meta_with_insights(
    fhir_resource: Resource, concept_insights: List[CodeableConceptAcdInsight]
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

    Returns: total number of derived codings added to the resource, across all provided
             codeable concepts.
    """
    id_maker = insight_id_maker()

    num_codes_added: int = 0

    for concept_insight in concept_insights:
        num_codes_added += _add_codeable_concept_insight(
            fhir_resource, concept_insight, id_maker
        )

    return num_codes_added
