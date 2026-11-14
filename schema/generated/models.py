from __future__ import annotations

import re
import sys
from datetime import (
    date,
    datetime,
    time
)
from decimal import Decimal
from enum import Enum
from typing import (
    Any,
    ClassVar,
    Literal,
    Optional,
    Union
)

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    SerializationInfo,
    SerializerFunctionWrapHandler,
    field_validator,
    model_serializer
)


metamodel_version = "1.12.0"
version = "None"


class ConfiguredBaseModel(BaseModel):
    model_config = ConfigDict(
        serialize_by_alias = True,
        validate_by_name = True,
        validate_assignment = True,
        validate_default = True,
        extra = "forbid",
        arbitrary_types_allowed = True,
        use_enum_values = True,
        strict = False,
    )





class LinkMLMeta(RootModel):
    root: dict[str, Any] = {}
    model_config = ConfigDict(frozen=True)

    def __getattr__(self, key:str):
        return getattr(self.root, key)

    def __getitem__(self, key:str):
        return self.root[key]

    def __setitem__(self, key:str, value):
        self.root[key] = value

    def __contains__(self, key:str) -> bool:
        return key in self.root


linkml_meta = LinkMLMeta({'default_prefix': 'td',
     'default_range': 'string',
     'description': 'The TimeDetective ontology. Source of truth for what a '
                    'procedure, a playbook and a Finding are. Instances live in '
                    'knowledge/.',
     'id': 'https://github.com/stayingfoolish/timedetective/schema/core',
     'imports': ['linkml:types'],
     'name': 'timedetective_core',
     'prefixes': {'linkml': {'prefix_prefix': 'linkml',
                             'prefix_reference': 'https://w3id.org/linkml/'},
                  'td': {'prefix_prefix': 'td',
                         'prefix_reference': 'https://github.com/stayingfoolish/timedetective/schema/core/'}},
     'source_file': 'schema/core.yaml'} )

class SkillCategory(str, Enum):
    """
    Skill type. A procedure's category is also its folder name under knowledge/procedures/, src/timedetective/skills/ and tests/skills/. Adding a value here is a schema change.
    """
    diagnostics = "diagnostics"
    """
    Measures a property of a series; changes nothing.
    """
    transforms = "transforms"
    """
    Returns a new series.
    """
    trend = "trend"
    """
    Tests for and sizes a monotonic change.
    """
    changepoint = "changepoint"
    """
    Finds when behavior changed.
    """
    relationship = "relationship"
    """
    Relates two or more series.
    """
    detectability = "detectability"
    """
    Says what this record is able to show.
    """
    robustness = "robustness"
    """
    Re-tests a result another way.
    """


class ClaimStrength(str, Enum):
    """
    The claim-strength ladder. Only the critic assigns it.
    """
    descriptive = "descriptive"
    """
    A direction and a magnitude with an interval.
    """
    significant = "significant"
    """
    Beats a stated null model after the autocorrelation check.
    """
    robust = "robust"
    """
    Survives a second method and an independent record.
    """



class Procedure(ConfiguredBaseModel):
    """
    One test, check or transform. Implemented by exactly one skill registered under the same name.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://github.com/stayingfoolish/timedetective/schema/core'})

    name: str = Field(default=..., description="""Registry name; equals the YAML file name without extension.""", json_schema_extra = { "linkml_meta": {'domain_of': ['Procedure']} })
    category: SkillCategory = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Procedure']} })
    description: Optional[str] = Field(default=None, description="""One or two lines on what it does.""", json_schema_extra = { "linkml_meta": {'domain_of': ['Procedure']} })
    requires: Optional[list[str]] = Field(default=None, description="""Properties that must hold before this procedure may run.""", json_schema_extra = { "linkml_meta": {'domain_of': ['Procedure']} })
    produces: Optional[list[str]] = Field(default=None, description="""Properties this procedure adds to the state.""", json_schema_extra = { "linkml_meta": {'domain_of': ['Procedure']} })
    source: str = Field(default=..., description="""Key into knowledge/sources.yaml for the paper that defines it. Never invented; use TODO if the real paper is not yet in hand.""", json_schema_extra = { "linkml_meta": {'domain_of': ['Procedure']} })


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
Procedure.model_rebuild()
