default:
    @just --list

test:
    poetry run pytest -q

publish:
    poetry build
    poetry publish
