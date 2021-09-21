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

from ibm_whcs_sdk import annotator_for_clinical_data as acd

from text_analytics.acd.fhir_enrichment import logging_codes
from text_analytics.acd.fhir_enrichment.insights.add_insights_condition import create_conditions_from_insights
from text_analytics.acd.fhir_enrichment.insights.add_insights_medication import create_med_statements_from_insights
from text_analytics.acd.fhir_enrichment.insights.update_structured_resources import update_with_insights
from text_analytics.fhir_object_utils import create_transaction_bundle


logger = logging.getLogger('whpa-cdp-lib-fhir-enrichment')


# Enrich_fhir_resource adds insights to an existing FHIR Resource (like Immunization, Condition, AllergyIntolerance) and creates bundle
#
# ai_results = list of list(s) - where the sub list is
#        the fhir field object to update
#        the fhir path to the object to update
#        the acd response for that field
#        examples:
#           [[Condition.code, "Condition.code", ai_result1]
#           [[Immunization.vaccineCode, "Immunization.vaccineCode", ai_result1]
#           [[AllergyIntolerance.code, "AllergyIntolerance.code", ai_result1],
#             [AllergyIntolerance.reaction[0].manifestation[0], "AllergyIntolerance.reaction[0].manifestation[0]", ai_result2],
#             [AllergyIntolerance.reaction[0].manifestation[1], "AllergyIntolerance.reaction[0].manifestation[1]", ai_result3]]
# fhir_resource - FHIR resource input before insights are added
# annotation_type - concept from ACD used to generate insights
def enrich_structured_resource(ai_results, fhir_resource, annotation_type):
    updated_resource = update_with_insights(ai_results, fhir_resource, annotation_type)

    # create fhir bundle with transaction
    bundle = None
    if updated_resource is not None:
        url_transaction = updated_resource.resource_type + "/" + str(updated_resource.id)
        bundle = create_transaction_bundle([[updated_resource, 'PUT', url_transaction]])
    return bundle


"""
enrich_diagnostic_report creates appropriate resources (MedicationStatement, Condition
and adds insights. Then it creates a bundle of resource(s).

immunization - FHIR DiagnosticReport input
acd_result - ACD ContainerAnnotation, used for mock ACD output
"""
def enrich_diagnostic_report(diagnostic_report_fhir, ai_result):
    try:
        create_conditions_fhir = create_conditions_from_insights(diagnostic_report_fhir, ai_result)
        create_med_statements_fhir = create_med_statements_from_insights(diagnostic_report_fhir, ai_result)
    except acd.ACDException as ex:
        logger.exception("ACD returned an error code=%s message=%s correlation_id=%s",
                         ex.code,
                         ex.message,
                         ex.correlation_id)
        return None
    except Exception:
        logger.exception("could not find data %s", str(diagnostic_report_fhir))
        return None

    # create fhir bundle with transaction
    bundle_entries = []

    # Only create and send back a bundle if there were conditions found.
    if create_conditions_fhir is not None:
        for condition in create_conditions_fhir:
            bundle_entry = []
            bundle_entry.append(condition)
            bundle_entry.append('POST')
            bundle_entry.append(condition.resource_type)
            bundle_entries.append(bundle_entry)
    if create_med_statements_fhir is not None:
        for med_statement in create_med_statements_fhir:
            bundle_entry = []
            bundle_entry.append(med_statement)
            bundle_entry.append('POST')
            bundle_entry.append(med_statement.resource_type)
            bundle_entries.append(bundle_entry)
    if create_conditions_fhir is None and create_med_statements_fhir is None:
        # If no conditions or medications were found, return None
        bundle = None

    if len(bundle_entries) > 0:
        bundle = create_transaction_bundle(bundle_entries)

    return bundle
