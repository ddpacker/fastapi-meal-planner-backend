sast:
	bandit -r app/ -c pyproject.toml --severity-level medium --confidence-level medium -f json -o .scans/bandit-report.json