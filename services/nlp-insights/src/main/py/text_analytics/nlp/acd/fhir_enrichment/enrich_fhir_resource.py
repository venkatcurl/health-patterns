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

from typing import List
from typing import Optional

from fhir.resources.bundle import Bundle
from fhir.resources.resource import Resource
from ibm_whcs_sdk.annotator_for_clinical_data import (
    annotator_for_clinical_data_v1 as acd,
)

from text_analytics.fhir.fhir_object_utils import (
    create_transaction_bundle,
    BundleEntryDfn,
)
from text_analytics.insight_source.unstructured_text import UnstructuredText
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
from text_analytics.nlp.nlp_config import NlpConfig, ACD_NLP_CONFIG


def enrich_resource_codeable_concepts(
    concept_insights: List[AcdConceptRef],
    fhir_resource: Resource,
    nlp_config: NlpConfig = ACD_NLP_CONFIG,
) -> Optional[Bundle]:
    """Creates a bundle containing the fhir resource that includes additional codeings

    Args:
        concept_insights - collection of bindings between codeable concepts to enrich
                           and ACD/NLP analysis of those insights
        fhir_resource - the resource that contains the codeable concepts referenced by
                        the concept insights

    Returns: Bundle with single enriched resource, or None if the resource was not
             enriched
    """
    num_updates = update_codeable_concepts_and_meta_with_insights(
        fhir_resource, concept_insights, nlp_config
    )

    if num_updates > 0:
        return create_transaction_bundle(
            [
                BundleEntryDfn(
                    resource=fhir_resource,
                    method="PUT",
                    url=fhir_resource.resource_type + "/" + str(fhir_resource.id),
                )
            ]
        )

    return None


def create_new_resources_from_insights(
    text_source: UnstructuredText,
    insights: acd.ContainerAnnotation,
    nlp_config: NlpConfig = ACD_NLP_CONFIG,
) -> Optional[Bundle]:
    """Creates a bundle of new (derived) resources from ACD insights

       This is called when a source resource contains unstructured text, such as
       a diagnostic report or a document reference. NLP is run against the
       unstructured text, and new resources are created. The source resource
       is not modified.

    Args:
        source resource - the resource that caused the insights to be created
        insights - response from ACD for free text in the resource
        nlp_config - nlp configuration

    Returns a bundle of derived resources, or None if no resources were derived
    """
    conditions = create_conditions_from_insights(text_source, insights, nlp_config)
    med_statements = create_med_statements_from_insights(text_source, insights, nlp_config)

    if not conditions and not med_statements:
        return None

    bundle_entries = []

    if conditions:
        for condition in conditions:
            bundle_entries.append(
                BundleEntryDfn(
                    resource=condition, method="POST", url=condition.resource_type
                )
            )

    if med_statements:
        for med_statement in med_statements:
            bundle_entries.append(
                BundleEntryDfn(
                    resource=med_statement,
                    method="POST",
                    url=med_statement.resource_type,
                )
            )

    return create_transaction_bundle(bundle_entries)