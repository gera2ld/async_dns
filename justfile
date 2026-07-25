default:
    @just --list

test:
    poetry run pytest -q
