"""
Defines an NLP service concrete class for working with ACD
"""

import json
import logging
from typing import List
from typing import NamedTuple

from fhir.resources.resource import Resource
from ibm_cloud_sdk_core.authenticators.iam_authenticator import IAMAuthenticator
from ibm_whcs_sdk.annotator_for_clinical_data import (
    annotator_for_clinical_data_v1 as acd,
)

from text_analytics.fhir.create_bundle import BundleEntryDfn
from text_analytics.insight_source.concept_text_adjustment import AdjustedConceptRef
from text_analytics.insight_source.unstructured_text import UnstructuredText
from text_analytics.nlp.abstract_nlp_service import NLPService
from text_analytics.nlp.acd.fhir_enrichment.insights.create_condition import (
    create_conditions_from_insights,
)
from text_analytics.nlp.acd.fhir_enrichment.insights.create_medication import (
    create_med_statements_from_insights,
)
from text_analytics.nlp.acd.fhir_enrichment.insights.update_codeable_concepts import (
    update_codeable_concepts_and_meta_with_insights,
    AcdConceptRef,
)
from text_analytics.nlp.nlp_config import ACD_NLP_CONFIG


logger = logging.getLogger(__name__)


class ACDService(NLPService):
    """The ACD NLPService uses the IBM Annotated Clinical Data product to derive insights"""

    PROCESS_TYPE_UNSTRUCTURED = "ACD Unstructured"
    PROCESS_TYPE_STRUCTURED = "ACD Structured"

    def __init__(self, json_string: str) -> None:
        """Initializes the ACD service from a json configuration string"""
        config_dict = json.loads(json_string)
        self.acd_key = config_dict["config"]["apikey"]
        self.acd_url = config_dict["config"]["endpoint"]
        self.acd_flow = config_dict["config"]["flow"]
        self.config_name = config_dict["name"]
        self.json_string = json_string
        self.nlp_config = ACD_NLP_CONFIG
        if config_dict.get("version") is not None:
            self.version = config_dict.get("version")
        else:
            self.version = "2021-01-01"

    def _run_nlp(self, text: str) -> acd.ContainerAnnotation:
        """Sends text to NLP service and returns the output"""
        service = acd.AnnotatorForClinicalDataV1(
            authenticator=IAMAuthenticator(apikey=self.acd_key), version=self.version
        )
        service.set_service_url(self.acd_url)
        logger.info("Calling ACD-%s with text %s", self.config_name, text)
        resp = service.analyze_with_flow(self.acd_flow, text)
        return resp

    def derive_new_resources(
        self, notes: List[UnstructuredText]
    ) -> List[BundleEntryDfn]:
        class ResultEntry(NamedTuple):
            """Tracks nlp input and output"""

            text_source: UnstructuredText
            nlp_output: acd.ContainerAnnotation

        nlp_responses = [ResultEntry(note, self._run_nlp(note.text)) for note in notes]

        new_resources: List[Resource] = []
        for response in nlp_responses:
            conditions = create_conditions_from_insights(
                response.text_source, response.nlp_output, self.nlp_config
            )
            if conditions:
                new_resources.extend(conditions)

            medications = create_med_statements_from_insights(
                response.text_source, response.nlp_output, self.nlp_config
            )

            if medications:
                new_resources.extend(medications)

        return [
            BundleEntryDfn(resource=resource, method="POST", url=resource.resource_type)
            for resource in new_resources
        ]

    def enrich_codeable_concepts(
        self, resource: Resource, concept_refs: List[AdjustedConceptRef]
    ) -> int:

        nlp_responses = [
            AcdConceptRef(concept_ref, self._run_nlp(concept_ref.adjusted_text))
            for concept_ref in concept_refs
        ]

        return update_codeable_concepts_and_meta_with_insights(
            resource, nlp_responses, self.nlp_config
        )
