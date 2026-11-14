# Proposals awaiting sign-off

Nothing here is loaded by the code or the validator. `schema/core.yaml` says the Finding and
Playbook classes are not to be added without agreement, and `scripts/validate_knowledge.py`
fails if `knowledge/playbooks/` contains files before the Playbook class exists. These drafts
are written against the 53 procedures that now exist, so they can be moved into place once agreed.

- `finding_and_playbook_schema.md`: draft LinkML classes and the decisions they need.
- `playbooks/*.yaml`: four first-wave playbooks in the draft format. Every edge has `source: TODO`.
