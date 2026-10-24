"""PaperPilot web API: a thin FastAPI adapter over the paperpilot engine (ADR-0005).

It translates HTTP requests into engine calls and engine exceptions into error kinds; it holds
no retrieval, prompt, citation or LLM logic (constitution Principle II).
"""
