"""india-regions: India's states and districts through time.

    >>> from india_regions import normalize_region, match_district
    >>> normalize_region("Orissa", 1998)
    'orissa'
    >>> match_district("Gurgaon", "Haryana", 2020).id
    'gurugram-district'
"""

from ._core import (  # noqa: F401
    DATA_VERSION,
    DIRECTION_WORDS,
    DISTRICT_ALIASES,
    DISTRICT_EVENTS,
    DISTRICT_SUCCESSOR,
    DISTRICTS,
    MERGES,
    PARENT,
    PARENT_BEFORE,
    RENAMED_FROM,
    STATE_ALIASES,
    STATES,
    SUCCESSOR,
    Match,
    district_by_census2011,
    district_by_lgd,
    district_candidates,
    district_for_year,
    district_periods,
    districts_in_year,
    era_state_id,
    get_district,
    get_state,
    is_valid_in_year,
    match_district,
    match_districts,
    match_state,
    merge_group,
    normalize_district_key,
    normalize_region,
    normalize_state,
    normalize_state_key,
    origin_state,
    resolve_state_for_year,
    same_territory,
    similarity,
    states_in_year,
)

__version__ = "0.1.0"
