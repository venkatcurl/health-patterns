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

from fhir.resources.extension import Extension
from acd.fhir_enrichment.insights import insight_constants
from acd.fhir_enrichment.utils import acd_utils
from acd.fhir_enrichment.utils import fhir_object_utils


# Parameters:
#   ai_results: list of tuples - where the tuple is
#     - codeable concept object to enrich
#     - fhir path for that object
#     - acd output for that field
#     example: [[AllergyIntolerance.code, "AllergyIntolerance.code", ai_result1],
#             [AllergyIntolerance.reaction[0].manifestation[0], "AllergyIntolerance.reaction[0].manifestation[0]", ai_result2],
#             [AllergyIntolerance.reaction[0].manifestation[1], "AllergyIntolerance.reaction[0].manifestation[1]", ai_result3]]
#   fhir_resource: FHIR resource object that is updated (ie Condition, Immunization, AllergyIntolerance)
#   conceptType: List of concepts to use to generate insights
# Returns the updated resource if any insights were added to it.  Returns None if no insights found (resource not updated).
def update_with_insights(ai_results, fhir_resource, conceptType):
    insight_num = 0
    # adding codings to each field run through ACD
    for codeable_concept, fhir_path, acd_result in ai_results:
        acd_attrs = acd_result.attribute_values
        if acd_attrs is not None:
            concepts = acd_result.concepts
            for attr in acd_attrs:
                if attr.name in conceptType:
                    # TODO check if the coding already exists in the FHIR resource

                    # Add a new insight
                    insight_num = insight_num + 1
                    insight_id = "insight-" + str(insight_num)

                    if codeable_concept.coding is None:
                        codeable_concept.coding = []
                    concept = acd_utils.get_source_for_attribute(attr, concepts)
                    fhir_object_utils.add_codings_with_extension(concept, codeable_concept)

                    # Create meta if any insights were added
                    insight_ext = fhir_object_utils.add_resource_meta(fhir_resource)
                    insight_id_ext = fhir_object_utils.create_insight_id_extension(insight_id, insight_constants.INSIGHT_ID_SYSTEM_URN)
                    insight_ext.extension = [insight_id_ext]

                    # Create insight detail for resource meta extension
                    insight_detail = Extension.construct()
                    insight_detail.url = insight_constants.INSIGHT_DETAIL_URL
                    # Save acd result
                    evaluated_output_ext = fhir_object_utils.create_ACD_output_extension(acd_result)
                    insight_detail.extension = [evaluated_output_ext]
                    # Add reference path to insight added in resource
                    reference_path_ext = fhir_object_utils.create_reference_path_extension(fhir_path)
                    insight_detail.extension.append(reference_path_ext)

                    insight_ext.extension.append(insight_detail)

    if insight_num == 0:  # No insights found
        return None

    return fhir_resource
