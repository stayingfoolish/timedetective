# Literature extractor (not built)

Turns applied papers into evidence for playbook edges, procedure sources and dataset cards.
Only the inputs exist so far:

- `vocabulary.yaml`: maps the many names papers use for a method to one registry name,
  with the Manokhin book as the reference vocabulary.
- `corpus_candidates.yaml`: open-access candidate papers by cluster. None has been read yet.

## Intent of this step

Before any extraction runs, fix the two things that would otherwise corrupt it:

1. **What counts as the same method.** Without one vocabulary, "modified Mann-Kendall" in
   five papers becomes five edges, or three different tests become one.
2. **What we read.** A corpus drawn from one variable or one community would encode that
   community's habits as if they were general rules.

## Corpus rules

- Open access only. Record the licence and the version read.
- Each cluster mixes applied papers (what analysts do) with comparison papers (what works).
- A paper enters `knowledge/sources.yaml` only after it has been opened and read.

## Pipeline (planned)

1. Extract an ordered trace of steps per paper; every step carries the quoted sentence.
2. Normalize each step through `vocabulary.yaml`; unmatched steps are recorded as unmapped.
3. Aggregate identical transitions across papers into candidate edges with their support count.
4. Gate: quote exists in the paper, schema is valid, calibration does not get worse, a person signs off.
5. Write accepted edges to `knowledge/playbooks/`, sources to `knowledge/sources.yaml`,
   dataset facts to dataset cards, and unregistered methods to the procedure backlog.
