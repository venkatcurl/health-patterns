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

from typing import Any
from typing import Dict
from typing import List
from typing import NamedTuple
from typing import Optional
from typing import Set

from text_analytics.simple_nlp_concept import SimpleNlpConcept
from text_analytics.umls.semtype_lookup import get_names_from_type_ids


def build_concept_from_json_dict(concept_dict: Dict[str, Any]) -> SimpleNlpConcept:
    """
    Wrapper to build QuickUmlsConcept

    This uses the names found in the json response
    from QuickUMLS.

    It performs necessary conversions and transformations
    """
    types = concept_dict.get("semtypes")
    if types:
        types = get_names_from_type_ids(types)

    return SimpleNlpConcept(
        covered_text=concept_dict.get("ngram"),
        cui=concept_dict.get("cui"),
        begin=concept_dict.get("start"),
        end=concept_dict.get("end"),
        preferredName=concept_dict.get("term"),
        types=concept_dict.get("types"),
    )
