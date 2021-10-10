from abc import ABC, abstractmethod
from typing import List

from fhir.resources.resource import Resource

from text_analytics.fhir.create_bundle import BundleEntryDfn
from text_analytics.insight_source.concept_text_adjustment import AdjustedConceptRef
from text_analytics.insight_source.unstructured_text import UnstructuredText


class NLPService(ABC):
    """Base NLP service

    An NLP service has two basic functions:
    - Given unstructured text, derive new resources
    - Given a reference to a concept (possibly with adjusted text for context), use the
      text to derive additional codings.
    """

    @abstractmethod
    def derive_new_resources(
        self, notes: List[UnstructuredText]
    ) -> List[BundleEntryDfn]:
        """Invokes NLP on the unstructured text elements and derives new FHIR resources

        Args:
            notes: list of unstructured text objects to derive new resources. There is no requirement
            that all objects originated from the same source FHIR resource.
        Returns:
            list of bundle definition for the new resources
        """

    @abstractmethod
    def enrich_codeable_concepts(
        self, resource: Resource, concept_refs: List[AdjustedConceptRef]
    ) -> int:
        """Invokes NLP each concept's text, updates the concept's FHIR resource with derived codings

        The resource's meta is updated with insight detail. The insight id uses a starting value, and
        is incremented as insights are added. This means that additional care may be required to set the
        initial insight id, if another call to this method is used to derive other concepts for the same FHIR resource.
        As of 10/07/2021 there is no need for this feature since all concepts for the resource are provided in a
        single call.

        Args: resource - the resource containing the codeable concepts to derive new codings for
              concept_refs - the codeable concepts to derive new codings for (within resource)
        Returns: number of insights appended to the FHIR resource
        """
