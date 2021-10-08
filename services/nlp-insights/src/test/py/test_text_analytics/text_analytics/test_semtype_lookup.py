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
"""Test semantic type lookup"""

import doctest
import unittest

import text_analytics.umls.semtype_lookup


class TestSemanticTypes(unittest.TestCase):
    """Test semantic type lookup

       These are tests other than documentation tests
    """

    # def test_something(self):
    #    pass


def load_tests(loader, tests, pattern):
    """Used by unittest to discover tests

       This might not work with some custom test_text_analytics runners, and doesn't
       apply any patterns to the tests or doc-tests that are
       returned. It does work with the pydev test_text_analytics runner and the unittest CLI
    """
    del loader, pattern  # not used
    tests.addTests(doctest.DocTestSuite(text_analytics.umls.semtype_lookup))
    tests.addTests(unittest.makeSuite(TestSemanticTypes))
    return tests


if __name__ == "__main__":
    unittest.main()