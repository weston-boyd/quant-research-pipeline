# Contributing

Contributions that improve reliability, documentation, portability, test coverage, and research-process integrity are welcome.

## Development setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
pytest -q
```

## Contribution standards

Contributions should:

- preserve backward compatibility unless a breaking change is justified;
- include tests for new behavior;
- avoid strategy-specific or broker-specific assumptions in core modules;
- keep stage transitions and evidence decisions explicit;
- use deterministic filesystem behavior;
- provide clear error messages;
- pass the complete test suite.

## Pull requests

A pull request should explain:

1. the problem being solved;
2. the proposed behavior;
3. any compatibility considerations;
4. the tests added or changed.

Before submitting, run:

```powershell
pytest -q
```
