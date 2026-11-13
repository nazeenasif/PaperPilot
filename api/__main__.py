"""`python -m api`: serve the API on 127.0.0.1:8000 only (never all interfaces, FR-002a)."""

import uvicorn

HOST = "127.0.0.1"
PORT = 8000


def main() -> None:
    """Run uvicorn bound to the loopback address."""
    uvicorn.run("api.main:app", host=HOST, port=PORT)


if __name__ == "__main__":
    main()
