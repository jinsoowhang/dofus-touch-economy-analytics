from __future__ import annotations

import json
import time
from collections import defaultdict
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from dofus_touch_economy.models import Item
from dofus_touch_economy.normalization import normalize_item_name

TOUCH_CONFIG_URL = "https://dt-proxy-production-login.ankama-games.com/config.json?lang=en"
DOFUSDB_ITEMS_URL = "https://api.dofusdb.fr/items"
DOFUSWIKI_API_URL = "https://dofuswiki.fandom.com/api.php"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
USER_AGENT = "DofusTouchEconomy/0.1 item-icon-cache"
FALLBACK_BATCH_SIZE = 20
LEGACY_NAME_ALIASES = {
    "barleys": "Barley",
    "bethel akama's tail": "Bethel Akarna's Tail",
    "bloodly koalak tail": "Bloody Koalak Tuft",
    "bloody koalak tail": "Bloody Koalak Tuft",
    "boowonoke hairs": "Boowonoké Hairs",
    "dark treechnid seed": "Dark Treeckler Seed",
    "fouxnambalist hairs": "Fouxnamballist Hairs",
    "perfect little vulkarian backpack": "Perfect Little Vulkanian Backpack",
    "pingwinch stemum": "Pingwinch Sternum",
    "shredded dragoalak headgear": "Shredded Drakoalak Headgear",
    "spifoux skin": "Spitfoux Skin",
    "spiritabbly tail": "Spiritabby Tail",
    "tanukoui san essence": "Tanukouï San Essence",
    "tanukoui san testicles": "Tanukouï San Testicles",
    "tanukoui san's workshop key": "Tanukouï San's Workshop Key",
    "tokokoko leaf": "Rokoko Leaf",
    "tuf of siks-t hair": "Tuft of Siks-T Hair",
    "wind pandawushu artifact": "Wind Pandawushu Artefact",
    "zoth abacuz": "Zoth Abacus",
}

JsonFetcher = Callable[[str, dict[str, str] | None], Any]
BytesFetcher = Callable[[str], bytes]


@dataclass(frozen=True)
class IconFetchSummary:
    catalog_count: int
    cached_count: int
    touch_match_count: int
    fallback_match_count: int
    wiki_match_count: int
    ambiguous_match_count: int
    downloaded_count: int
    missing_names: tuple[str, ...]
    failed_names: tuple[str, ...]


@dataclass(frozen=True)
class _Target:
    item_id: int
    uuid: UUID
    display_name: str
    normalized_name: str
    icon_source_url: str | None


@dataclass(frozen=True)
class _Candidate:
    item_id: int
    icon_id: int
    normalized_name: str
    source_url: str
    source: str


def fetch_item_icons(
    session_factory: sessionmaker[Session],
    icon_directory: Path,
    *,
    refresh: bool = False,
    max_workers: int = 8,
    json_fetcher: JsonFetcher | None = None,
    bytes_fetcher: BytesFetcher | None = None,
) -> IconFetchSummary:
    if max_workers < 1:
        raise ValueError("max_workers must be positive")
    fetch_json = json_fetcher or _fetch_json
    fetch_bytes = bytes_fetcher or _fetch_bytes
    targets = _load_targets(session_factory)
    icon_directory.mkdir(parents=True, exist_ok=True)

    cached = [
        target
        for target in targets
        if not refresh
        and target.icon_source_url is not None
        and _icon_path(icon_directory, target.uuid).is_file()
    ]
    pending = [target for target in targets if target not in cached]

    config = fetch_json(TOUCH_CONFIG_URL, None)
    data_url = _trusted_config_url(config, "dataUrl", ".ankama-games.com")
    assets_url = _trusted_config_url(config, "assetsUrl", ".ankama.com")
    touch_payload = fetch_json(
        f"{data_url.rstrip('/')}/data/map",
        {"class": "Items", "lang": "en"},
    )
    touch_candidates = _touch_candidates(touch_payload, f"{assets_url.rstrip('/')}/gfx/items")

    assignments: dict[int, _Candidate] = {}
    ambiguous_count = 0
    fallback_targets: list[_Target] = []
    for target in pending:
        candidates = _candidates_for_target(touch_candidates, target)
        if not candidates:
            fallback_targets.append(target)
            continue
        candidate, was_ambiguous = _choose_candidate(candidates)
        assignments[target.item_id] = candidate
        ambiguous_count += int(was_ambiguous)

    fallback_candidates = _fallback_candidates(fallback_targets, fetch_json)
    wiki_targets: list[_Target] = []
    for target in fallback_targets:
        candidates = _candidates_for_target(fallback_candidates, target)
        if not candidates:
            wiki_targets.append(target)
            continue
        candidate, was_ambiguous = _choose_candidate(candidates)
        assignments[target.item_id] = candidate
        ambiguous_count += int(was_ambiguous)

    wiki_candidates = _wiki_candidates(wiki_targets, fetch_json)
    missing_names: list[str] = []
    for target in wiki_targets:
        candidates = _candidates_for_target(wiki_candidates, target)
        if not candidates:
            missing_names.append(target.display_name)
            continue
        candidate, was_ambiguous = _choose_candidate(candidates)
        assignments[target.item_id] = candidate
        ambiguous_count += int(was_ambiguous)

    pending_by_id = {target.item_id: target for target in pending}
    successful_sources: dict[int, str] = {}
    failed_names: list[str] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                _download_icon,
                fetch_bytes,
                candidate.source_url,
                _icon_path(icon_directory, pending_by_id[item_id].uuid),
            ): item_id
            for item_id, candidate in assignments.items()
        }
        for future in as_completed(futures):
            item_id = futures[future]
            target = pending_by_id[item_id]
            try:
                future.result()
            except (HTTPError, URLError, OSError, ValueError):
                failed_names.append(target.display_name)
            else:
                successful_sources[item_id] = assignments[item_id].source_url

    _record_sources(session_factory, successful_sources)
    touch_match_count = sum(candidate.source == "touch" for candidate in assignments.values())
    fallback_match_count = sum(candidate.source == "dofusdb" for candidate in assignments.values())
    wiki_match_count = sum(candidate.source == "dofuswiki" for candidate in assignments.values())
    return IconFetchSummary(
        catalog_count=len(targets),
        cached_count=len(cached),
        touch_match_count=touch_match_count,
        fallback_match_count=fallback_match_count,
        wiki_match_count=wiki_match_count,
        ambiguous_match_count=ambiguous_count,
        downloaded_count=len(successful_sources),
        missing_names=tuple(sorted(missing_names)),
        failed_names=tuple(sorted(failed_names)),
    )


def _load_targets(session_factory: sessionmaker[Session]) -> list[_Target]:
    with session_factory() as session:
        rows = session.execute(
            select(
                Item.id,
                Item.uuid,
                Item.display_name,
                Item.normalized_name,
                Item.icon_source_url,
            ).order_by(Item.normalized_name, Item.id)
        )
        return [_Target(*row) for row in rows]


def _touch_candidates(payload: Any, assets_url: str) -> dict[str, list[_Candidate]]:
    if not isinstance(payload, dict):
        raise ValueError("Dofus Touch item payload must be an object")
    candidates: defaultdict[str, list[_Candidate]] = defaultdict(list)
    for value in payload.values():
        if not isinstance(value, dict):
            continue
        _append_candidate(
            candidates,
            value.get("id"),
            value.get("iconId"),
            value.get("nameId"),
            assets_url,
            "touch",
        )
    return dict(candidates)


def _fallback_candidates(
    targets: list[_Target],
    fetch_json: JsonFetcher,
) -> dict[str, list[_Candidate]]:
    names = sorted({_query_name(target) for target in targets})
    candidates: defaultdict[str, list[_Candidate]] = defaultdict(list)
    for start in range(0, len(names), FALLBACK_BATCH_SIZE):
        batch = names[start : start + FALLBACK_BATCH_SIZE]
        skip = 0
        while True:
            parameters = [
                ("$limit", "50"),
                ("$skip", str(skip)),
                ("$select[]", "id"),
                ("$select[]", "iconId"),
                ("$select[]", "name"),
                *(("name.en[$in][]", name) for name in batch),
            ]
            payload = fetch_json(f"{DOFUSDB_ITEMS_URL}?{urlencode(parameters)}", None)
            if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
                raise ValueError("DofusDB item payload must contain a data list")
            rows = payload["data"]
            for value in rows:
                if not isinstance(value, dict):
                    continue
                localized_names = value.get("name")
                english_name = (
                    localized_names.get("en") if isinstance(localized_names, dict) else None
                )
                _append_candidate(
                    candidates,
                    value.get("id"),
                    value.get("iconId"),
                    english_name,
                    "https://api.dofusdb.fr/img/items",
                    "dofusdb",
                )
            skip += len(rows)
            total = payload.get("total")
            if not rows or not isinstance(total, int) or skip >= total:
                break
    return dict(candidates)


def _wiki_candidates(
    targets: list[_Target],
    fetch_json: JsonFetcher,
) -> dict[str, list[_Candidate]]:
    names = sorted({_query_name(target) for target in targets})
    candidates: defaultdict[str, list[_Candidate]] = defaultdict(list)
    for start in range(0, len(names), FALLBACK_BATCH_SIZE):
        batch = names[start : start + FALLBACK_BATCH_SIZE]
        parameters = [
            ("action", "query"),
            ("format", "json"),
            ("formatversion", "2"),
            ("prop", "pageimages"),
            ("piprop", "original"),
            ("redirects", "1"),
            ("titles", "|".join(batch)),
        ]
        payload = fetch_json(f"{DOFUSWIKI_API_URL}?{urlencode(parameters)}", None)
        query = payload.get("query") if isinstance(payload, dict) else None
        pages = query.get("pages") if isinstance(query, dict) else None
        if not isinstance(pages, list):
            raise ValueError("Dofus Wiki payload must contain a pages list")
        aliases: defaultdict[str, set[str]] = defaultdict(set)
        redirects = query.get("redirects", [])
        if isinstance(redirects, list):
            for redirect in redirects:
                if not isinstance(redirect, dict):
                    continue
                source_title = redirect.get("from")
                target_title = redirect.get("to")
                if isinstance(source_title, str) and isinstance(target_title, str):
                    aliases[normalize_item_name(target_title)].add(
                        normalize_item_name(source_title)
                    )
        for page in pages:
            if not isinstance(page, dict) or "missing" in page:
                continue
            title = page.get("title")
            original = page.get("original")
            source_url = original.get("source") if isinstance(original, dict) else None
            page_id = page.get("pageid")
            if (
                not isinstance(title, str)
                or not isinstance(source_url, str)
                or not isinstance(page_id, int)
                or not _is_trusted_wiki_image(source_url)
            ):
                continue
            normalized_name = normalize_item_name(title)
            for candidate_name in {normalized_name, *aliases[normalized_name]}:
                candidates[candidate_name].append(
                    _Candidate(
                        item_id=page_id,
                        icon_id=page_id,
                        normalized_name=candidate_name,
                        source_url=_original_wiki_url(source_url),
                        source="dofuswiki",
                    )
                )
    missing_names = [name for name in names if normalize_item_name(name) not in candidates]
    for start in range(0, len(missing_names), FALLBACK_BATCH_SIZE):
        batch = missing_names[start : start + FALLBACK_BATCH_SIZE]
        parameters = [
            ("action", "query"),
            ("format", "json"),
            ("formatversion", "2"),
            ("prop", "imageinfo"),
            ("iiprop", "url"),
            ("titles", "|".join(f"File:{name}.png" for name in batch)),
        ]
        payload = fetch_json(f"{DOFUSWIKI_API_URL}?{urlencode(parameters)}", None)
        query = payload.get("query") if isinstance(payload, dict) else None
        pages = query.get("pages") if isinstance(query, dict) else None
        if not isinstance(pages, list):
            raise ValueError("Dofus Wiki image payload must contain a pages list")
        for page in pages:
            if not isinstance(page, dict) or "missing" in page:
                continue
            title = page.get("title")
            image_info = page.get("imageinfo")
            source_url = (
                image_info[0].get("url")
                if isinstance(image_info, list) and image_info and isinstance(image_info[0], dict)
                else None
            )
            page_id = page.get("pageid")
            if (
                not isinstance(title, str)
                or not title.startswith("File:")
                or not title.casefold().endswith(".png")
                or not isinstance(source_url, str)
                or not isinstance(page_id, int)
                or not _is_trusted_wiki_image(source_url)
            ):
                continue
            normalized_name = normalize_item_name(title.removeprefix("File:")[:-4])
            candidates[normalized_name].append(
                _Candidate(
                    item_id=page_id,
                    icon_id=page_id,
                    normalized_name=normalized_name,
                    source_url=_original_wiki_url(source_url),
                    source="dofuswiki",
                )
            )
    return dict(candidates)


def _query_name(target: _Target) -> str:
    return LEGACY_NAME_ALIASES.get(target.normalized_name, target.display_name)


def _candidates_for_target(
    candidates: dict[str, list[_Candidate]],
    target: _Target,
) -> list[_Candidate]:
    direct = candidates.get(target.normalized_name, [])
    if direct:
        return direct
    return candidates.get(normalize_item_name(_query_name(target)), [])


def _original_wiki_url(source_url: str) -> str:
    separator = "&" if "?" in source_url else "?"
    return f"{source_url}{separator}format=original"


def _append_candidate(
    candidates: defaultdict[str, list[_Candidate]],
    item_id: object,
    icon_id: object,
    name: object,
    base_url: str,
    source: str,
) -> None:
    if (
        not isinstance(item_id, int)
        or not isinstance(icon_id, int)
        or not isinstance(name, str)
        or not name.strip()
    ):
        return
    normalized_name = normalize_item_name(name)
    candidates[normalized_name].append(
        _Candidate(
            item_id=item_id,
            icon_id=icon_id,
            normalized_name=normalized_name,
            source_url=f"{base_url.rstrip('/')}/{icon_id}.png",
            source=source,
        )
    )


def _choose_candidate(candidates: list[_Candidate]) -> tuple[_Candidate, bool]:
    ordered = sorted(candidates, key=lambda candidate: (candidate.item_id, candidate.icon_id))
    return ordered[0], len({candidate.source_url for candidate in ordered}) > 1


def _download_icon(fetch_bytes: BytesFetcher, source_url: str, destination: Path) -> None:
    content = fetch_bytes(source_url)
    if not content.startswith(PNG_SIGNATURE):
        raise ValueError("item icon response is not a PNG")
    temporary_path = destination.with_suffix(".png.tmp")
    temporary_path.write_bytes(content)
    temporary_path.replace(destination)


def _record_sources(
    session_factory: sessionmaker[Session],
    successful_sources: dict[int, str],
) -> None:
    if not successful_sources:
        return
    with session_factory() as session:
        items = session.scalars(select(Item).where(Item.id.in_(successful_sources))).all()
        for item in items:
            item.icon_source_url = successful_sources[item.id]
        session.commit()


def _icon_path(icon_directory: Path, item_uuid: UUID) -> Path:
    return icon_directory / f"{item_uuid}.png"


def _trusted_config_url(config: Any, key: str, host_suffix: str) -> str:
    if not isinstance(config, dict) or not isinstance(config.get(key), str):
        raise ValueError(f"Dofus Touch config is missing {key}")
    value = config[key]
    parsed = urlparse(value)
    hostname = parsed.hostname or ""
    if parsed.scheme != "https" or not hostname.endswith(host_suffix):
        raise ValueError(f"Dofus Touch config returned an untrusted {key}")
    return value


def _is_trusted_wiki_image(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "https" and parsed.hostname == "static.wikia.nocookie.net"


def _fetch_json(url: str, payload: dict[str, str] | None) -> Any:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Accept": "application/json", "User-Agent": USER_AGENT}
    if data is not None:
        headers["Content-Type"] = "application/json"
    return json.loads(_request(url, data=data, headers=headers).decode("utf-8"))


def _fetch_bytes(url: str) -> bytes:
    return _request(url, data=None, headers={"Accept": "image/png", "User-Agent": USER_AGENT})


def _request(url: str, *, data: bytes | None, headers: dict[str, str]) -> bytes:
    for attempt in range(3):
        try:
            with urlopen(Request(url, data=data, headers=headers), timeout=30) as response:
                return response.read()
        except (HTTPError, URLError):
            if attempt == 2:
                raise
            time.sleep(0.5 * (attempt + 1))
    raise RuntimeError("unreachable")
