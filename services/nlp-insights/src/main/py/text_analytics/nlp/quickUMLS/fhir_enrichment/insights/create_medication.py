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
from typing import List
from typing import Optional

from fhir.resources.codeableconcept import CodeableConcept
from fhir.resources.medicationstatement import MedicationStatement
from fhir.resources.reference import Reference

from text_analytics.fhir import fhir_object_utils
from text_analytics.insight.insight_constants import UMLS_URL, SNOMED_URL
from text_analytics.insight.insight_id import insight_id_maker
from text_analytics.insight.span import Span
from text_analytics.insight.text_fragment import TextFragment
from text_analytics.insight_source.unstructured_text import UnstructuredText
from text_analytics.nlp.nlp_config import NlpConfig, QUICK_UMLS_NLP_CONFIG
from text_analytics.nlp.nlp_reponse import NlpResponse, NlpCui
from text_analytics.umls.semtype_lookup import resource_relevant_to_any_type_names


def _add_insight_codings_to_medication_stmt(
    medication_stmt: MedicationStatement, nlp_cui: NlpCui
) -> None:
    """Adds information from the insight's concept to a MedicationStatement

    Because the entire medication statement is assumed to be derived from NLP of
    another resource, we do not mark individual codings as derived by
    NLP.

    Args:
        medication_stmt - condition to update
        nlp_cui   - concept with data to update the condition with
    """
    if medication_stmt.code is None:
        codeable_concept = CodeableConcept.construct(
            text=nlp_cui.preferred_name, coding=[]
        )
        medication_stmt.code = codeable_concept

    existing_codes_by_system = fhir_object_utils.get_existing_codes_by_system(
        medication_stmt.code.coding
    )

    if nlp_cui.cui not in existing_codes_by_system[UMLS_URL]:
        coding = fhir_object_utils.create_coding(
            UMLS_URL, nlp_cui.cui, derived_by_nlp=False
        )
        medication_stmt.code.coding.append(coding)
        existing_codes_by_system[UMLS_URL].add(nlp_cui.cui)

    if nlp_cui.snomed_ct:
        for snomed_code in nlp_cui.snomed_ct:
            if snomed_code not in existing_codes_by_system[SNOMED_URL]:
                coding = fhir_object_utils.create_coding(
                    SNOMED_URL, snomed_code, derived_by_nlp=False
                )
                medication_stmt.code.coding.append(coding)
                existing_codes_by_system[SNOMED_URL].add(snomed_code)


def _add_insight_to_medication_stmt(
    text_source: UnstructuredText,
    medication_stmt: MedicationStatement,
    nlp_cui: NlpCui,
    insight_id: str,
    nlp_config: NlpConfig,
) -> None:
    """Adds data from the insight to the MedicationStatement"""
    insight_id_ext = fhir_object_utils.create_insight_id_extension(
        insight_id, nlp_config.nlp_system
    )

    source = TextFragment(
        text_source=text_source,
        text_span=Span(
            begin=nlp_cui.begin, end=nlp_cui.end, covered_text=nlp_cui.covered_text
        ),
    )

    nlp_output_ext = nlp_config.create_nlp_output_extension(nlp_cui)

    unstructured_insight_detail = (
        fhir_object_utils.create_derived_from_unstructured_insight_detail_extension(
            source=source,
            confidences=None,
            nlp_extensions=[nlp_output_ext] if nlp_output_ext else None,
        )
    )

    fhir_object_utils.add_insight_to_meta(
        medication_stmt, insight_id_ext, unstructured_insight_detail
    )

    _add_insight_codings_to_medication_stmt(medication_stmt, nlp_cui)


def _create_minimum_medication_statement(
    subject: Reference,
    nlp_cui: NlpCui,
) -> MedicationStatement:
    """Creates a new medication statement, with minimum fields set

    The object is created with a status of 'unknown' and a
    medicationCodeableConcept with text set based on the
    drug information in the provided concept.

    Args:
        subject: The subject of the medication statement
        nlp_cui - the insight returned by NLP

    Returns the new medication statement
    """
    codeable_concept = CodeableConcept.construct(text=nlp_cui.preferred_name, coding=[])

    return MedicationStatement.construct(
        subject=subject, medicationCodeableConcept=codeable_concept, status="unknown"
    )


def create_med_statements_from_insights(
    text_source: UnstructuredText,
    nlp_response: NlpResponse,
    nlp_config: NlpConfig = QUICK_UMLS_NLP_CONFIG,
) -> Optional[List[MedicationStatement]]:
    """For the text source and NLP output, create FHIR medication statement resources

    Args:
        text_source - the resource text that NLP was run over
        nlp_response - the nlp concepts
        nlp_conifg - nlp configuration

    Returns conditions derived by NLP, or None if there are no conditions
    """
    TrackerEntry = namedtuple("TrackerEntry", ["fhir_resource", "id_maker"])
    medication_tracker = {}  # key is UMLS ID, value is TrackerEntry

    for nlp_cui in nlp_response.nlp_cuis:
        if resource_relevant_to_any_type_names(MedicationStatement, nlp_cui.types):
            if nlp_cui.cui not in medication_tracker:
                new_medication_stmt = _create_minimum_medication_statement(
                    subject=text_source.source_resource.subject, nlp_cui=nlp_cui
                )
                medication_tracker[nlp_cui.cui] = TrackerEntry(
                    fhir_resource=new_medication_stmt,
                    id_maker=insight_id_maker(start=nlp_config.insight_id_start),
                )

            med_stmt, id_maker = medication_tracker[nlp_cui.cui]

            _add_insight_to_medication_stmt(
                text_source,
                med_stmt,
                nlp_cui,
                next(id_maker),
                nlp_config,
            )

    if not medication_tracker:
        return None

    medication_stmts = [entry.fhir_resource for entry in medication_tracker.values()]

    for med_stmt in medication_stmts:
        fhir_object_utils.append_derived_by_nlp_extension(med_stmt)

    return medication_stmts