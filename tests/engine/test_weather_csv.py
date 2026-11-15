import hashlib

import pandas as pd
import pytest
import yaml

from timedetective.packs.earth.adapters.csv import load_csv


def test_area_mean_preserves_fixed_support_and_quality(tmp_path):
    path = tmp_path / "region.csv"
    path.write_text("date,cell_id,value,weight_km2,quality_flag\n2000-01-01,a,10,1,good\n2000-01-01,b,20,3,good\n2000-02-01,a,12,1,good\n2000-02-01,b,20,3,bad\n")
    meta = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "spatial_support": {"kind": "polygon", "id": "synthetic"}, "weights_source": "synthetic test",
            "accepted_quality_flags": ["good"]}
    path.with_suffix(".meta.yaml").write_text(yaml.safe_dump(meta))
    x = load_csv(path)
    assert x.iloc[0] == 17.5
    assert pd.isna(x.iloc[1])
    assert x.attrs["incomplete_spatial_timestamps"] == 1
    meta.pop("weights_source")
    path.with_suffix(".meta.yaml").write_text(yaml.safe_dump(meta))
    with pytest.raises(ValueError, match="weights"):
        load_csv(path)
