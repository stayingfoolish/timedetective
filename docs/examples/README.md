# Real-data evidence runs

These are computed from the committed NASA response, not invented or copied from papers.

- `weather_point_finding.json` / `.md`: first retained run, before reference snapshots were embedded.
- `weather_point_finding_v2.json` / `.md`: current report with reference snapshots and graph/source fingerprints.

Both refer to 3°N, 42°E—not the full Horn of Africa. Neither establishes the expected regional
drought narrative. The two precipitation products disagree on seasonal anomaly signs.
The input response was archived without modifications and is checksum-verified by the adapter.

Independent arithmetic directly summing the raw JSON (without the new statistical code)
confirmed these values, in mm per season:

| Product | Season | 2000–2019 mean | 2020–2022 mean | Difference | 2023 total |
| --- | --- | ---: | ---: | ---: | ---: |
| POWER PRECTOTCORR | MAM | 190.6095 | 270.7867 | +80.1772 | 266.71 |
| POWER IMERG_PRECTOT | MAM | 193.2380 | 175.9033 | −17.3347 | 339.97 |
| POWER PRECTOTCORR | OND | 208.5755 | 213.1700 | +4.5945 | 699.32 |
| POWER IMERG_PRECTOT | OND | 224.8945 | 111.5167 | −113.3778 | 606.98 |

The event window includes all MAM and OND seasons in 2020–2022, not a preselected set of
only failed seasons. A positive 2023 anomaly does not establish absence of an underlying trend.
Investigate footprint, quality, correction and product-version differences before making
regional climate statements from this disagreement.
