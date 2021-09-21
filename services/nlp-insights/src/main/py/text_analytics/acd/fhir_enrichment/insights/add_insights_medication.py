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

from fhir.resources.codeableconcept import CodeableConcept
from fhir.resources.dosage import Dosage, DosageDoseAndRate
from fhir.resources.medicationstatement import MedicationStatement
from fhir.resources.quantity import Quantity
from fhir.resources.timing import Timing

from text_analytics import fhir_object_utils
from text_analytics import insight_constants
from text_analytics.acd.fhir_enrichment.utils import acd_utils
from text_analytics.acd.fhir_enrichment.utils import enrichment_constants
from text_analytics.acd.fhir_enrichment.utils import fhir_object_utils as acd_fhir_utils


logger = logging.getLogger("whpa-cdp-lib-fhir-enrichment")


def _create_med_statement_from_template():
    # Currently have to create medication statement object with required fields.
    # Doing just a .construct() and then adding the fields, causing a validation
    # error the first time a field is added
    # TODO: investigate a better way of doing this, ie can we turn off validation temporarily
    med_statement_template = {
        "status": "unknown",
        "medicationCodeableConcept": {"text": "template"},
    }
    med_statement = MedicationStatement.construct(**med_statement_template)
    return med_statement


def create_med_statements_from_insights(diagnostic_report, acd_output):
    # build insight set from ACD output
    acd_attrs = acd_output.attribute_values
    med_statements_found = {}  # key is UMLS ID, value is the FHIR resource
    med_statements_insight_counter = (
        {}
    )  # key is UMLS ID, value is the current insight_num
    if acd_attrs is not None:
        acd_medicationInds = acd_output.medication_ind
        for attr in acd_attrs:
            if attr.name in enrichment_constants.annotation_type_medication:
                medInd = acd_utils.get_source_for_attribute(attr, acd_medicationInds)
                cui = medInd.cui
                med_statement = med_statements_found.get(cui)
                if med_statement is None:
                    med_statement = _create_med_statement_from_template()
                    med_statements_found[cui] = med_statement
                    insight_id_num = 1
                else:
                    insight_id_num = med_statements_insight_counter[cui] + 1

                insight_ext = fhir_object_utils.create_insight_extension_in_meta(
                    med_statement
                )

                med_statements_insight_counter[cui] = insight_id_num
                insight_id_string = "insight-" + str(insight_id_num)
                _build_resource_data(med_statement, medInd, insight_id_string)

                insight_span_ext = acd_fhir_utils.create_unstructured_insight_detail(
                    insight_ext,
                    insight_id_string,
                    acd_output,
                    diagnostic_report,
                    medInd,
                )
                # Add confidences
                insight_model_data = attr.insight_model_data
                if insight_model_data is not None:
                    acd_fhir_utils.add_medication_confidences(
                        insight_span_ext.extension, insight_model_data
                    )

    if len(med_statements_found) == 0:
        return None
    else:
        med_statements = list(med_statements_found.values())
        for med_statement in med_statements:
            med_statement.subject = diagnostic_report.subject
            fhir_object_utils.append_derived_by_nlp_extension(med_statement)
    return med_statements


def _build_resource_data(med_statement, acd_medication, insight_id):
    if med_statement.status is None:
        # hard code to unknown for now
        med_statement.status = "unknown"

    # TODO: may need to reconsider hard coding into the first drug and first name entry
    # Currently we have only seen medication entries looking like this,
    # but suspect this may be problematic in the future
    acd_drug = acd_medication.drug[0].get("name1")[0]

    # Update template text
    # Should be template on the first occurrance found of the drug
    # Future occurrances of this drug in the same document will not be set to template
    # First instance will be dict until we create the CodeableConcept the first time
    if (
        type(med_statement.medicationCodeableConcept) is dict
        and med_statement.medicationCodeableConcept.get("text") == "template"
    ):
        codeable_concept = CodeableConcept.construct()
        # TODO: investigate in construction if we should be using drugSurfaceForm or drugNormalizedName
        codeable_concept.text = acd_drug.get("drugSurfaceForm")
        med_statement.medicationCodeableConcept = codeable_concept
        codeable_concept.coding = []

    acd_fhir_utils.add_codings_drug(acd_drug, med_statement.medicationCodeableConcept)

    if hasattr(acd_medication, "administration"):
        # Dosage
        dose_with_units = acd_medication.administration[0].get("dosageValue")
        if dose_with_units is not None:
            dose = Dosage.construct()
            dose_rate = DosageDoseAndRate.construct()
            dose_amount = None
            dose_units = None
            if " " in dose_with_units:
                # for now need parse, assuming units is after the first space
                dose_info = dose_with_units.split(" ")
                amount = dose_info[0].replace(",", "")  # Remove any commas, e.g. 1,000
                try:
                    dose_amount = float(amount)
                except OverflowError:
                    logger.exception("Enable to convert string to float: %s", amount)
                if isinstance(dose_info[1], str):
                    dose_units = dose_info[1]
            else:
                # if no space, assume only value
                amount = dose_with_units.replace(
                    ",", ""
                )  # Remove any commas, e.g. 1,000
                try:
                    dose_amount = float(amount)
                except OverflowError:
                    logger.exception("Unable to convert string to float: %s", amount)

            if dose_amount is not None:
                dose_quantity = Quantity.construct()
                dose_quantity.value = dose_amount
                if dose_units is not None:
                    dose_quantity.unit = dose_units
                dose_rate.doseQuantity = dose_quantity
                dose.doseAndRate = [dose_rate]

            if med_statement.dosage is None:
                med_statement.dosage = []
            med_statement.dosage.append(dose)

            # medication timing
            frequency = acd_medication.administration[0].get("frequencyValue")
            if frequency is not None:
                code = None
                display = None

                # TODO: Create function to map from ACD frequency to possible FHIR dose timings
                if frequency in ["Q AM", "Q AM.", "AM"]:
                    code = "AM"
                    display = "AM"
                elif frequency in ["Q PM", "Q PM.", "PM"]:
                    code = "PM"
                    display = "PM"

                if code is not None and display is not None:
                    timing = Timing.construct()
                    timing_codeable_concept = CodeableConcept.construct()
                    timing_codeable_concept.coding = [
                        fhir_object_utils.create_coding(
                            insight_constants.TIMING_URL, code, display
                        )
                    ]
                    timing_codeable_concept.text = frequency
                    timing.code = timing_codeable_concept
                    dose.timing = timing
