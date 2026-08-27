PYTHON ?= python3
TEAM ?= _template
SCENARIO ?= balanced_commute

.PHONY: test leaderboard serve validate evaluate watch scenarios clean

serve:
	$(PYTHON) -m webboard --port 8000 --data server_data

test:
	$(PYTHON) -m unittest discover -s tests -v

leaderboard:
	$(PYTHON) scripts/build_leaderboard.py

validate:
	$(PYTHON) scripts/validate_submission.py submissions/$(TEAM)

evaluate:
	$(PYTHON) -m traffic_sim.cli evaluate submissions/$(TEAM)/policy.py

watch:
	$(PYTHON) -m traffic_sim.cli watch submissions/$(TEAM)/policy.py --scenario $(SCENARIO)

scenarios:
	$(PYTHON) -m traffic_sim.cli scenarios

clean:
	rm -rf __pycache__ */__pycache__ */*/__pycache__ .pytest_cache
