# Weather literature and rule-to-evidence audit

The automatic precipitation extension adds verified references and implementation mappings
in [precipitation_investigator.md](precipitation_investigator.md). Its SPI and GEV procedures
are conditional model calculations; its bootstrap trend/change tests failed dependence
calibration. The historical review below describes the earlier weather build.

Reviewed 2026-11-15 UTC. This is a targeted evidence library, not an exhaustive systematic
review. Full-text availability is not the same as having read every page. The registry records
whether selected full-text sections, an abstract, or only a bibliographic record were accessed.
No paper is copied into the repository; the raw NASA data are separate from literature.

## Verified reference inventory

| Source | Access achieved | Why it belongs / implementation boundary |
| --- | --- | --- |
| [Hirsch, Slack & Smith (1982)](https://lake.wateratlas.usf.edu/upload/documents/Techniques-of-Trend-Analysis-for-Monthly-Water-Quality-Data.pdf) | Selected full-text sections | Season-stratified hydrological trend reasoning; serial correlation remains a limitation |
| [Schwarz (1978)](https://sites.stat.washington.edu/courses/stat527/s14/readings/ann_stat1978.pdf) | Full text | Model-dimension penalty; does not justify treating iid BIC as calibrated weather evidence |
| [Zhang et al. (2011)](https://www.geos.ed.ac.uk/~ghegerl/assets/WIRES_index.pdf) | Selected full-text sections | Daily extremes and loss of information through temporal/spatial averaging |
| [Wilks (2016)](https://read.nxtbook.com/ametsoc/bams/december2016/essay_thestipplingshows.html) | Selected full-text sections | Multiple-testing/field significance; descriptive discovery cannot claim local significance |
| [Nicholson (2017)](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1002/2016RG000544) | Selected full-text sections | Regional and monthly heterogeneity in eastern African rainfall; no universal rainy-season assumption |
| [Lyon & DeWitt (2012)](https://agupubs.onlinelibrary.wiley.com/doi/10.1029/2011gl050337) | Selected full-text sections | Step versus trend is a real competing explanation; this older event is not an answer key for 2020–2022 |
| [Yue et al. (2002)](https://onlinelibrary.wiley.com/doi/abs/10.1002/hyp.1095) | Publisher abstract | Trend/autocorrelation interaction and prewhitening risks; local calibration takes precedence |
| [McKee, Doesken & Kleist (1993)](https://www.droughtmanagement.info/literature/AMS_Relationship_Drought_Frequency_Duration_Time_Scales_1993.pdf) | Selected full-text sections | Drought timescale and SPI background; empirical percentiles are not called SPI |
| [Guttman (1999)](https://onlinelibrary.wiley.com/doi/10.1111/j.1752-1688.1999.tb03592.x) | Publisher abstract | SPI distribution/sample-size sensitivity; future implementation, not current capability |
| [Venema et al. (2012)](https://cp.copernicus.org/articles/8/89/2012/) | Publisher page/abstract | Homogenization needs its own validation; metadata coincidence is only a screen |
| [Funk et al. (2015)](https://www.usgs.gov/publications/climate-hazards-infrared-precipitation-stations-a-new-environmental-record-monitoring) | USGS abstract | CHIRPS as a potential longer-record comparison, with gauge lineage to review; not imported here |
| [Gelaro et al. (2017)](https://pubmed.ncbi.nlm.nih.gov/32020988/) | Bibliographic record | Verified MERRA-2 system paper identity; operational facts use NASA documentation below |
| [Reichle et al. (2017)](https://ntrs.nasa.gov/citations/82000664252800) | NASA bibliographic record | Corrected land precipitation paper identity; full publisher text was blocked |
| [Huffman et al., IMERG V07 ATBD (2023)](https://gpm.nasa.gov/sites/default/files/2023-07/IMERG_V07_ATBD_final_230712.pdf) | Selected full-text sections, especially 3.2–3.3 | Calibration transition, MERRA-2/GEOS motion inputs, gauges and quality; prevents false independence claims |

## Operational and implementation documentation

- [NASA POWER daily API](https://power.larc.nasa.gov/docs/services/api/temporal/daily/): documented endpoint, time standard, point versus regional access.
- [NASA POWER monthly API](https://power.larc.nasa.gov/docs/services/api/temporal/monthly/): monthly means and calendar interpretation.
- [NASA POWER meteorological sources](https://power.larc.nasa.gov/docs/methodology/data/sources_meteorology/): source grids, near-real-time substitutions and IMERG access. Actual response units are retained and checked.
- [NASA MERRA precipitation history](https://gmao.gsfc.nasa.gov/science-snapshots/merra-2-global-precipitation-time-series/): distinguish original MERRA from MERRA-2; do not copy the original-MERRA 2009 artifact into MERRA-2 metadata.
- [SciPy Theil–Sen](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.theilslopes.html): implementation used for slopes; primary Sen paper access was blocked.
- [Statsmodels robust covariance](https://www.statsmodels.org/stable/generated/statsmodels.regression.linear_model.RegressionResults.get_robustcov_results.html): actual HAC implementation and parameters; not a guarantee of finite-sample coverage.

The source keys and access records are in [sources.yaml](../knowledge/sources.yaml).
Threshold choices and composite procedure definitions belong to
[weather_policy_v1](weather_playbook.md), not to falsely attributed papers.

## Located but not verified enough to drive a new rule

These are research leads, not citations silently substituted into the 34 old TODOs:

| Paper | Identifier / access issue | Intended follow-up |
| --- | --- | --- |
| Mann (1945), Nonparametric Tests Against Trend | 10.2307/1907187; JSTOR returned no article text | Verify original statistic and assumptions |
| Sen (1968), Estimates of the Regression Coefficient Based on Kendall's Tau | 10.1080/01621459.1968.10480934; publisher blocked | Verify primary slope/interval derivation |
| Hamed & Rao (1998), A modified Mann-Kendall trend test for autocorrelated data | 10.1016/S0022-1694(97)00125-X; publisher blocked | Reconcile primary correction with known calibration failures |
| Pettitt (1979), A Non-Parametric Approach to the Change-Point Problem | 10.2307/2346729; full article blocked | Verify dependence assumptions and searched-break inference |
| Newey & West (1987), A Simple, Positive Semi-Definite, Heteroskedasticity and Autocorrelation Consistent Covariance Matrix | NBER t0055 working-paper page blocked; university PDF opened but text unavailable | Read primary method before replacing the existing TODO |

## Strategic corrections to the prior chats

1. Two NASA products are not automatically independent. The IMERG ATBD explicitly lists
   MERRA-2/GEOS inputs for motion estimation, and gauge information can also be shared.
2. An observed wet reversal cannot prove that a long-term drying trend does not exist.
3. A literature account of a regional drought is context, not an expected numerical result
   for every point, product, season or baseline.
4. A non-significant slope is not proof of no trend. Detectability requires a separately
   validated power calculation; current weather outputs do not claim one.
5. A large citation inventory cannot compensate for missing input values, unreviewed quality
   flags, mismatched support or failed statistical calibration.
