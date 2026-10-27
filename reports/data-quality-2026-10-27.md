# Data-quality report, snapshot 2026-10-27

Source: Clean Water Hub public API. Personal fields were removed at download.

## Records by protocol

A survey is usable when it has a date, is not deleted or archived, and is not a duplicate.

| protocol | records | usable | no_date | bad_date | deleted | archived | duplicates | sites | first | last |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| salt | 38,185 | 35,289 | 460 | 17 | 2,240 | 0 | 390 | 13,516 | 2005-02-10 | 2026-10-27 |
| sos_chem | 25,620 | 24,714 | 638 | 10 | 315 | 0 | 203 | 1,946 | 1994-03-26 | 2026-10-26 |
| nitrate | 16,522 | 15,880 | 8 | 3 | 273 | 0 | 363 | 5,165 | 2012-07-05 | 2026-10-26 |
| va_rocky | 7,026 | 6,516 | 145 | 0 | 266 | 0 | 189 | 898 | 2002-02-03 | 2026-10-27 |
| sos_bio | 974 | 780 | 177 | 0 | 57 | 0 | 3 | 363 | 1994-03-26 | 2026-10-26 |
| va_muddy | 184 | 118 | 24 | 0 | 62 | 0 | 1 | 63 | 2014-09-09 | 2026-10-21 |

## Usable surveys by state (top 12)

| state | surveys | sites |
| --- | --- | --- |
| IA | 25,760 | 3,188 |
| VA | 13,254 | 1,237 |
| (none) | 13,022 | 9,083 |
| MD | 8,131 | 824 |
| NJ | 3,074 | 1,312 |
| OH | 2,932 | 387 |
| MN | 2,821 | 790 |
| PA | 2,601 | 589 |
| WI | 2,390 | 745 |
| MI | 1,805 | 325 |
| Ohio | 1,640 | 54 |
| CT | 1,200 | 156 |

## Usable surveys by year

| year | nitrate | salt | sos_bio | sos_chem | va_muddy | va_rocky |
| --- | --- | --- | --- | --- | --- | --- |
| 1994 | 0 | 0 | 1 | 1 | 0 | 0 |
| 1995 | 0 | 0 | 1 | 1 | 0 | 0 |
| 1996 | 0 | 0 | 2 | 2 | 0 | 0 |
| 1997 | 0 | 0 | 3 | 1 | 0 | 0 |
| 1998 | 0 | 0 | 1 | 1 | 0 | 0 |
| 1999 | 0 | 0 | 4 | 4 | 0 | 0 |
| 2000 | 0 | 0 | 1 | 15 | 0 | 0 |
| 2001 | 0 | 0 | 1 | 11 | 0 | 0 |
| 2002 | 0 | 0 | 5 | 103 | 0 | 4 |
| 2003 | 0 | 0 | 5 | 178 | 0 | 1 |
| 2004 | 0 | 0 | 3 | 218 | 0 | 2 |
| 2005 | 0 | 1 | 8 | 229 | 0 | 4 |
| 2006 | 0 | 0 | 6 | 224 | 0 | 424 |
| 2007 | 0 | 1 | 18 | 266 | 0 | 376 |
| 2008 | 0 | 1 | 15 | 399 | 0 | 460 |
| 2009 | 0 | 0 | 11 | 133 | 0 | 265 |
| 2010 | 0 | 0 | 16 | 201 | 0 | 288 |
| 2011 | 0 | 0 | 11 | 230 | 0 | 264 |
| 2012 | 1 | 0 | 8 | 199 | 0 | 179 |
| 2013 | 0 | 0 | 5 | 177 | 0 | 265 |
| 2014 | 1 | 0 | 4 | 165 | 3 | 300 |
| 2015 | 0 | 1 | 5 | 121 | 3 | 274 |
| 2016 | 7 | 1 | 4 | 119 | 1 | 298 |
| 2017 | 18 | 0 | 27 | 305 | 4 | 333 |
| 2018 | 19 | 55 | 47 | 479 | 9 | 276 |
| 2019 | 27 | 414 | 92 | 865 | 6 | 318 |
| 2020 | 6 | 1,136 | 48 | 1,275 | 0 | 141 |
| 2021 | 19 | 2,388 | 109 | 2,055 | 18 | 283 |
| 2022 | 38 | 4,326 | 100 | 2,756 | 13 | 349 |
| 2023 | 1,439 | 4,091 | 58 | 4,500 | 16 | 421 |
| 2024 | 2,565 | 6,564 | 48 | 4,722 | 14 | 394 |
| 2025 | 4,565 | 8,783 | 64 | 3,203 | 20 | 337 |
| 2026 | 7,175 | 7,527 | 49 | 1,556 | 11 | 260 |

## Water temperature units

The Hub stores no unit. Readings up to 32 are taken as Celsius, 41 and up as Fahrenheit (converted); 32 to 41 is ambiguous and left blank.

| protocol | temp_rule | readings |
| --- | --- | --- |
| sos_bio | celsius | 597 |
| sos_bio | fahrenheit_converted | 21 |
| sos_bio | ambiguous | 5 |
| sos_bio | implausible | 1 |
| sos_chem | celsius | 20,624 |
| sos_chem | implausible | 54 |
| sos_chem | fahrenheit_converted | 28 |
| sos_chem | ambiguous | 20 |
| va_muddy | celsius | 73 |
| va_muddy | fahrenheit_converted | 2 |
| va_rocky | celsius | 1,803 |
| va_rocky | fahrenheit_converted | 32 |
| va_rocky | implausible | 9 |

## Chemistry readings

Out of range = outside the plausible band shown.

| protocol | parameter | unit | readings | median | p95 | out_of_range |
| --- | --- | --- | --- | --- | --- | --- |
| nitrate | nitrate | mg/L | 15,879 | 2 | 20 | 16 |
| salt | chloride | mg/L | 35,288 | 85 | 612 | 5 |
| salt | quantab_unit_reading | Quantab units | 16,037 | 3 | 7.1 |  |
| sos_chem | ph_units | pH | 21,775 | 8 | 9 | 19 |
| sos_chem | nitrate_n | mg/L | 20,722 | 2 | 20 | 1 |
| sos_chem | dissolved_oxygen | mg/L | 19,793 | 8 | 12 | 13 |
| sos_chem | phosphate | mg/L | 19,217 | 0.12 | 1.5 | 123 |
| sos_chem | chloride | mg/L | 19,000 | 36 | 224 | 0 |
| sos_chem | transparency | cm | 16,640 | 60 | 90 | 3 |
| sos_chem | dissolved_oxygen_saturation | % | 9,417 | 81 | 120 | 5 |
| sos_chem | conductivity | uS/cm | 205 | 103.2 | 126.64 | 0 |

## Species-group fields

| protocol | tolerance | fields | times_present | mean_count_when_found |
| --- | --- | --- | --- | --- |
| sos_bio | less_sensitive | 12 | 2,258 | 8.6 |
| sos_bio | sensitive | 7 | 1,766 | 9.4 |
| sos_bio | tolerant | 5 | 1,598 | 5.9 |
| va_muddy | less_sensitive | 9 | 425 | 18.5 |
| va_muddy | sensitive | 5 | 224 | 14.3 |
| va_muddy | tolerant | 6 | 330 | 13.5 |
| va_muddy | unassigned | 2 | 69 | 5.1 |
| va_rocky | less_sensitive | 7 | 18,489 | 29.4 |
| va_rocky | sensitive | 5 | 22,605 | 37.2 |
| va_rocky | tolerant | 6 | 19,286 | 26.3 |
| va_rocky | unassigned | 1 | 4,595 | 6.7 |

## Field completeness, biological surveys

| protocol | usable | pct_temp | pct_flow | pct_weather | pct_group_size | pct_certified_field |
| --- | --- | --- | --- | --- | --- | --- |
| sos_bio | 780 | 77 | 60 | 76 | 77 | 29 |
| va_rocky | 6,516 | 26 | 94 | 96 | 98 | 98 |
| va_muddy | 118 | 54 | 91 | 90 | 95 | 96 |

## Chapter sites (467, 468)

| site_id | protocol | records | usable | no_date | duplicates | first | last |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 467 | sos_bio | 31 | 27 | 4 | 0 | 2005-05-24 | 2024-05-26 |
| 467 | va_rocky | 1 | 1 | 0 | 0 | 2025-09-21 | 2025-09-21 |
| 468 | sos_bio | 26 | 16 | 10 | 0 | 2007-03-27 | 2024-09-15 |
| 468 | va_rocky | 2 | 2 | 0 | 0 | 2024-09-15 | 2026-05-17 |

Years with no usable chapter survey: 2013, 2014, 2017, 2020

## Biological sites nearest the chapter sites (within 25 km)

Candidates for upstream and downstream comparison.

| site_id | site | stream | state | km | biological surveys |
| --- | --- | --- | --- | --- | --- |
| 5378 | Great Seneca Creek- IWLA Rockville Chapter grounds | Great Seneca Creek | MD | 0.1 | 1 |
| 545 | LGS Site #6 - Cabin Branch | Cabin Branch | MD | 3.5 | 3 |
| 56 | IWLA National Headquarters - Training Site | Muddy Branch | MD | 4.8 | 14 |
| 55 | IWLA National Headquarters - Roadside | Muddy Branch | MD | 4.9 | 4 |
| 402 | LGS Site #1 - Cabin Branch | Cabin Branch | MD | 6.4 | 1 |
| 39066 | Greenway Trail- Foreman Ave | Little Seneca Creek | MD | 8.3 | 3 |
| 5383 | Hookers Branch | Hookers Branch | MD | 10.0 | 3 |
| 10201 | North Branch of Rock Creek, Rockville, Maryland | North Branch of Rock Creek, Rockville, MD | MD | 13.2 | 28 |
| 12062 | Springs Stream- A Tributary to Rock Creek | Springs Stream | MD | 13.2 | 11 |
| 11258 | NICRUN1.64 | Nichols Run | VA | 13.8 | 14 |
| 11194 | CLABRA0.08 | Clarks Branch | VA | 14.1 | 2 |
| 10275 | BCC-IWLA #2 | Horsepen Branch | MD | 15.8 | 2 |
| 411 | BCC IWLA 1 | Horsepen Branch | MD | 15.9 | 1 |
| 46620 | WHIHOLRUN0.13 | Whiskey Hollow Run | VA | 16.0 | 1 |
| 12077 | Horsepen Branch | Horsepen Branch | MD | 16.7 | 1 |
