"""Tag tidying: named places and real times only, no merged people (see ghostwriter/tags.py)."""

from ghostwriter import tags
from ghostwriter.models import StoryAnalysis


def test_only_named_places_are_kept():
    keep = ["Lucknow", "the Jaipur highway", "Nani's house", "St. Mary's School", "लखनऊ"]
    drop = ["corridor", "the corridor", "temple", "Temple", "room 307", "a hostel terrace"]
    assert [p for p in keep + drop if tags.is_named_place(p)] == keep


def test_only_real_times_are_kept():
    keep = ["1990s", "1942", "Diwali 2004", "the '80s", "the eighties", "childhood", "college days", "World War II"]
    drop = ["past", "the past", "night", "midnight", "December", "Diwali", "that evening"]
    assert [e for e in keep + drop if tags.is_real_time(e)] == keep


def test_clean_dedupes_but_never_merges_people(analysis):
    messy = analysis.model_copy(update={
        "people": ["grandmother", "Nani (grandmother)", "Grandmother ", "Dadi (grandmother)"],
        "places": ["Allahabad", "temple", "allahabad"],
        "eras": ["1990s", "past"],
        "keepsakes": ["brass lamp", "Brass lamp"],
    })
    clean = tags.clean(messy)
    assert clean.people == ["grandmother", "Nani (grandmother)", "Dadi (grandmother)"]
    assert clean.places == ["Allahabad"]
    assert clean.eras == ["1990s"]
    assert clean.keepsakes == ["brass lamp"]


def test_the_schema_sent_to_gemma_limits_tags():
    schema = StoryAnalysis.model_json_schema()
    assert schema["properties"]["places"]["maxItems"] == 12
    assert schema["properties"]["places"]["items"]["maxLength"] == 80
