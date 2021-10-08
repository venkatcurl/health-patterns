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
import logging
from typing import Any
from typing import Dict
from typing import Iterable
from typing import List
from typing import Optional

from fhir.resources.codeableconcept import CodeableConcept
from fhir.resources.dosage import Dosage, DosageDoseAndRate
from fhir.resources.extension import Extension
from fhir.resources.medicationstatement import MedicationStatement
from fhir.resources.quantity import Quantity
from fhir.resources.reference import Reference
from fhir.resources.timing import Timing
from ibm_whcs_sdk.annotator_for_clinical_data import (
    annotator_for_clinical_data_v1 as acd,
)
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
    create_coding,
)
from text_analytics.insight import insight_constants
from text_analytics.insight.insight_id import insight_id_maker
from text_analytics.insight.span import Span
from text_analytics.insight.text_fragment import TextFragment
from text_analytics.insight_source.unstructured_text import UnstructuredText
from text_analytics.nlp.acd.fhir_enrichment.insights.enrichment_constants import (
    ANNOTATION_TYPE_MEDICATION,
)
from text_analytics.nlp.acd.fhir_enrichment.utils.acd_utils import (
    filter_attribute_values,
)
from text_analytics.nlp.nlp_config import NlpConfig


logger = logging.getLogger("whpa-cdp-lib-fhir-enrichment")


def create_med_statements_from_insights(
    text_source: UnstructuredText,
    acd_output: acd.ContainerAnnotation,
    nlp_config: NlpConfig,
) -> Optional[List[MedicationStatement]]:
    """Creates medication statements, given acd data from the text source

    Args:
        text_source - the resource that NLP was run over (must be unstructured)
        acd_output - the acd output

    Returns medication statements derived from NLP, or None if there are no such statements
    """
    # build insight set from ACD output
    acd_attrs: List[acd.AttributeValueAnnotation] = acd_output.attribute_values
    TrackerEntry = namedtuple("TrackerEntry", ["fhir_resource", "id_maker"])
    med_statement_tracker = {}  # key is UMLS ID, value is TrackerEntry

    if acd_attrs and acd_output.medication_ind:
        acd_medicationInds: List[acd.MedicationAnnotation] = acd_output.medication_ind
        for attr in filter_attribute_values(acd_attrs, ANNOTATION_TYPE_MEDICATION):
            medInd = _get_annotation_for_attribute(attr, acd_medicationInds)
            cui = medInd.cui

            if cui not in med_statement_tracker:
                med_statement_tracker[cui] = TrackerEntry(
                    fhir_resource=_create_minimum_medication_statement(
                        text_source.source_resource.subject, medInd
                    ),
                    id_maker=insight_id_maker(start=nlp_config.insight_id_start),
                )

            med_statement, id_maker = med_statement_tracker[cui]

            _add_insight_to_medication_statement(
                text_source,
                med_statement,
                attr,
                medInd,
                acd_output,
                next(id_maker),
                nlp_config,
            )

    if not med_statement_tracker:
        return None

    med_statements = [
        trackedStmt.fhir_resource for trackedStmt in med_statement_tracker.values()
    ]
    for med_statement in med_statements:
        append_derived_by_nlp_extension(med_statement)

    return med_statements


def _get_annotation_for_attribute(
    attr: acd.AttributeValueAnnotation,
    acd_annotations: Iterable[acd.MedicationAnnotation],
) -> acd.MedicationAnnotation:
    """Finds the annotation associated with the ACD attribute.

    The "associated" annotation is the one with the uid indicated by the attribute.
    This will be the "source" for the attribute (eg the annotation used to create the attribute).

     Args:
        attr - the ACD attribute value
        acd_annotations - the list of acd annotations to search

     Returns:
        The annotation that was used to create the attribute.
    """
    concept = attr.concept
    uid = concept.uid
    for acd_annotation in acd_annotations:
        if acd_annotation.uid == uid:
            return acd_annotation
    return None


def _add_insight_to_medication_statement(  # pylint: disable=too-many-arguments
    text_source: UnstructuredText,
    med_statement: MedicationStatement,
    attr: acd.AttributeValueAnnotation,
    medInd: acd.MedicationAnnotation,
    acd_output: acd.ContainerAnnotation,
    insight_id_string: str,
    nlp_config: NlpConfig,
):
    """Adds insight data to the medication statement"""

    insight_id_ext = create_insight_id_extension(
        insight_id_string, nlp_config.nlp_system
    )

    source = TextFragment(
        text_source=text_source,
        text_span=Span(begin=attr.begin, end=attr.end, covered_text=attr.covered_text),
    )

    if attr.insight_model_data:
        confidences = get_medication_confidences(attr.insight_model_data)
    else:
        confidences = None

    nlp_output_ext = nlp_config.create_nlp_output_extension(acd_output)

    unstructured_insight_detail = (
        create_derived_from_unstructured_insight_detail_extension(
            source=source,
            confidences=confidences,
            nlp_extensions=[nlp_output_ext] if nlp_output_ext else None,
        )
    )

    add_insight_to_meta(med_statement, insight_id_ext, unstructured_insight_detail)

    _update_codings_and_administration_info(med_statement, medInd)


def _create_minimum_medication_statement(
    subject: Reference,
    annotation: acd.MedicationAnnotation,
) -> MedicationStatement:
    """Creates a new medication statement, with minimum fields set

    The object is created with a status of 'unknown' and a
    medicationCodeableConcept with text set based on the
    drug information in the provided annotation.

    Args:
        subject: The subject of the medication statement
        annotation - the annotation to use to set the codeable concept

    Returns the new medication statement
    """
    # annotation.drug is an optional list of type List[object]
    # There's a lot of assumptions being made here based on the data that has
    # been seen in examples.
    #
    # It could also be potentially problematic to assume the first entry is the
    # one that is needed.
    #
    # So far, this approach has worked OK.
    acd_drug = _get_drug_from_annotation(annotation)

    codeable_concept = CodeableConcept.construct()

    # Someday we may change this to use drugNormalizedName instead of drugSurfaceForm
    codeable_concept.text = acd_drug.get("drugSurfaceForm")
    codeable_concept.coding = []

    return MedicationStatement.construct(
        subject=subject, medicationCodeableConcept=codeable_concept, status="unknown"
    )


def _get_drug_from_annotation(annotation: acd.MedicationAnnotation) -> dict:
    """Returns a dictionary of drug information

    Args:
       annotation - the ACD annotation to get the drug info from


    Return a dictionary
    """
    # There's a lot of assumptions being made here based on the data that has
    # been seen in examples. These are not backed by documentation:
    # For example, annotation.drug is an optional list of type List[object]
    #
    # It could also be potentially problematic to assume the first entry is the
    # one that is needed.
    try:
        return annotation.drug[0].get("name1")[0]
    except (TypeError, IndexError, AttributeError):
        logger.exception(
            "Unable to retrieve drug information for attribute %s",
            annotation.json(indent=2),
        )
        return {}


def _update_codings_and_administration_info(  # pylint: disable=too-many-branches, too-many-locals, too-many-statements
    med_statement: MedicationStatement, annotation: acd.MedicationAnnotation
):
    """
    Update the medication statement with the drug information from the ACD annotation
    """
    acd_drug = _get_drug_from_annotation(annotation)

    _add_codings_drug(acd_drug, med_statement.medicationCodeableConcept)

    if hasattr(annotation, "administration"):
        # Dosage
        dose_with_units = annotation.administration[0].get("dosageValue")
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
            frequency = annotation.administration[0].get("frequencyValue")
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
                        create_coding(insight_constants.TIMING_URL, code, display)
                    ]
                    timing_codeable_concept.text = frequency
                    timing.code = timing_codeable_concept
                    dose.timing = timing


def _add_codings_drug(
    acd_drug: Dict[Any, Any], codeable_concept: CodeableConcept
) -> None:
    """Add codes from the drug concept to the codeable_concept.

    To be used for resources created from insights - does not add an extension indicating the code is derived.
    Parameters:
        acd_drug - ACD concept for the drug
        codeable_concept - FHIR codeable concept the codes will be added to
    """
    if acd_drug.get("cui") is not None:
        # For CUIs, we do not handle comma-delimited values (have not seen that we ever have more than one value)
        append_coding(
            codeable_concept,
            insight_constants.UMLS_URL,
            acd_drug["cui"],
            acd_drug.get("drugSurfaceForm"),
        )

    if "rxNormID" in acd_drug:
        for code_id in acd_drug["rxNormID"].split(","):
            append_coding(codeable_concept, insight_constants.RXNORM_URL, code_id)


def get_medication_confidences(
    insight_model_data: InsightModelData,
) -> Optional[List[Extension]]:
    """Returns a list of confidence extensions

    The list is suitable to be added to the insight span extensions array.
     Args:
        insight_model_data - model data for the insight

     Returns:
        collection of confidence extensions, or None if no confidence info was available
    """
    # Medication has 5 types of confidence scores
    # For alpha only pulling medication.usage scores
    # Not using startedEvent scores, stoppedEvent scores, doseChangedEvent scores, adversetEvent scores
    # Per documentation in InsightModelData, most structural components of the scores is optional,
    # Handling that with exception handlers, since we expect those to be there based on experience
    confidence_list = []

    try:
        confidence_list.append(
            create_confidence_extension(
                insight_constants.CONFIDENCE_SCORE_MEDICATION_TAKEN,
                insight_model_data.medication.usage.taken_score,
            )
        )
    except AttributeError:
        pass

    try:
        confidence_list.append(
            create_confidence_extension(
                insight_constants.CONFIDENCE_SCORE_MEDICATION_CONSIDERING,
                insight_model_data.medication.usage.considering_score,
            )
        )
    except AttributeError:
        pass

    try:
        confidence_list.append(
            create_confidence_extension(
                insight_constants.CONFIDENCE_SCORE_MEDICATION_DISCUSSED,
                insight_model_data.medication.usage.discussed_score,
            )
        )
    except AttributeError:
        pass

    try:
        confidence_list.append(
            create_confidence_extension(
                insight_constants.CONFIDENCE_SCORE_MEDICATION_MEASUREMENT,
                insight_model_data.medication.usage.lab_measurement_score,
            )
        )
    except AttributeError:
        pass

    return confidence_list if confidence_list else None