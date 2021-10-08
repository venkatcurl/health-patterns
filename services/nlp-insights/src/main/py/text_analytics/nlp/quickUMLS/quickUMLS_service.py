"""
Defines an NLP service concrete class for QuickUMLS NLP.

"""
import json
import logging
from typing import List
from typing import NamedTuple

from fhir.resources.resource import Resource
import requests

from text_analytics.fhir.fhir_object_utils import BundleEntryDfn
from text_analytics.insight_source.concept_text_adjustment import AdjustedConceptRef
from text_analytics.insight_source.unstructured_text import UnstructuredText
from text_analytics.nlp.abstract_nlp_service import NLPService
from text_analytics.nlp.nlp_config import QUICK_UMLS_NLP_CONFIG
from text_analytics.nlp.nlp_reponse import NlpResponse, NlpCui
from text_analytics.nlp.quickUMLS.fhir_enrichment.insights.create_condition import (
    create_conditions_from_insights,
)
from text_analytics.nlp.quickUMLS.fhir_enrichment.insights.create_medication import (
    create_med_statements_from_insights,
)
from text_analytics.nlp.quickUMLS.fhir_enrichment.insights.update_codeable_concepts import (
    update_codeable_concepts_and_meta_with_insights,
    NlpConceptRef,
)
from text_analytics.umls.semtype_lookup import get_names_from_type_ids


logger = logging.getLogger(__name__)


class QuickUMLSService(NLPService):
    """
    The QuickUMLS Service is able to detect UMLS cuis in unstructured text.
    """

    def __init__(self, json_string: str) -> None:
        config_dict = json.loads(json_string)
        self.quick_umls_url = config_dict["config"]["endpoint"]
        self.json_string = json_string
        self.config_name = config_dict["name"]
        self.nlp_config = QUICK_UMLS_NLP_CONFIG

    def _run_nlp(self, text: str) -> NlpResponse:
        logger.info("Calling QUICKUMLS-%s with text %s", self.config_name, text)

        request_body = {"text": text}
        resp = requests.post(self.quick_umls_url, json=request_body)
        concepts = json.loads(resp.text)
        nlp_cuis = nlp_cuis = [
            NlpCui(
                cui=concept["cui"],
                covered_text=concept["ngram"] if "ngram" in concept else "",
                begin=concept["start"] if "start" in concept else 0,
                end=concept["end"] if "end" in concept else 0,
                preferred_name=concept["term"] if "term" in concept else "",
                types=(
                    get_names_from_type_ids(concept["semtypes"])
                    if "semtypes" in concept
                    else set()
                ),
                snomed_ct=concept["snomed_ct"] if "snomed_ct" in concept else None,
            )
            for concept in concepts
            if "cui" in concept
        ]
        return NlpResponse(nlp_cuis=nlp_cuis)

    def derive_new_resources(
        self, notes: List[UnstructuredText]
    ) -> List[BundleEntryDfn]:
        class ResultEntry(NamedTuple):
            """Tracks nlp input and output"""

            text_source: UnstructuredText
            nlp_output: NlpResponse

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
            NlpConceptRef(concept_ref, self._run_nlp(concept_ref.adjusted_text))
            for concept_ref in concept_refs
        ]

        return update_codeable_concepts_and_meta_with_insights(
            resource, nlp_responses, self.nlp_config
        )