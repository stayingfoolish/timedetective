# Draft: Finding and Playbook classes

A proposal for `schema/core.yaml`. Shaped by what the skills return today
(`skills/result.py`: `values`, an optional `series`, or a `Refusal` with `failed` and `would_change`).

## Draft classes

```yaml
classes:
  Finding:
    attributes:
      schema_version: {required: true}
      question: {required: true}            # the user's words
      playbook: {required: true}            # playbook name
      subject: {range: SeriesRef, multivalued: true}
      claim: {range: Claim}                 # absent when the run ended in a refusal
      path: {range: Step, multivalued: true}
      refusals: {range: Refusal, multivalued: true}
      would_strengthen: {multivalued: true} # what would move the claim up a rung

  Claim:
    attributes:
      statement_type: {range: StatementType}   # trend, step, slope_change, co_movement, decoupling, none
      direction: {}
      magnitude: {range: float}
      unit: {}
      interval_low: {range: float}
      interval_high: {range: float}
      strength: {range: ClaimStrength}         # set by the critic only

  Step:
    attributes:
      procedure: {required: true}
      parameters: {}                         # JSON object
      values: {}                             # JSON object: the skill's scalar outputs
      edge_taken: {}                         # id of the playbook edge that led here
      source: {}                             # that edge's source key

  Refusal:
    attributes:
      procedure: {required: true}
      failed: {required: true}
      would_change: {required: true}

  SeriesRef:
    attributes:
      name: {required: true}
      units: {}
      cadence: {}
      source: {}
      retrieved: {range: date}

  Playbook:
    attributes:
      name: {identifier: true}
      question: {required: true}
      domain: {required: true}               # core, earth, retail
      start: {required: true}                # node id
      nodes: {range: Node, multivalued: true, inlined_as_list: true}
      edges: {range: Edge, multivalued: true, inlined_as_list: true}

  Node:
    attributes:
      id: {identifier: true}
      procedure: {}                          # absent for terminal nodes
      parameters: {}
      input: {}                              # which series in the state the procedure reads
      terminal: {range: TerminalKind}        # claim or refusal

  Edge:
    attributes:
      from: {required: true}
      to: {required: true}
      when: {range: Condition}               # absent means unconditional
      source: {required: true}

  Condition:
    attributes:
      property: {required: true}             # a key a procedure produced
      op: {range: ConditionOp}               # eq, ne, lt, le, gt, ge, is_true, is_false, refused
      value: {}
```

## Decisions needed

1. **Where claim strength is decided.** The drafts end in terminal nodes named
   `claim_descriptive`, `claim_significant`, `claim_robust`. Rule 5 says only the critic assigns
   strength, so these terminals are requests the critic checks, not assignments. Agree or change.
2. **Which procedure may support "significant".** Calibration (`docs/calibration.md`) says only
   `mann_kendall_prewhitened` holds 5% under AR(1) noise. The critic should probably refuse
   "significant" from any other test when `autocorrelated` is true.
3. **Sources for engineering utilities.** `record_summary`, `gap_audit`, `regularize` and similar
   have no defining paper. The validator currently treats them as unfinished. Options: allow
   `source: none` with a stated reason, or keep requiring a reference.
4. **Secondary sources.** 19 procedures cite the Manokhin book, which describes the method but
   is not the defining paper. Accept for now, or hold them at TODO until the primary is opened.
5. **Series in the state.** Transforms return a new series. The playbook needs a way to say
   "run the next test on the deseasonalized series" (`input:` in the draft).
6. **Thresholds on edges.** Edges such as `delta_bic > 10` or `bic_margin > 6` are judgment
   calls today. Each needs a source or an explicit "house rule" label.
