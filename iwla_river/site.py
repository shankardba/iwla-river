"""Build the findings site. Kept as `python -m iwla_river.site` for bin/refresh; the site lives in iwla_river/web."""

from .web.build import build

if __name__ == "__main__":
    build()
