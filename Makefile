.PHONY: help validate generate test calibrate demo

help:            ## list the tasks
	@grep -E '^[a-z]+:.*##' Makefile | sed 's/:.*## /\t/'

validate:        ## check knowledge/ YAML against schema/core.yaml
	uv run python scripts/validate_knowledge.py

generate:        ## regenerate schema/generated/ from schema/core.yaml
	uv run gen-pydantic schema/core.yaml > schema/generated/models.py

test:            ## fast tests (everything except calibration)
	uv run pytest -m "not slow"

calibrate:       ## false-positive rate on trend-free series (slow)
	uv run pytest tests/calibration -m slow

demo:            ## run the Streamlit demo
	uv run streamlit run app/main.py
