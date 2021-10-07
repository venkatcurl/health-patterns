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
"""Low level NLP configuration"""
from typing import Any
from typing import Callable
from typing import NamedTuple
from typing import Optional

from fhir.resources.extension import Extension
from ibm_whcs_sdk.annotator_for_clinical_data import (
    annotator_for_clinical_data_v1 as acd,
)

from text_analytics import fhir_object_utils


class NlpConfig(NamedTuple):
    """NLP Configuration Settings"""

    nlp_system: str
    get_nlp_output_loc: Callable[[Any], Optional[str]]
    insight_id_start: int = 1
    
    def create_nlp_output_extension(self, nlp_output: Any) -> Optional[Extension]:
        """Creates an NLP output extension
        
           This uses the get_nlp_output_loc method to build the extension.
           If the method does not supply a location, None is returned
        """
        nlp_output_url = self.get_nlp_output_loc(nlp_output)
        if nlp_output_url:
            return fhir_object_utils.create_nlp_output_extension(nlp_output_url)

        return None


def acd_get_nlp_output_loc(nlp_output: acd.ContainerAnnotation):
    """Returns the location of ACD NLP output"""
    del nlp_output
    # TODO: save output to an external MinIO location.
    # For now, just put in a dummy String
    return "uri://path/acd-123.json"


ACD_NLP_CONFIG = NlpConfig(
    nlp_system="urn:id:COM.IBM.WH.PA.CDP.CDE/1.0.0",
    get_nlp_output_loc=acd_get_nlp_output_loc,
)


QUICK_UMLS_NLP_CONFIG = NlpConfig(
    nlp_system="urn:id:COM.IBM.QUICKUMLS/1.0.0", get_nlp_output_loc=lambda x: None
)
