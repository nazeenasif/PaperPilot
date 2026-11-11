"""Fixtures for the evaluation harness tests. The root `tests/conftest.py` fixtures (temporary
library, fake embedder, scripted LLM) apply here too. Nothing here can reach the model, the
provider or the Hugging Face hub.

No __init__.py in tests/evaluation: as a package it would be imported as "evaluation" and shadow
the real package under test (as tests/api)."""
