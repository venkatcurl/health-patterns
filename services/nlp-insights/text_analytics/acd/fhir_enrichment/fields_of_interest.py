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

import logging
from acd.fhir_enrichment.utils.enrichment_constants import ALLERGEN, CONDITION, MANIFESTATION, VACCINE

logger = logging.getLogger('whpa-cdp-lib-fhir-enrichment')


# Returns a list of tuples containing
#  - the type of data
#  - the object for insight enhancement
#  - FHIR path to the object of insight
#  - the associated text
# The object for insight enhancement, and FHIR path, can be either the allergen code or the reaction manifestation.
#   example: [(ALLERGEN, AllergyIntolerance.code, "AllergyIntolerance.code", AllergyIntolerance.code.text),
#             (MANIFESTATION, AllergyIntolerance.reaction[0].manifestation[0], "AllergyIntolerance.reaction[0].manifestation[0]", AllergyIntolerance.reaction[0].manifestation[0].text),
#             (MANIFESTATION, AllergyIntolerance.reaction[0].manifestation[1], "AllergyIntolerance.reaction[0].manifestation[1]", AllergyIntolerance.reaction[0].manifestation[1].text)]
def allergy_intolerance_fields_of_interest(allergy_intolerance):
    fields_of_interest = []

    # AllergyIntolerance has multiple fields to NLP:
    #    AllergyIntolerance.code.text
    #    AllergyIntolerance.reaction[].manifestation[].text
    if allergy_intolerance.code.text is not None:
        fhir_path = "AllergyIntolerance.code"
        fields_of_interest.append((ALLERGEN, allergy_intolerance.code, fhir_path, allergy_intolerance.code.text))

    if allergy_intolerance.reaction is not None:
        reaction_counter = 0
        for reaction in allergy_intolerance.reaction:
            manifestation_counter = 0
            for mf in reaction.manifestation:
                fhir_path = f'AllergyIntolerance.reaction[{reaction_counter}].manifestation[{manifestation_counter}]'
                fields_of_interest.append((MANIFESTATION, mf, fhir_path, mf.text))
                manifestation_counter += 1
            reaction_counter += 1

    return fields_of_interest


# Returns a list with a single tuple containing
#  - the type of data
#  - the object for insight enhancement
#  - FHIR path to the object of insight: "Condition.code"
#  - the associated text
def condition_fields_of_interest(condition):
    fields_of_interest = []
    if condition.code.text is not None:
        fhir_path = "Condition.code"
        fields_of_interest.append((CONDITION, condition.code, fhir_path, condition.code.text))

    return fields_of_interest


# Returns a list with a single tuple containing
#  - the type of data
#  - the object for insight enhancement
#  - FHIR path to the object of insight: "Immunization.vaccineCode"
#  - the associated text
def immunization_fields_of_interest(immunization):
    fields_of_interest = []
    if immunization.vaccineCode.text is not None:
        fhir_path = "Immunization.vaccineCode"
        fields_of_interest.append((VACCINE, immunization.vaccineCode, fhir_path, immunization.vaccineCode.text))

    return fields_of_interest
