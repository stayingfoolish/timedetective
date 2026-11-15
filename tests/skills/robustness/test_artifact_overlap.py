import generators as g

from timedetective.skills.robustness.artifact_overlap import artifact_overlap


def test_metadata_overlap_and_absence_do_not_establish_cause():
    x = g.seasonal_weather()
    assert not artifact_overlap(x, [2014]).ok
    x.attrs["known_issues"] = [{"start": "2014-06-01", "source": "test_metadata", "effect": "synthetic sensor replacement"}]
    assert len(artifact_overlap(x, [2015]).values["coincidences"]) == 1
    assert artifact_overlap(x, [2020]).values["coincidences"] == []
