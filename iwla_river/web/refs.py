"""Every source the site cites: data, methods and the science behind each reading of a result.

A finding lists the keys it relies on in Page.refs; the build fails on an unknown key, and a test checks that
every finding cites something. Data sources carry the date they were accessed for this site.
"""

from __future__ import annotations

ACCESSED = "2026-10"

# kind: "data" (where numbers come from), "method" (how they were worked out), "science" (what they mean)
REFS: dict[str, dict] = {
    # ---- data ----
    "cwh": dict(kind="data", short="Izaak Walton League, Clean Water Hub",
                full="Izaak Walton League of America. Clean Water Hub: Save Our Streams biological, chemical, Salt Watch and "
                     "Nitrate Watch surveys. Snapshot downloaded through the Hub's public API.",
                url="https://www.cleanwaterhub.org/"),
    "sos": dict(kind="data", short="Izaak Walton League, Save Our Streams protocols",
                full="Izaak Walton League of America. Save Our Streams stream monitoring: biological survey method, "
                     "macroinvertebrate identification and stream health score.",
                url="https://www.iwla.org/save-our-streams"),
    "streamcat": dict(kind="data", short="Hill et al. 2016 (EPA StreamCat)",
                      full="Hill, R.A., Weber, M.H., Leibowitz, S.G., Olsen, A.R. and Thornbrugh, D.J. (2016). The Stream-Catchment "
                           "(StreamCat) Dataset: a database of watershed metrics for the conterminous United States. Journal of the "
                           "American Water Resources Association 52(1): 120–128.",
                      doi="10.1111/1752-1688.12372"),
    "nlcd2019": dict(kind="data", short="Dewitz 2021 (NLCD 2019)",
                     full="Dewitz, J. (2021). National Land Cover Database (NLCD) 2019 Products. U.S. Geological Survey data release.",
                     doi="10.5066/P9KZCM54"),
    "annual-nlcd": dict(kind="data", short="USGS Annual NLCD Collection 1.2",
                        full="U.S. Geological Survey. Annual National Land Cover Database (NLCD) Collection 1.2 Science Products: "
                             "fractional impervious surface, conterminous United States, 1985–2025 (30 m). Files from ScienceBase "
                             "item 697b907eb66b0197c3043c9f; 21 of the 41 years used here.",
                        url="https://www.sciencebase.gov/catalog/item/697b907eb66b0197c3043c9f"),
    "nhdplus": dict(kind="data", short="McKay et al. 2012 (NHDPlus V2)",
                    full="McKay, L., Bondelid, T., Dewald, T., Johnston, J., Moore, R. and Rea, A. (2012). NHDPlus Version 2: User "
                         "Guide. U.S. Environmental Protection Agency and U.S. Geological Survey.",
                    url="https://www.epa.gov/waterdata/nhdplus-national-hydrography-dataset-plus"),
    "nldi": dict(kind="data", short="USGS Network-Linked Data Index",
                 full="U.S. Geological Survey. Hydro Network-Linked Data Index (NLDI) web service: the NHDPlus stream segment at a point.",
                 url="https://waterdata.usgs.gov/blog/nldi-intro/"),
    "wbd": dict(kind="data", short="USGS and NRCS 2013 (Watershed Boundary Dataset)",
                full="U.S. Geological Survey and U.S. Department of Agriculture, Natural Resources Conservation Service (2013). "
                     "Federal Standards and Procedures for the National Watershed Boundary Dataset (WBD), 4th edition. USGS "
                     "Techniques and Methods 11–A3. Boundaries from the USGS WBD map service.",
                doi="10.3133/tm11A3"),
    "openmeteo": dict(kind="data", short="Zippenfenig 2023 (Open-Meteo)",
                      full="Zippenfenig, P. (2023). Open-Meteo.com Weather API. Zenodo. Historical weather from its archive "
                           "(ERA5-based reanalysis, see Hersbach et al. 2020).",
                      doi="10.5281/zenodo.7970649"),
    "era5": dict(kind="data", short="Hersbach et al. 2020 (ERA5)",
                 full="Hersbach, H. et al. (2020). The ERA5 global reanalysis. Quarterly Journal of the Royal Meteorological "
                      "Society 146(730): 1999–2049.",
                 doi="10.1002/qj.3803"),
    "census-boundaries": dict(kind="data", short="US Census Bureau cartographic boundaries",
                              full="U.S. Census Bureau. Cartographic Boundary Files: states.",
                              url="https://www.census.gov/geographies/mapping-files/time-series/geo/cartographic-boundary.html"),
    "osm": dict(kind="data", short="OpenStreetMap contributors",
                full="OpenStreetMap contributors. Named rivers, creeks, lakes, bays and peaks (Open Database License), read from "
                     "Protomaps vector map files.",
                url="https://www.openstreetmap.org/copyright"),
    "terrain-tiles": dict(kind="data", short="AWS Terrain Tiles",
                          full="Mapzen / Amazon Web Services. Terrain Tiles on the Registry of Open Data on AWS (elevation, "
                               "terrarium encoding), used for shaded relief and river height profiles.",
                          url="https://registry.opendata.aws/terrain-tiles/"),
    "wqp": dict(kind="data", short="Read et al. 2017 (Water Quality Portal)",
                full="Read, E.K. et al. (2017). Water quality data for national-scale aquatic research: the Water Quality Portal. "
                     "Water Resources Research 53(2): 1735–1745. Agency chloride results downloaded from waterqualitydata.us.",
                doi="10.1002/2016WR019993"),
    "nwis": dict(kind="data", short="USGS National Water Information System",
                 full="U.S. Geological Survey (2016). National Water Information System data available on the World Wide Web "
                      "(USGS Water Data for the Nation): daily streamflow, specific conductance and water temperature.",
                 doi="10.5066/F7P55KJN"),
    "echo": dict(kind="data", short="EPA ECHO Exporter",
                 full="U.S. Environmental Protection Agency. Enforcement and Compliance History Online (ECHO) Exporter: Clean "
                      "Water Act permits, compliance status and effluent exceedances by facility.",
                 url="https://echo.epa.gov/tools/data-downloads"),
    "attains": dict(kind="data", short="EPA ATTAINS",
                    full="U.S. Environmental Protection Agency. ATTAINS: state assessments of impaired waters under Clean Water "
                         "Act sections 303(d) and 305(b). National geospatial snapshot of January 2025.",
                    url="https://www.epa.gov/waterdata/attains"),
    "usmin": dict(kind="data", short="USGS USMIN mine features",
                  full="Horton, J.D. and San Juan, C.A. (2016, consolidated release 2025). Prospect- and mine-related features "
                       "from U.S. Geological Survey 7.5- and 15-minute topographic quadrangle maps of the United States. U.S. "
                       "Geological Survey data release; consolidated features from ScienceBase item 64dfc0efd34e5f6cd553c265.",
                  doi="10.5066/F78W3CHG"),
    "acs": dict(kind="data", short="US Census Bureau, ACS 2020–2024",
                full="U.S. Census Bureau. American Community Survey 5-year estimates, 2020–2024: population, median household "
                     "income and poverty by census tract (summary files).",
                url="https://www.census.gov/programs-surveys/acs"),
    "nrsa": dict(kind="data", short="EPA National Rivers and Streams Assessment",
                 full="U.S. Environmental Protection Agency. National Rivers and Streams Assessment (2008–09, 2013–14, 2018–19 "
                      "and later surveys): benthic macroinvertebrate multimetric index and condition class.",
                 url="https://www.epa.gov/national-aquatic-resource-surveys/nrsa"),
    "mbss": dict(kind="data", short="Maryland DNR, Maryland Biological Stream Survey",
                 full="Maryland Department of Natural Resources. Maryland Biological Stream Survey (MBSS), 1995–2024: benthic "
                      "index of biotic integrity, public map layers.",
                 url="https://dnr.maryland.gov/streams/Pages/mbss.aspx"),
    "stream-waders": dict(kind="data", short="Maryland DNR, Stream Waders",
                          full="Maryland Department of Natural Resources. Stream Waders volunteer benthic monitoring program.",
                          url="https://dnr.maryland.gov/streams/Pages/streamwaders.aspx"),
    "restoration": dict(kind="data", short="County and state restoration project records",
                        full="Completed stream restoration projects with a place and year: Fairfax County stormwater capital "
                             "projects, Montgomery County Department of Environmental Protection projects, the Maryland Chesapeake "
                             "and Atlantic Coastal Bays Trust Fund, and the American Rivers Dam Removal Database (figshare).",
                        doi="10.6084/m9.figshare.5234068"),
    "epa319": dict(kind="data", short="EPA Grants Reporting and Tracking System (Section 319)",
                   full="U.S. Environmental Protection Agency. Grants Reporting and Tracking System (GRTS): Clean Water Act "
                        "Section 319 nonpoint-source projects by 12-digit watershed, and Nonpoint Source Success Stories.",
                   url="https://www.epa.gov/nps/grants-reporting-and-tracking-system-grts"),
    "epa-chloride": dict(kind="data", short="US EPA 1988 (chloride criteria)",
                         full="U.S. Environmental Protection Agency (1988). Ambient Water Quality Criteria for Chloride — 1988. "
                              "EPA 440/5-88-001. Chronic criterion 230 mg/L.",
                         url="https://www.epa.gov/wqc/national-recommended-water-quality-criteria-aquatic-life-criteria-table"),
    "epa-nitrate": dict(kind="data", short="US EPA nitrate drinking-water standard",
                        full="U.S. Environmental Protection Agency. National Primary Drinking Water Regulations, 40 CFR 141.62: "
                             "nitrate maximum contaminant level 10 mg/L as nitrogen.",
                        url="https://www.epa.gov/ground-water-and-drinking-water/national-primary-drinking-water-regulations"),

    "va-deq-partners": dict(kind="data", short="Virginia DEQ, monitoring partners",
                            full="Virginia Department of Environmental Quality. Monitoring Partner Resources: volunteer and partner "
                                 "data solicited for potential use in the state's water quality assessment process (data levels I–III).",
                            url="https://www.deq.virginia.gov/water/water-quality/monitoring/monitoring-partner-resources"),

    # ---- methods ----
    "wilcoxon1945": dict(kind="method", short="Wilcoxon 1945",
                         full="Wilcoxon, F. (1945). Individual comparisons by ranking methods. Biometrics Bulletin 1(6): 80–83.",
                         doi="10.2307/3001968"),
    "white1980": dict(kind="method", short="White 1980 (robust standard errors)",
                      full="White, H. (1980). A heteroskedasticity-consistent covariance matrix estimator and a direct test for "
                           "heteroskedasticity. Econometrica 48(4): 817–838.", doi="10.2307/1912934"),
    "cameron-miller2015": dict(kind="method", short="Cameron and Miller 2015 (clustered errors)",
                               full="Cameron, A.C. and Miller, D.L. (2015). A practitioner's guide to cluster-robust inference. "
                                    "Journal of Human Resources 50(2): 317–372.", doi="10.3368/jhr.50.2.317"),
    "mann": dict(kind="method", short="Mann 1945",
                 full="Mann, H.B. (1945). Nonparametric tests against trend. Econometrica 13(3): 245–259.", doi="10.2307/1907187"),
    "hirsch1982": dict(kind="method", short="Hirsch, Slack and Smith 1982",
                       full="Hirsch, R.M., Slack, J.R. and Smith, R.A. (1982). Techniques of trend analysis for monthly water "
                            "quality data. Water Resources Research 18(1): 107–121.", doi="10.1029/WR018i001p00107"),
    "sen1968": dict(kind="method", short="Sen 1968",
                    full="Sen, P.K. (1968). Estimates of the regression coefficient based on Kendall's tau. Journal of the American "
                         "Statistical Association 63(324): 1379–1389.", doi="10.1080/01621459.1968.10480934"),
    "bh1995": dict(kind="method", short="Benjamini and Hochberg 1995",
                   full="Benjamini, Y. and Hochberg, Y. (1995). Controlling the false discovery rate: a practical and powerful "
                        "approach to multiple testing. Journal of the Royal Statistical Society B 57(1): 289–300.",
                   doi="10.1111/j.2517-6161.1995.tb02031.x"),
    "good2005": dict(kind="method", short="Good 2005 (permutation tests)",
                     full="Good, P.I. (2005). Permutation, Parametric, and Bootstrap Tests of Hypotheses, 3rd edition. Springer.",
                     doi="10.1007/b138696"),
    "friedman2001": dict(kind="method", short="Friedman 2001",
                         full="Friedman, J.H. (2001). Greedy function approximation: a gradient boosting machine. Annals of "
                              "Statistics 29(5): 1189–1232.", doi="10.1214/aos/1013203451"),
    "sklearn": dict(kind="method", short="Pedregosa et al. 2011 (scikit-learn)",
                    full="Pedregosa, F. et al. (2011). Scikit-learn: machine learning in Python. Journal of Machine Learning "
                         "Research 12: 2825–2830.", url="https://jmlr.org/papers/v12/pedregosa11a.html"),
    "breiman2001": dict(kind="method", short="Breiman 2001 (permutation importance)",
                        full="Breiman, L. (2001). Random forests. Machine Learning 45: 5–32.", doi="10.1023/A:1010933404324"),
    "lightgbm": dict(kind="method", short="Ke et al. 2017 (LightGBM)",
                     full="Ke, G. et al. (2017). LightGBM: a highly efficient gradient boosting decision tree. Advances in Neural "
                          "Information Processing Systems 30: 3146–3154.",
                     url="https://papers.nips.cc/paper/6907-lightgbm-a-highly-efficient-gradient-boosting-decision-tree"),
    "treeshap": dict(kind="method", short="Lundberg et al. 2020 (TreeSHAP)",
                     full="Lundberg, S.M. et al. (2020). From local explanations to global understanding with explainable AI for "
                          "trees. Nature Machine Intelligence 2: 56–67.", doi="10.1038/s42256-019-0138-9"),
    "iforest": dict(kind="method", short="Liu, Ting and Zhou 2008 (Isolation Forest)",
                    full="Liu, F.T., Ting, K.M. and Zhou, Z.-H. (2008). Isolation forest. Proceedings of the 8th IEEE International "
                         "Conference on Data Mining: 413–422.", doi="10.1109/ICDM.2008.17"),
    "getis-ord": dict(kind="method", short="Ord and Getis 1995 (Gi*)",
                      full="Ord, J.K. and Getis, A. (1995). Local spatial autocorrelation statistics: distributional issues and an "
                           "application. Geographical Analysis 27(4): 286–306.", doi="10.1111/j.1538-4632.1995.tb00912.x"),
    "mann-whitney": dict(kind="method", short="Mann and Whitney 1947",
                         full="Mann, H.B. and Whitney, D.R. (1947). On a test of whether one of two random variables is "
                              "stochastically larger than the other. Annals of Mathematical Statistics 18(1): 50–60.",
                         doi="10.1214/aoms/1177730491"),
    "laird-ware1982": dict(kind="method", short="Laird and Ware 1982 (mixed models)",
                           full="Laird, N.M. and Ware, J.H. (1982). Random-effects models for longitudinal data. Biometrics "
                                "38(4): 963–974.", doi="10.2307/2529876"),
    "statsmodels": dict(kind="method", short="Seabold and Perktold 2010 (statsmodels)",
                        full="Seabold, S. and Perktold, J. (2010). Statsmodels: econometric and statistical modeling with Python. "
                             "Proceedings of the 9th Python in Science Conference: 92–96.", doi="10.25080/Majora-92bf1922-011"),
    "shrout-fleiss1979": dict(kind="method", short="Shrout and Fleiss 1979 (intraclass correlation)",
                              full="Shrout, P.E. and Fleiss, J.L. (1979). Intraclass correlations: uses in assessing rater "
                                   "reliability. Psychological Bulletin 86(2): 420–428.", doi="10.1037/0033-2909.86.2.420"),
    "spearman1910": dict(kind="method", short="Spearman 1910 (Spearman–Brown)",
                         full="Spearman, C. (1910). Correlation calculated from faulty data. British Journal of Psychology 3(3): "
                              "271–295.", doi="10.1111/j.2044-8295.1910.tb00206.x"),
    "brown1910": dict(kind="method", short="Brown 1910 (Spearman–Brown)",
                      full="Brown, W. (1910). Some experimental results in the correlation of mental abilities. British Journal "
                           "of Psychology 3(3): 296–322.", doi="10.1111/j.2044-8295.1910.tb00207.x"),
    "lloyd1982": dict(kind="method", short="Lloyd 1982 (k-means)",
                      full="Lloyd, S.P. (1982). Least squares quantization in PCM. IEEE Transactions on Information Theory "
                           "28(2): 129–137.", doi="10.1109/TIT.1982.1056489"),
    "rousseeuw1987": dict(kind="method", short="Rousseeuw 1987 (silhouette)",
                          full="Rousseeuw, P.J. (1987). Silhouettes: a graphical aid to the interpretation and validation of "
                               "cluster analysis. Journal of Computational and Applied Mathematics 20: 53–65.",
                          doi="10.1016/0377-0427(87)90125-7"),
    "hubert-arabie1985": dict(kind="method", short="Hubert and Arabie 1985 (adjusted Rand index)",
                              full="Hubert, L. and Arabie, P. (1985). Comparing partitions. Journal of Classification 2(1): "
                                   "193–218.", doi="10.1007/BF01908075"),
    "hennig2007": dict(kind="method", short="Hennig 2007 (cluster stability)",
                       full="Hennig, C. (2007). Cluster-wise assessment of cluster stability. Computational Statistics and Data "
                            "Analysis 52(1): 258–271.", doi="10.1016/j.csda.2006.11.025"),
    "kruskal": dict(kind="method", short="Kruskal and Wallis 1952",
                    full="Kruskal, W.H. and Wallis, W.A. (1952). Use of ranks in one-criterion variance analysis. Journal of the "
                         "American Statistical Association 47(260): 583–621.", doi="10.1080/01621459.1952.10483441"),
    "spearman": dict(kind="method", short="Spearman 1904",
                     full="Spearman, C. (1904). The proof and measurement of association between two things. American Journal of "
                          "Psychology 15(1): 72–101.", doi="10.2307/1412159"),
    "cohen1968": dict(kind="method", short="Cohen 1968 (weighted kappa)",
                      full="Cohen, J. (1968). Weighted kappa: nominal scale agreement with provision for scaled disagreement or "
                           "partial credit. Psychological Bulletin 70(4): 213–220.", doi="10.1037/h0026256"),
    "efron1979": dict(kind="method", short="Efron 1979 (bootstrap)",
                      full="Efron, B. (1979). Bootstrap methods: another look at the jackknife. Annals of Statistics 7(1): 1–26.",
                      doi="10.1214/aos/1176344552"),
    "barnett2005": dict(kind="method", short="Barnett, van der Pols and Dobson 2005",
                        full="Barnett, A.G., van der Pols, J.C. and Dobson, A.J. (2005). Regression to the mean: what it is and "
                             "how to deal with it. International Journal of Epidemiology 34(1): 215–220.",
                        doi="10.1093/ije/dyh299"),

    # ---- science ----
    "barbour1999": dict(kind="science", short="Barbour et al. 1999 (Rapid Bioassessment Protocols)",
                        full="Barbour, M.T., Gerritsen, J., Snyder, B.D. and Stribling, J.B. (1999). Rapid Bioassessment Protocols "
                             "for Use in Streams and Wadeable Rivers: Periphyton, Benthic Macroinvertebrates and Fish, 2nd edition. "
                             "EPA 841-B-99-002. U.S. Environmental Protection Agency.",
                        url="https://www.epa.gov/sites/default/files/2019-02/documents/rapid-bioassessment-streams-rivers-1999.pdf"),
    "engel-voshell2002": dict(kind="science", short="Engel and Voshell 2002",
                              full="Engel, S.R. and Voshell, J.R. (2002). Volunteer biological monitoring: can it accurately "
                                   "assess the ecological condition of streams? American Entomologist 48(3): 164–177.",
                              doi="10.1093/ae/48.3.164"),
    "paul-meyer2001": dict(kind="science", short="Paul and Meyer 2001",
                           full="Paul, M.J. and Meyer, J.L. (2001). Streams in the urban landscape. Annual Review of Ecology and "
                                "Systematics 32: 333–365.", doi="10.1146/annurev.ecolsys.32.081501.114040"),
    "walsh2005": dict(kind="science", short="Walsh et al. 2005 (urban stream syndrome)",
                      full="Walsh, C.J., Roy, A.H., Feminella, J.W., Cottingham, P.D., Groffman, P.M. and Morgan, R.P. (2005). The "
                           "urban stream syndrome: current knowledge and the search for a cure. Journal of the North American "
                           "Benthological Society 24(3): 706–723.", doi="10.1899/04-028.1"),
    "kaushal2005": dict(kind="science", short="Kaushal et al. 2005",
                        full="Kaushal, S.S. et al. (2005). Increased salinization of fresh water in the northeastern United States. "
                             "Proceedings of the National Academy of Sciences 102(38): 13517–13520.",
                        doi="10.1073/pnas.0506414102"),
    "kaushal2018": dict(kind="science", short="Kaushal et al. 2018",
                        full="Kaushal, S.S. et al. (2018). Freshwater salinization syndrome on a continental scale. Proceedings of "
                             "the National Academy of Sciences 115(4): E574–E583.", doi="10.1073/pnas.1711234115"),
    "corsi2010": dict(kind="science", short="Corsi et al. 2010",
                      full="Corsi, S.R., Graczyk, D.J., Geis, S.W., Booth, N.L. and Richards, K.D. (2010). A fresh look at road "
                           "salt: aquatic toxicity and water-quality impacts on local, regional, and national scales. "
                           "Environmental Science & Technology 44(19): 7376–7382.", doi="10.1021/es101333u"),
    "bernhardt2005": dict(kind="science", short="Bernhardt et al. 2005",
                          full="Bernhardt, E.S. et al. (2005). Synthesizing U.S. river restoration efforts. Science 308(5722): "
                               "636–637.", doi="10.1126/science.1109769"),
}

KIND_TITLES = {"data": "Data sources", "method": "Methods", "science": "Science behind the readings"}


def link(key: str) -> str:
    r = REFS[key]
    return f"https://doi.org/{r['doi']}" if r.get("doi") else r["url"]


def check(keys) -> None:
    bad = [k for k in keys if k not in REFS]
    if bad:
        raise KeyError(f"unknown reference key(s): {', '.join(bad)}")
