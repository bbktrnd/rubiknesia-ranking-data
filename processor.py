#!/usr/bin/env python3

import argparse
import csv
import io
import json
import random
import shutil
import sys
import tempfile
import urllib.request
import zipfile

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


# ============================================================
# RUBIKNESIA RANKING TIMER
# WCA DATA PROCESSOR
# ============================================================

API_URL = (
    "https://www.worldcubeassociation.org/"
    "api/v0/export/public"
)

DATA_DIR = Path("data")

MAX_SCRAMBLES_PER_EVENT = 5000

SCRAMBLES_PER_FILE = 250


# ============================================================
# EVENTS
# ============================================================

SUPPORTED_EVENTS = {

    "222": {
        "name": "2x2 Cube",
        "format": "time"
    },

    "333": {
        "name": "3x3 Cube",
        "format": "time"
    },

    "444": {
        "name": "4x4 Cube",
        "format": "time"
    },

    "555": {
        "name": "5x5 Cube",
        "format": "time"
    },

    "666": {
        "name": "6x6 Cube",
        "format": "time"
    },

    "777": {
        "name": "7x7 Cube",
        "format": "time"
    },

    "333oh": {
        "name": "3x3 One-Handed",
        "format": "time"
    },

    "333bf": {
        "name": "3x3 Blindfolded",
        "format": "time"
    },

    "444bf": {
        "name": "4x4 Blindfolded",
        "format": "time"
    },

    "555bf": {
        "name": "5x5 Blindfolded",
        "format": "time"
    },

    "333fm": {
        "name": "3x3 Fewest Moves",
        "format": "number"
    },

    "333mbf": {
        "name": "3x3 Multi-Blind",
        "format": "multi"
    },

    "clock": {
        "name": "Clock",
        "format": "time"
    },

    "minx": {
        "name": "Megaminx",
        "format": "time"
    },

    "pyram": {
        "name": "Pyraminx",
        "format": "time"
    },

    "skewb": {
        "name": "Skewb",
        "format": "time"
    },

    "sq1": {
        "name": "Square-1",
        "format": "time"
    },

    "333ft": {
        "name": "3x3 With Feet",
        "format": "time",
        "legacy": True
    }

}


# ============================================================
# JSON
# ============================================================

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


# ============================================================
# DOWNLOAD
# ============================================================

def fetch_json(url):

    request = urllib.request.Request(

        url,

        headers={

            "User-Agent":
                "Rubiknesia-Ranking-Timer/1.0"

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

    print(
        url
    )

    request = urllib.request.Request(

        url,

        headers={

            "User-Agent":
                "Rubiknesia-Ranking-Timer/1.0"

        }

    )

    with urllib.request.urlopen(
        request,
        timeout=600
    ) as response:

        total = response.headers.get(
            "Content-Length"
        )

        if total:

            total = int(total)

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
                        "\r"
                        +
                        "Download: "
                        +
                        f"{percent:.1f}%",

                        end="",

                        flush=True
                    )

    print()

    print(
        "Download complete."
    )


# ============================================================
# ZIP HELPERS
# ============================================================

def find_table_file(
    zip_file,
    table_name
):

    table_name = (
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

        if not basename.endswith(
            ".tsv"
        ):

            continue

        if table_name in basename:

            candidates.append(
                filename
            )

    if not candidates:

        raise RuntimeError(

            "Cannot find TSV table: "
            +
            table_name

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


# ============================================================
# FIELD HELPERS
# ============================================================

def field(
    row,
    *names
):

    for name in names:

        if name in row:

            return row[name]

    return None


def integer(
    value,
    default=None
):

    try:

        return int(
            value
        )

    except Exception:

        return default


# ============================================================
# RANKING PROCESSOR
# ============================================================

def read_rankings(
    zip_file,
    table_name
):

    filename = find_table_file(

        zip_file,

        table_name

    )

    print(
        "Reading:",
        filename
    )

    values = {

        event: []

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

        if event not in values:

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

        values[event].append(
            best
        )

    return values


def compress_ranking(
    values
):

    if not values:

        return {

            "total": 0,

            "table": []

        }

    counter = Counter(
        values
    )

    total = 0

    table = []

    for value in sorted(
        counter
    ):

        total += counter[
            value
        ]

        table.append(
            [
                value,
                total
            ]
        )

    return {

        "total":
            len(values),

        "table":
            table

    }


# ============================================================
# SCRAMBLE PROCESSOR
# ============================================================

def read_scrambles(
    zip_file
):

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
                "rubiknesia-" +
                event
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

        totals[event] += 1

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
                )

        }

        if (
            MAX_SCRAMBLES_PER_EVENT
            <= 0
        ):

            samples[event].append(
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
                randomizers[event]
                .randrange(
                    totals[event]
                )
            )

            if (
                index
                <
                MAX_SCRAMBLES_PER_EVENT
            ):

                current[index] = (
                    record
                )

    return (
        samples,
        totals
    )


# ============================================================
# OUTPUT
# ============================================================

def write_rankings(
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

            "event":
                event,

            "name":
                config["name"],

            "format":
                config["format"],

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
                average

        }

        filename = (
            event +
            ".json"
        )

        save_json(

            ranking_dir /
            filename,

            payload

        )

        manifest_data[event] = {

            "file":
                "ranking/" +
                filename,

            "single_count":
                single["total"],

            "average_count":
                average["total"]

        }

    return manifest_data


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
                        shard
                }

            )

            files.append(
                filename
            )

        index = {

            "event":
                event,

            "name":
                config["name"],

            "source_total":
                totals.get(
                    event,
                    0
                ),

            "available":
                len(records),

            "per_file":
                SCRAMBLES_PER_FILE,

            "files":
                files

        }

        save_json(

            event_dir /
            "index.json",

            index,

            pretty=True

        )

        manifest_data[event] = {

            "index":
                "scrambles/"
                +
                event
                +
                "/index.json",

            "source_total":
                totals.get(
                    event,
                    0
                ),

            "available":
                len(records)

        }

    return manifest_data


# ============================================================
# BUILD
# ============================================================

def build(
    zip_path,
    api_info
):

    build_dir = Path(
        ".build-data"
    )

    if build_dir.exists():

        shutil.rmtree(
            build_dir
        )

    build_dir.mkdir(
        parents=True
    )

    print()

    print(
        "Opening WCA export..."
    )

    with zipfile.ZipFile(
        zip_path,
        "r"
    ) as zip_file:

        single_rankings = (
            read_rankings(
                zip_file,
                "ranks_single"
            )
        )

        average_rankings = (
            read_rankings(
                zip_file,
                "ranks_average"
            )
        )

        (
            scramble_samples,
            scramble_totals

        ) = read_scrambles(
            zip_file
        )

    print()

    print(
        "Writing ranking JSON..."
    )

    ranking_manifest = (
        write_rankings(

            build_dir,

            single_rankings,

            average_rankings,

            api_info[
                "export_date"
            ]

        )
    )

    print(
        "Writing scramble JSON..."
    )

    scramble_manifest = (
        write_scrambles(

            build_dir,

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

    export_date = api_info.get(
        "export_date"
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
        else "unknown"
    )

    attribution = (

        "This information is based on "
        "competition results owned and "
        "maintained by the World Cube "
        "Association, published at "
        "https://worldcubeassociation.org/results "
        "as of "
        +
        date_only
        +
        "."

    )

    manifest = {

        "project":
            "Rubiknesia Ranking Timer",

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

        "scramble_sample_limit":
            (
                MAX_SCRAMBLES_PER_EVENT
            ),

        "scrambles_per_file":
            SCRAMBLES_PER_FILE,

        "events":
            SUPPORTED_EVENTS,

        "ranking":
            ranking_manifest,

        "scrambles":
            scramble_manifest

    }

    save_json(

        build_dir /
        "manifest.json",

        manifest,

        pretty=True

    )

    if DATA_DIR.exists():

        shutil.rmtree(
            DATA_DIR
        )

    shutil.move(

        str(build_dir),

        str(DATA_DIR)

    )

    print()

    print(
        "======================================"
    )

    print(
        "Rubiknesia WCA data build complete."
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


# ============================================================
# MAIN
# ============================================================

def main():

    parser = argparse.ArgumentParser(

        description=(
            "Generate lightweight "
            "WCA data for "
            "Rubiknesia Ranking Timer"
        )

    )

    parser.add_argument(

        "--force",

        action="store_true",

        help=(
            "Rebuild even if the "
            "export date has not changed"
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

    if (
        not args.force
        and
        current_manifest
        and
        current_manifest.get(
            "export_date"
        )
        ==
        export_date
    ):

        print()

        print(
            "No new WCA export."
        )

        print(
            "Nothing to update."
        )

        return

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
