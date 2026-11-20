PY ?= python
export PYTHONPATH := src
export MPLBACKEND := Agg

.PHONY: test demo eval figures check

test:
	$(PY) -m unittest discover -s tests -v

demo:
	$(PY) -m protocol_diff.cli explain --variant clearance_persist

eval:
	$(PY) -m protocol_diff.cli bench --out results/results.json

figures:
	$(PY) scripts/make_figures.py

check:
	$(PY) scripts/check_repro.py
