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



class Finding(ConfiguredBaseModel):
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://github.com/stayingfoolish/timedetective/schema/core'})

    schema_version: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Finding']} })
    question: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Finding', 'Playbook']} })
    playbook: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Finding']} })
    subject: Optional[list[SeriesRef]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Finding']} })
    claim: Optional[Claim] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Finding']} })
    path: Optional[list[Step]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Finding']} })
    refusals: Optional[list[FindingRefusal]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Finding']} })
    would_strengthen: Optional[list[str]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Finding']} })


class Claim(ConfiguredBaseModel):
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://github.com/stayingfoolish/timedetective/schema/core'})

    statement_type: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Claim']} })
    statement: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Claim']} })
    strength: ClaimStrength = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Claim']} })


class SeriesRef(ConfiguredBaseModel):
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://github.com/stayingfoolish/timedetective/schema/core'})

    name: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['SeriesRef', 'Playbook', 'Dataset', 'Procedure']} })
    units: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['SeriesRef', 'Dataset']} })
    cadence: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['SeriesRef', 'Dataset']} })
    source: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['SeriesRef',
                       'Step',
                       'Edge',
                       'Dataset',
                       'KnownIssue',
                       'Procedure']} })
    retrieved: date = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['SeriesRef']} })
    metadata_json: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['SeriesRef']} })


class Step(ConfiguredBaseModel):
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://github.com/stayingfoolish/timedetective/schema/core'})

    node: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Step']} })
    procedure: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Step', 'FindingRefusal', 'Node']} })
    parameters_json: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Step', 'Node']} })
    values_json: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Step']} })
    source: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['SeriesRef',
                       'Step',
                       'Edge',
                       'Dataset',
                       'KnownIssue',
                       'Procedure']} })
    edge_taken: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Step']} })
    edge_source: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Step']} })


class FindingRefusal(ConfiguredBaseModel):
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://github.com/stayingfoolish/timedetective/schema/core'})

    procedure: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Step', 'FindingRefusal', 'Node']} })
    failed: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['FindingRefusal']} })
    would_change: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['FindingRefusal']} })


class Playbook(ConfiguredBaseModel):
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://github.com/stayingfoolish/timedetective/schema/core'})

    name: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['SeriesRef', 'Playbook', 'Dataset', 'Procedure']} })
    question: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Finding', 'Playbook']} })
    domain: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Playbook', 'Edge']} })
    start: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Playbook', 'KnownIssue']} })
    nodes: list[Node] = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Playbook']} })
    edges: list[Edge] = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Playbook']} })


class Node(ConfiguredBaseModel):
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://github.com/stayingfoolish/timedetective/schema/core'})

    id: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Node', 'Edge']} })
    procedure: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Step', 'FindingRefusal', 'Node']} })
    parameters_json: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Step', 'Node']} })
    input: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Node']} })
    terminal: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Node']} })


class Edge(ConfiguredBaseModel):
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://github.com/stayingfoolish/timedetective/schema/core'})

    id: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Node', 'Edge']} })
    origin: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Edge']} })
    target: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Edge']} })
    outcome: str = Field(default=..., description="""ok, refused, or always; exactly one edge must match.""", json_schema_extra = { "linkml_meta": {'domain_of': ['Edge']} })
    domain: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Playbook', 'Edge']} })
    source: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['SeriesRef',
                       'Step',
                       'Edge',
                       'Dataset',
                       'KnownIssue',
                       'Procedure']} })


class Dataset(ConfiguredBaseModel):
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://github.com/stayingfoolish/timedetective/schema/core'})

    name: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['SeriesRef', 'Playbook', 'Dataset', 'Procedure']} })
    pack: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Dataset']} })
    title: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Dataset']} })
    plain_definition: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Dataset']} })
    variable: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Dataset']} })
    units: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['SeriesRef', 'Dataset']} })
    provider: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Dataset']} })
    product_id: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Dataset']} })
    cadence: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['SeriesRef', 'Dataset']} })
    analysis_cadence: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Dataset']} })
    record_start: date = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Dataset']} })
    spatial_resolution: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Dataset']} })
    known_issues: Optional[list[KnownIssue]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Dataset']} })
    companions: Optional[list[str]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Dataset']} })
    source: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['SeriesRef',
                       'Step',
                       'Edge',
                       'Dataset',
                       'KnownIssue',
                       'Procedure']} })


class KnownIssue(ConfiguredBaseModel):
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://github.com/stayingfoolish/timedetective/schema/core'})

    kind: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['KnownIssue']} })
    start: Optional[date] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Playbook', 'KnownIssue']} })
    end: Optional[date] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['KnownIssue']} })
    effect: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['KnownIssue']} })
    handling: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['KnownIssue']} })
    source: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['SeriesRef',
                       'Step',
                       'Edge',
                       'Dataset',
                       'KnownIssue',
                       'Procedure']} })


class Procedure(ConfiguredBaseModel):
    """
    One test, check or transform. Implemented by exactly one skill registered under the same name.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://github.com/stayingfoolish/timedetective/schema/core'})

    name: str = Field(default=..., description="""Registry name; equals the YAML file name without extension.""", json_schema_extra = { "linkml_meta": {'domain_of': ['SeriesRef', 'Playbook', 'Dataset', 'Procedure']} })
    category: SkillCategory = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Procedure']} })
    description: Optional[str] = Field(default=None, description="""One or two lines on what it does.""", json_schema_extra = { "linkml_meta": {'domain_of': ['Procedure']} })
    requires: Optional[list[str]] = Field(default=None, description="""Properties that must hold before this procedure may run.""", json_schema_extra = { "linkml_meta": {'domain_of': ['Procedure']} })
    produces: Optional[list[str]] = Field(default=None, description="""Properties this procedure adds to the state.""", json_schema_extra = { "linkml_meta": {'domain_of': ['Procedure']} })
    source: str = Field(default=..., description="""Key into knowledge/sources.yaml for the paper that defines it. Never invented; use TODO if the real paper is not yet in hand.""", json_schema_extra = { "linkml_meta": {'domain_of': ['SeriesRef',
                       'Step',
                       'Edge',
                       'Dataset',
                       'KnownIssue',
                       'Procedure']} })


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
Finding.model_rebuild()
Claim.model_rebuild()
SeriesRef.model_rebuild()
Step.model_rebuild()
FindingRefusal.model_rebuild()
Playbook.model_rebuild()
Node.model_rebuild()
Edge.model_rebuild()
Dataset.model_rebuild()
KnownIssue.model_rebuild()
Procedure.model_rebuild()
