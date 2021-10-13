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

from collections import OrderedDict
from enum import Enum
import logging
from typing import Dict, Type
from typing import Generator
from typing import List
from typing import NamedTuple
from typing import Union

from fhir.resources.resource import Resource
from ibm_whcs_sdk.annotator_for_clinical_data import (
    annotator_for_clinical_data_v1 as acd,
)

from text_analytics.insight_source.fields_of_interest import CodeableConceptRefType


AnnotationContextType = Union[Type[Resource], CodeableConceptRefType]


AttrSourceConcept = Union[
    acd.Concept,
    acd.SymptomDisease,
    acd.MedicationAnnotation,
]


class AttrSourcePropName(Enum):
    """Possible values for fields in an acd response that may contain the source CUI"""

    CONCEPTS = "concepts"
    SYMPTOM_DISEASE_IND = "symptom_disease_ind"
    MEDICATION_IND = "medication_ind"


class AcdAttrSourceLoc(NamedTuple):
    """Binds an attribute name/type to the fields to search for the source CUI(s)"""

    attr_name: str
    source_prop_names: List[AttrSourcePropName]


AttributeNameAndSourceMap = Dict[AnnotationContextType, List[AcdAttrSourceLoc]]


logger = logging.getLogger(__name__)


class AttributeWithCuiSources(NamedTuple):
    """Binds an attribute with it's source CUIS"""

    attr: acd.AttributeValueAnnotation
    sources: OrderedDict[AttrSourcePropName, AttrSourceConcept]


def _create_attribute_sources(
    attr: acd.AttributeValueAnnotation,
    container: acd.ContainerAnnotation,
    source_prop_names: List[AttrSourcePropName],
) -> AttributeWithCuiSources:
    """For the given attribute value annotation, find the source CUI(s) for the annotation.

    Args: attr - the attribute value annotation
          acd_response - the complete response
          source_prop_names - properties in the container to look for the cuis
    Returns: attribute and source CUI(s)
    """

    result: OrderedDict[AttrSourcePropName, AttrSourceConcept] = OrderedDict()
    uid = attr.concept.uid

    for prop_name in source_prop_names:
        if hasattr(container, prop_name.value) and getattr(container, prop_name.value):
            for cui_obj in getattr(container, prop_name.value):
                if hasattr(cui_obj, "uid") and getattr(cui_obj, "uid") == uid:
                    result[prop_name] = cui_obj

    return AttributeWithCuiSources(attr=attr, sources=result)


def get_attribute_sources(
    container: acd.ContainerAnnotation,
    context: AnnotationContextType,
    ann_names_map: AttributeNameAndSourceMap,
) -> Generator[AttributeWithCuiSources, None, None]:
    """Generator to filter attributes by name of attribute

    Args:
        attribute_values - list of attribute value annotations from ACD
        values - allowed names for returned attributes
        ann_type_map - mapping of context to list of attribute names to search for
    """

    if not container.attribute_values:
        return

    attribute_values: List[acd.AttributeValueAnnotation] = container.attribute_values
    annotation_locs: List[AcdAttrSourceLoc] = ann_names_map.get(context, [])

    for attr in attribute_values:
        for loc in annotation_locs:
            if attr.name == loc.attr_name:
                sources = _create_attribute_sources(
                    attr, container, loc.source_prop_names
                )
                logger.debug(
                    "Yielding attribute %s for examination of sources %s",
                    attr.name,
                    sources,
                )
                yield sources
