#!/usr/bin/env python3

import argparse
import csv
import io
import json
import random
import re
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


API_URL = "https://www.worldcubeassociation.org/api/v0/export/public"

DATA_DIR = Path("data")
BUILD_DIR = Path(".build-data")

DATA_SCHEMA_VERSION = 2

MAX_SCRAMBLES_PER_EVENT = 5000
SCRAMBLES_PER_FILE = 250

SUPPORTED_GENDERS = ("m", "f", "o", "u")


SUPPORTED_EVENTS = {

    "222": {
        "name": "2x2 Cube",
        "format": "time",
        "official_average": "ao5",
    },

    "333": {
        "name": "3x3 Cube",
        "format": "time",
        "official_average": "ao5",
    },

    "444": {
        "name": "4x4 Cube",
        "format": "time",
        "official_average": "ao5",
    },

    "555": {
        "name": "5x5 Cube",
        "format": "time",
        "official_average": "ao5",
    },

    "666": {
        "name": "6x6 Cube",
        "format": "time",
        "official_average": "mo3",
    },

    "777": {
        "name": "7x7 Cube",
        "format": "time",
        "official_average": "mo3",
    },

    "333oh": {
        "name": "3x3 One-Handed",
        "format": "time",
        "official_average": "ao5",
    },

    "333bf": {
        "name": "3x3 Blindfolded",
        "format": "time",
        "official_average": "mo3",
    },

    "444bf": {
        "name": "4x4 Blindfolded",
        "format": "time",
        "official_average": "mo3",
    },

    "555bf": {
        "name": "5x5 Blindfolded",
        "format": "time",
        "official_average": "mo3",
    },

    "333fm": {
        "name": "3x3 Fewest Moves",
        "format": "number",
        "official_average": "mo3",
    },

    "333mbf": {
        "name": "3x3 Multi-Blind",
        "format": "multi",
        "official_average": None,
    },

    "clock": {
        "name": "Clock",
        "format": "time",
        "official_average": "ao5",
    },

    "minx": {
        "name": "Megaminx",
        "format": "time",
        "official_average": "ao5",
    },

    "pyram": {
        "name": "Pyraminx",
        "format": "time",
        "official_average": "ao5",
    },

    "skewb": {
        "name": "Skewb",
        "format": "time",
        "official_average": "ao5",
    },

    "sq1": {
        "name": "Square-1",
        "format": "time",
        "official_average": "ao5",
    },

    "333ft": {
        "name": "3x3 With Feet",
        "format": "time",
        "official_average": "ao5",
        "legacy": True,
    },
}


def load_json(path):

    try:

        with open(
            path,
            "r",
            encoding="utf-8"
        ) as file:

            return json.load(file)

    except Exception:

        return None


def save_json(
    path,
    data,
    pretty=False
):

    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        path,
        "w",
        encoding="utf-8"
    ) as file:

        if pretty:

            json.dump(
                data,
                file,
                ensure_ascii=False,
                indent=2
            )

        else:

            json.dump(
                data,
                file,
                ensure_ascii=False,
                separators=(",", ":")
            )


def fetch_json(url):

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent":
                "Rubiknesia-Ranking-Timer/2.0"
        }
    )

    with urllib.request.urlopen(
        request,
        timeout=60
    ) as response:

        return json.loads(
            response
            .read()
            .decode("utf-8")
        )


def download_file(
    url,
    destination
):

    print()

    print(
        "Downloading WCA TSV export..."
    )

    print(url)

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent":
                "Rubiknesia-Ranking-Timer/2.0"
        }
    )

    with urllib.request.urlopen(
        request,
        timeout=1200
    ) as response:

        total = response.headers.get(
            "Content-Length"
        )

        total = (
            int(total)
            if total
            else None
        )

        downloaded = 0

        chunk_size = (
            1024 *
            1024
        )

        with open(
            destination,
            "wb"
        ) as file:

            while True:

                chunk = response.read(
                    chunk_size
                )

                if not chunk:
                    break

                file.write(
                    chunk
                )

                downloaded += len(
                    chunk
                )

                if total:

                    percent = (
                        downloaded /
                        total *
                        100
                    )

                    print(
                        f"\rDownload: {percent:.1f}%",
                        end="",
                        flush=True
                    )

    print()

    print(
        "Download complete."
    )


def find_table_file(
    zip_file,
    table_name
):

    needle = (
        table_name
        .lower()
    )

    candidates = []

    for filename in zip_file.namelist():

        basename = (
            Path(filename)
            .name
            .lower()
        )

        if (
            basename.endswith(".tsv")
            and
            needle in basename
        ):

            candidates.append(
                filename
            )

    if not candidates:

        raise RuntimeError(
            f"Cannot find TSV table: {table_name}"
        )

    candidates.sort(
        key=len
    )

    return candidates[0]


def open_tsv(
    zip_file,
    filename
):

    binary_file = zip_file.open(
        filename
    )

    text_file = io.TextIOWrapper(
        binary_file,
        encoding="utf-8-sig",
        newline=""
    )

    return csv.DictReader(
        text_file,
        delimiter="\t"
    )


def field(
    row,
    *names
):

    for name in names:

        if (
            name in row
            and
            row[name] is not None
        ):

            return row[name]

    return None


def integer(
    value,
    default=None
):

    try:

        return int(value)

    except Exception:

        return default


def slug(value):

    value = (
        str(value or "")
        .strip()
        .lower()
        .lstrip("_")
    )

    value = re.sub(
        r"[^a-z0-9]+",
        "-",
        value
    ).strip("-")

    return (
        value
        or
        "unknown"
    )


def normalize_gender(value):

    value = (
        str(value or "")
        .strip()
        .lower()
    )

    if value == "m":
        return "m"

    if value == "f":
        return "f"

    if value in (
        "o",
        "other"
    ):
        return "o"

    return "u"


def read_continents(zip_file):

    filename = find_table_file(
        zip_file,
        "continents"
    )

    print(
        "Reading:",
        filename
    )

    continents = {}

    reader = open_tsv(
        zip_file,
        filename
    )

    for row in reader:

        continent_id = field(
            row,
            "id"
        )

        if not continent_id:
            continue

        name = (
            field(
                row,
                "name"
            )
            or
            continent_id
        )

        record_name = (
            field(
                row,
                "record_name",
                "recordName"
            )
            or
            name
        )

        continents[
            continent_id
        ] = {

            "id":
                continent_id,

            "key":
                slug(
                    continent_id
                ),

            "name":
                name,

            "record_name":
                record_name,

        }

    return continents


def read_countries(
    zip_file,
    continents
):

    filename = find_table_file(
        zip_file,
        "countries"
    )

    print(
        "Reading:",
        filename
    )

    countries = {}

    used_keys = set()

    reader = open_tsv(
        zip_file,
        filename
    )

    for row in reader:

        country_id = field(
            row,
            "id"
        )

        if not country_id:
            continue

        continent_id = field(
            row,
            "continent_id",
            "continentId"
        )

        iso2 = (
            field(
                row,
                "iso2"
            )
            or
            ""
        ).strip().upper()

        name = (
            field(
                row,
                "name"
            )
            or
            country_id
        )

        key = (
            iso2.lower()
            if iso2
            else
            slug(country_id)
        )

        if key in used_keys:

            key = slug(
                country_id
            )

        if key in used_keys:

            base = key

            suffix = 2

            while (
                f"{base}-{suffix}"
                in used_keys
            ):

                suffix += 1

            key = (
                f"{base}-{suffix}"
            )

        used_keys.add(
            key
        )

        continent = continents.get(
            continent_id
        )

        countries[
            country_id
        ] = {

            "id":
                country_id,

            "key":
                key,

            "iso2":
                iso2
                or
                None,

            "name":
                name,

            "continent_id":
                continent_id,

            "continent_key":
                (
                    continent["key"]
                    if continent
                    else
                    slug(continent_id)
                    if continent_id
                    else
                    None
                ),

        }

    return countries


def read_persons(
    zip_file,
    countries
):

    filename = find_table_file(
        zip_file,
        "persons"
    )

    print(
        "Reading:",
        filename
    )

    persons = {}

    reader = open_tsv(
        zip_file,
        filename
    )

    for row in reader:

        sub_id = integer(
            field(
                row,
                "sub_id",
                "subid",
                "subId"
            ),
            1
        )

        if sub_id != 1:
            continue

        wca_id = field(
            row,
            "wca_id",
            "id"
        )

        if not wca_id:
            continue

        country_id = field(
            row,
            "country_id",
            "countryId"
        )

        country = countries.get(
            country_id
        )

        persons[
            wca_id
        ] = {

            "country_id":
                country_id,

            "country_key":
                (
                    country["key"]
                    if country
                    else
                    None
                ),

            "continent_key":
                (
                    country[
                        "continent_key"
                    ]
                    if country
                    else
                    None
                ),

            "gender":
                normalize_gender(
                    field(
                        row,
                        "gender"
                    )
                ),

        }

    return persons


def write_regions(
    output_dir,
    continents,
    countries,
    export_date
):

    countries_by_continent = {}

    country_rows = []

    for country in countries.values():

        continent_key = country.get(
            "continent_key"
        )

        if continent_key:

            countries_by_continent.setdefault(
                continent_key,
                []
            ).append(
                country["key"]
            )

        country_rows.append({

            "key":
                country["key"],

            "id":
                country["id"],

            "iso2":
                country["iso2"],

            "name":
                country["name"],

            "continent_key":
                continent_key,

        })

    continent_rows = []

    for continent in continents.values():

        continent_rows.append({

            "key":
                continent["key"],

            "id":
                continent["id"],

            "name":
                continent["name"],

            "record_name":
                continent[
                    "record_name"
                ],

            "countries":
                sorted(
                    countries_by_continent.get(
                        continent["key"],
                        []
                    )
                ),

        })

    continent_rows.sort(
        key=lambda item:
            item["name"]
    )

    country_rows.sort(
        key=lambda item:
            item["name"]
    )

    payload = {

        "schema_version":
            DATA_SCHEMA_VERSION,

        "export_date":
            export_date,

        "genders": {

            "all":
                "All",

            "m":
                "Male",

            "f":
                "Female",

            "o":
                "Other",

            "u":
                "Unspecified",

        },

        "continents":
            continent_rows,

        "countries":
            country_rows,

    }

    save_json(
        output_dir /
        "regions.json",
        payload,
        pretty=True
    )


def new_filtered_event():

    return {

        "world": {

            gender: []

            for gender
            in SUPPORTED_GENDERS

        },

        "continents": {},

        "countries": {},

    }


def new_gender_bucket():

    return {

        "all": [],

        "m": [],

        "f": [],

        "o": [],

        "u": [],

    }


def compress_ranking(values):

    if not values:

        return {

            "total": 0,

            "table": []

        }

    counter = Counter(
        values
    )

    cumulative = 0

    table = []

    for value in sorted(
        counter
    ):

        cumulative += (
            counter[value]
        )

        table.append(
            [
                value,
                cumulative
            ]
        )

    return {

        "total":
            len(values),

        "table":
            table,

    }


def read_rankings(
    zip_file,
    table_name,
    persons
):

    filename = find_table_file(
        zip_file,
        table_name
    )

    print(
        "Reading:",
        filename
    )

    global_values = {

        event: []

        for event
        in SUPPORTED_EVENTS

    }

    filtered = {

        event:
            new_filtered_event()

        for event
        in SUPPORTED_EVENTS

    }

    missing_person_rows = 0

    reader = open_tsv(
        zip_file,
        filename
    )

    for row in reader:

        event = field(
            row,
            "event_id",
            "eventId"
        )

        if event not in global_values:
            continue

        best = integer(
            field(
                row,
                "best"
            )
        )

        if (
            best is None
            or
            best <= 0
        ):

            continue

        global_values[
            event
        ].append(
            best
        )

        person_id = field(
            row,
            "person_id",
            "personId",
            "wca_id"
        )

        person = persons.get(
            person_id
        )

        if not person:

            missing_person_rows += 1

            continue

        gender = person[
            "gender"
        ]

        event_filtered = filtered[
            event
        ]

        event_filtered[
            "world"
        ][gender].append(
            best
        )

        continent_key = person.get(
            "continent_key"
        )

        if continent_key:

            continent_store = (
                event_filtered[
                    "continents"
                ]
            )

            if (
                continent_key
                not in
                continent_store
            ):

                continent_store[
                    continent_key
                ] = new_gender_bucket()

            continent_store[
                continent_key
            ]["all"].append(
                best
            )

            continent_store[
                continent_key
            ][gender].append(
                best
            )

        country_key = person.get(
            "country_key"
        )

        if country_key:

            country_store = (
                event_filtered[
                    "countries"
                ]
            )

            if (
                country_key
                not in
                country_store
            ):

                country_store[
                    country_key
                ] = new_gender_bucket()

            country_store[
                country_key
            ]["all"].append(
                best
            )

            country_store[
                country_key
            ][gender].append(
                best
            )

    if missing_person_rows:

        print(

            f"Warning: "
            f"{missing_person_rows} "
            f"{table_name} rows "
            "could not be joined "
            "to current person metadata."

        )

    return (
        global_values,
        filtered
    )


def write_global_rankings(
    output_dir,
    single_rankings,
    average_rankings,
    export_date
):

    ranking_dir = (
        output_dir /
        "ranking"
    )

    ranking_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    manifest_data = {}

    for (
        event,
        config
    ) in SUPPORTED_EVENTS.items():

        single = compress_ranking(
            single_rankings.get(
                event,
                []
            )
        )

        average = compress_ranking(
            average_rankings.get(
                event,
                []
            )
        )

        payload = {

            "schema_version":
                DATA_SCHEMA_VERSION,

            "event":
                event,

            "name":
                config[
                    "name"
                ],

            "format":
                config[
                    "format"
                ],

            "official_average":
                config.get(
                    "official_average"
                ),

            "legacy":
                config.get(
                    "legacy",
                    False
                ),

            "export_date":
                export_date,

            "single":
                single,

            "average":
                average,

        }

        filename = (
            f"{event}.json"
        )

        save_json(
            ranking_dir /
            filename,
            payload
        )

        manifest_data[
            event
        ] = {

            "file":
                f"ranking/{filename}",

            "single_count":
                single[
                    "total"
                ],

            "average_count":
                average[
                    "total"
                ],

        }

    return manifest_data


def combined_gender_payload(
    single_bucket,
    average_bucket,
    include_all=True
):

    genders = (

        ("all",)
        +
        SUPPORTED_GENDERS

        if include_all

        else

        SUPPORTED_GENDERS

    )

    payload = {}

    for gender in genders:

        payload[
            gender
        ] = {

            "single":
                compress_ranking(
                    (
                        single_bucket
                        or
                        {}
                    ).get(
                        gender,
                        []
                    )
                ),

            "average":
                compress_ranking(
                    (
                        average_bucket
                        or
                        {}
                    ).get(
                        gender,
                        []
                    )
                ),

        }

    return payload


def bucket_has_data(
    single_bucket,
    average_bucket
):

    for bucket in (

        single_bucket
        or
        {},

        average_bucket
        or
        {}

    ):

        for values in (
            bucket.values()
        ):

            if values:

                return True

    return False


def write_filtered_rankings(
    output_dir,
    single_filtered,
    average_filtered,
    export_date
):

    root_dir = (
        output_dir /
        "ranking-filtered"
    )

    root_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    manifest = {}

    for (
        event,
        config
    ) in SUPPORTED_EVENTS.items():

        event_dir = (
            root_dir /
            event
        )

        event_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        single_event = (
            single_filtered[
                event
            ]
        )

        average_event = (
            average_filtered[
                event
            ]
        )

        world_payload = {

            "schema_version":
                DATA_SCHEMA_VERSION,

            "event":
                event,

            "scope":
                "world",

            "region_key":
                "world",

            "export_date":
                export_date,

            "gender":
                combined_gender_payload(
                    single_event[
                        "world"
                    ],
                    average_event[
                        "world"
                    ],
                    include_all=False
                ),

        }

        save_json(
            event_dir /
            "world.json",
            world_payload
        )

        continent_files = {}

        continent_keys = sorted(

            set(
                single_event[
                    "continents"
                ]
            )

            |

            set(
                average_event[
                    "continents"
                ]
            )

        )

        for continent_key in (
            continent_keys
        ):

            single_bucket = (
                single_event[
                    "continents"
                ].get(
                    continent_key
                )
            )

            average_bucket = (
                average_event[
                    "continents"
                ].get(
                    continent_key
                )
            )

            if not bucket_has_data(
                single_bucket,
                average_bucket
            ):

                continue

            local_path = (
                f"continents/"
                f"{continent_key}.json"
            )

            public_path = (
                f"ranking-filtered/"
                f"{event}/"
                f"continents/"
                f"{continent_key}.json"
            )

            payload = {

                "schema_version":
                    DATA_SCHEMA_VERSION,

                "event":
                    event,

                "scope":
                    "continent",

                "region_key":
                    continent_key,

                "export_date":
                    export_date,

                "gender":
                    combined_gender_payload(
                        single_bucket,
                        average_bucket,
                        include_all=True
                    ),

            }

            save_json(
                event_dir /
                local_path,
                payload
            )

            continent_files[
                continent_key
            ] = public_path

        country_files = {}

        country_keys = sorted(

            set(
                single_event[
                    "countries"
                ]
            )

            |

            set(
                average_event[
                    "countries"
                ]
            )

        )

        for country_key in (
            country_keys
        ):

            single_bucket = (
                single_event[
                    "countries"
                ].get(
                    country_key
                )
            )

            average_bucket = (
                average_event[
                    "countries"
                ].get(
                    country_key
                )
            )

            if not bucket_has_data(
                single_bucket,
                average_bucket
            ):

                continue

            local_path = (
                f"countries/"
                f"{country_key}.json"
            )

            public_path = (
                f"ranking-filtered/"
                f"{event}/"
                f"countries/"
                f"{country_key}.json"
            )

            payload = {

                "schema_version":
                    DATA_SCHEMA_VERSION,

                "event":
                    event,

                "scope":
                    "country",

                "region_key":
                    country_key,

                "export_date":
                    export_date,

                "gender":
                    combined_gender_payload(
                        single_bucket,
                        average_bucket,
                        include_all=True
                    ),

            }

            save_json(
                event_dir /
                local_path,
                payload
            )

            country_files[
                country_key
            ] = public_path

        event_index = {

            "schema_version":
                DATA_SCHEMA_VERSION,

            "event":
                event,

            "name":
                config[
                    "name"
                ],

            "format":
                config[
                    "format"
                ],

            "official_average":
                config.get(
                    "official_average"
                ),

            "export_date":
                export_date,

            "world": {

                "all":
                    (
                        f"ranking/"
                        f"{event}.json"
                    ),

                "gender":
                    (
                        f"ranking-filtered/"
                        f"{event}/"
                        f"world.json"
                    ),

            },

            "continents":
                continent_files,

            "countries":
                country_files,

        }

        save_json(
            event_dir /
            "index.json",
            event_index,
            pretty=True
        )

        manifest[
            event
        ] = {

            "index":
                (
                    f"ranking-filtered/"
                    f"{event}/"
                    f"index.json"
                ),

            "world_gender":
                (
                    f"ranking-filtered/"
                    f"{event}/"
                    f"world.json"
                ),

            "continent_count":
                len(
                    continent_files
                ),

            "country_count":
                len(
                    country_files
                ),

        }

    return manifest


def read_scrambles(zip_file):

    filename = find_table_file(
        zip_file,
        "scrambles"
    )

    print(
        "Reading:",
        filename
    )

    samples = {

        event: []

        for event
        in SUPPORTED_EVENTS

    }

    totals = {

        event: 0

        for event
        in SUPPORTED_EVENTS

    }

    randomizers = {

        event:
            random.Random(
                f"rubiknesia-{event}"
            )

        for event
        in SUPPORTED_EVENTS

    }

    reader = open_tsv(
        zip_file,
        filename
    )

    for row in reader:

        event = field(
            row,
            "event_id",
            "eventId"
        )

        if event not in samples:
            continue

        scramble = field(
            row,
            "scramble"
        )

        if not scramble:
            continue

        totals[
            event
        ] += 1

        record = {

            "scramble":
                scramble,

            "competition_id":
                field(
                    row,
                    "competition_id",
                    "competitionId"
                ),

            "round_type_id":
                field(
                    row,
                    "round_type_id",
                    "roundTypeId"
                ),

            "group_id":
                field(
                    row,
                    "group_id",
                    "groupId"
                ),

            "scramble_num":
                integer(
                    field(
                        row,
                        "scramble_num",
                        "scrambleNum"
                    )
                ),

            "is_extra":
                field(
                    row,
                    "is_extra",
                    "isExtra"
                ),

            "id":
                integer(
                    field(
                        row,
                        "id",
                        "scramble_id",
                        "scrambleId"
                    )
                ),

        }

        if (
            MAX_SCRAMBLES_PER_EVENT
            <= 0
        ):

            samples[
                event
            ].append(
                record
            )

            continue

        current = samples[
            event
        ]

        if (
            len(current)
            <
            MAX_SCRAMBLES_PER_EVENT
        ):

            current.append(
                record
            )

        else:

            index = (
                randomizers[
                    event
                ]
                .randrange(
                    totals[
                        event
                    ]
                )
            )

            if (
                index
                <
                MAX_SCRAMBLES_PER_EVENT
            ):

                current[
                    index
                ] = record

    return (
        samples,
        totals
    )


def write_scrambles(
    output_dir,
    samples,
    totals
):

    root_dir = (
        output_dir /
        "scrambles"
    )

    root_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    manifest_data = {}

    for (
        event,
        config
    ) in SUPPORTED_EVENTS.items():

        records = samples.get(
            event,
            []
        )

        event_dir = (
            root_dir /
            event
        )

        event_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        files = []

        for start in range(
            0,
            len(records),
            SCRAMBLES_PER_FILE
        ):

            part = (
                start //
                SCRAMBLES_PER_FILE
            )

            filename = (
                f"{part:03d}.json"
            )

            shard = records[
                start:
                start +
                SCRAMBLES_PER_FILE
            ]

            save_json(
                event_dir /
                filename,
                {

                    "event":
                        event,

                    "scrambles":
                        shard,

                }
            )

            files.append(
                filename
            )

        index = {

            "event":
                event,

            "name":
                config[
                    "name"
                ],

            "source_total":
                totals.get(
                    event,
                    0
                ),

            "available":
                len(
                    records
                ),

            "per_file":
                SCRAMBLES_PER_FILE,

            "files":
                files,

        }

        save_json(
            event_dir /
            "index.json",
            index,
            pretty=True
        )

        manifest_data[
            event
        ] = {

            "index":
                (
                    f"scrambles/"
                    f"{event}/"
                    f"index.json"
                ),

            "source_total":
                totals.get(
                    event,
                    0
                ),

            "available":
                len(
                    records
                ),

        }

    return manifest_data


def build(
    zip_path,
    api_info
):

    if BUILD_DIR.exists():

        shutil.rmtree(
            BUILD_DIR
        )

    BUILD_DIR.mkdir(
        parents=True
    )

    export_date = api_info.get(
        "export_date"
    )

    print()

    print(
        "Opening WCA export..."
    )

    with zipfile.ZipFile(
        zip_path,
        "r"
    ) as zip_file:

        continents = read_continents(
            zip_file
        )

        countries = read_countries(
            zip_file,
            continents
        )

        persons = read_persons(
            zip_file,
            countries
        )

        print(
            "Current persons loaded:",
            len(persons)
        )

        (
            single_rankings,
            single_filtered
        ) = read_rankings(
            zip_file,
            "ranks_single",
            persons
        )

        (
            average_rankings,
            average_filtered
        ) = read_rankings(
            zip_file,
            "ranks_average",
            persons
        )

        (
            scramble_samples,
            scramble_totals
        ) = read_scrambles(
            zip_file
        )

    print()

    print(
        "Writing region metadata..."
    )

    write_regions(
        BUILD_DIR,
        continents,
        countries,
        export_date
    )

    print(
        "Writing global ranking JSON..."
    )

    ranking_manifest = (
        write_global_rankings(
            BUILD_DIR,
            single_rankings,
            average_rankings,
            export_date
        )
    )

    print(
        "Writing filtered ranking JSON..."
    )

    filtered_manifest = (
        write_filtered_rankings(
            BUILD_DIR,
            single_filtered,
            average_filtered,
            export_date
        )
    )

    print(
        "Writing scramble JSON..."
    )

    scramble_manifest = (
        write_scrambles(
            BUILD_DIR,
            scramble_samples,
            scramble_totals
        )
    )

    generated_at = (
        datetime.now(
            timezone.utc
        )
        .isoformat()
    )

    export_version = (
        api_info.get(
            "export_version"
        )
        or
        "unknown"
    )

    date_only = (
        export_date[:10]
        if export_date
        else
        "unknown"
    )

    attribution = (
        "This information is based on "
        "competition results owned and "
        "maintained by the World Cube "
        "Association, published at "
        "https://worldcubeassociation.org/results "
        f"as of {date_only}."
    )

    manifest = {

        "project":
            "Rubiknesia Ranking Timer",

        "data_schema_version":
            DATA_SCHEMA_VERSION,

        "generated_at":
            generated_at,

        "export_date":
            export_date,

        "export_version":
            export_version,

        "source":
            "World Cube Association",

        "source_url":
            (
                "https://www."
                "worldcubeassociation.org/"
                "export/results"
            ),

        "attribution":
            attribution,

        "ranking_note":
            (
                "World, continental and national "
                "simulations use WCA results export "
                "data. Gender filters are custom "
                "Rubiknesia simulations derived "
                "from public WCA competitor gender "
                "data and are not official WCA "
                "gender rankings."
            ),

        "regions_file":
            "regions.json",

        "scramble_sample_limit":
            MAX_SCRAMBLES_PER_EVENT,

        "scrambles_per_file":
            SCRAMBLES_PER_FILE,

        "events":
            SUPPORTED_EVENTS,

        "ranking":
            ranking_manifest,

        "filtered_ranking":
            filtered_manifest,

        "scrambles":
            scramble_manifest,

    }

    save_json(
        BUILD_DIR /
        "manifest.json",
        manifest,
        pretty=True
    )

    if DATA_DIR.exists():

        shutil.rmtree(
            DATA_DIR
        )

    shutil.move(
        str(
            BUILD_DIR
        ),
        str(
            DATA_DIR
        )
    )

    print()

    print(
        "======================================"
    )

    print(
        "Rubiknesia WCA data build complete."
    )

    print(
        "Data schema:",
        DATA_SCHEMA_VERSION
    )

    print(
        "Export:",
        export_date
    )

    print(
        "Version:",
        export_version
    )

    print(
        "Output:",
        DATA_DIR.resolve()
    )

    print(
        "======================================"
    )


def main():

    parser = argparse.ArgumentParser(
        description=(
            "Generate lightweight WCA data "
            "for Rubiknesia Ranking Timer"
        )
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "Rebuild even when the WCA export "
            "date and local data schema "
            "are unchanged"
        )
    )

    args = parser.parse_args()

    print(
        "Checking WCA export..."
    )

    api_info = fetch_json(
        API_URL
    )

    export_date = api_info.get(
        "export_date"
    )

    export_version = api_info.get(
        "export_version",
        ""
    )

    tsv_url = api_info.get(
        "tsv_url"
    )

    print(
        "WCA export:",
        export_date
    )

    print(
        "Format:",
        export_version
    )

    if not tsv_url:

        raise RuntimeError(
            "WCA API did not provide tsv_url."
        )

    if (
        export_version
        and
        not export_version.startswith(
            "v2."
        )
    ):

        raise RuntimeError(
            "Unsupported WCA export version: "
            +
            export_version
        )

    current_manifest = load_json(
        DATA_DIR /
        "manifest.json"
    )

    current_export_date = (

        current_manifest.get(
            "export_date"
        )

        if current_manifest

        else

        None

    )

    current_schema_version = (

        current_manifest.get(
            "data_schema_version"
        )

        if current_manifest

        else

        None

    )

    if (

        not args.force

        and

        current_manifest

        and

        current_export_date
        ==
        export_date

        and

        current_schema_version
        ==
        DATA_SCHEMA_VERSION

    ):

        print()

        print(
            "No new WCA export "
            "and data schema is current."
        )

        print(
            "Nothing to update."
        )

        return

    if (

        current_export_date
        ==
        export_date

        and

        current_schema_version
        !=
        DATA_SCHEMA_VERSION

    ):

        print()

        print(
            "Processor data schema changed."
        )

        print(
            "Rebuilding from the "
            "current WCA export."
        )

    with tempfile.TemporaryDirectory() as temp:

        zip_path = (
            Path(temp) /
            "wca-export.zip"
        )

        download_file(
            tsv_url,
            zip_path
        )

        build(
            zip_path,
            api_info
        )


if __name__ == "__main__":

    try:

        main()

    except KeyboardInterrupt:

        print()

        print(
            "Cancelled."
        )

        sys.exit(1)

    except Exception as error:

        print()

        print(
            "ERROR:"
        )

        print(
            error
        )

        sys.exit(1)
