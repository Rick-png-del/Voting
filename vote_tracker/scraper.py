import html
import json
import math
import re
import time
import urllib.parse
import urllib.request


class ScrapeError(RuntimeError):
    pass


_START_TIME = time.time()


def fetch_votes(config):
    source = config.get("source", {})
    source_type = source.get("type", "sample")

    if source_type == "sample":
        return _sample_votes()
    if source_type == "hupu_vote_detail":
        return _hupu_vote_detail_votes(source)
    if source_type == "http_regex":
        return _http_regex_votes(source)

    raise ScrapeError(f"Unsupported source.type: {source_type}")


def _sample_votes():
    tick = int((time.time() - _START_TIME) / 30)
    names = ["Alice", "Bob", "Cindy", "David"]
    base_votes = [1210, 980, 770, 650]
    votes = []

    for index, name in enumerate(names):
        wave = int(math.sin(tick / (index + 2)) * 18)
        trend = tick * (index + 1)
        votes.append({"name": name, "votes": base_votes[index] + trend + wave})

    return votes


def _http_regex_votes(source):
    url = source.get("url")
    if not url:
        raise ScrapeError("source.url is required when source.type is http_regex")

    headers = source.get("headers", {})
    request = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            body = response.read().decode(charset, errors="replace")
    except Exception as exc:
        raise ScrapeError(f"Failed to fetch {url}: {exc}") from exc

    pattern = source.get("regex", {}).get("item_pattern")
    if not pattern:
        raise ScrapeError("source.regex.item_pattern is required")

    try:
        compiled = re.compile(pattern, re.IGNORECASE | re.DOTALL)
    except re.error as exc:
        raise ScrapeError(f"Invalid regex pattern: {exc}") from exc

    rows = []
    for match in compiled.finditer(body):
        group = match.groupdict()
        name = _clean_text(group.get("name", ""))
        votes = _parse_votes(group.get("votes", ""))
        if name and votes is not None:
            rows.append({"name": name, "votes": votes})

    if not rows:
        raise ScrapeError("No vote rows matched the configured regex")

    return rows


def _hupu_vote_detail_votes(source):
    activity_id = source.get("activity_id")
    if not activity_id:
        raise ScrapeError("source.activity_id is required when source.type is hupu_vote_detail")

    api_url = source.get(
        "api_url",
        "https://bbsactivity.hupu.com/bbsactivityapi/activity/vote/detail",
    )
    url = _with_query(api_url, {"activityId": activity_id})
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json,text/plain,*/*",
    }
    headers.update(source.get("headers", {}))

    payload = _fetch_json_with_retries(
        url,
        headers=headers,
        timeout=20,
        attempts=3,
        pause_seconds=3,
        label="Hupu vote detail",
    )

    if not payload.get("succeed") and payload.get("code") not in (0, 1):
        raise ScrapeError(f"Hupu API returned error: {payload.get('msg') or payload}")

    groups = payload.get("data", {}).get("groups", [])
    selected_groups = _select_hupu_groups(
        groups,
        group_id=source.get("group_id"),
        group_name=source.get("group_name"),
    )

    if not selected_groups:
        raise ScrapeError("No Hupu vote group matched source.group_id or source.group_name")

    include_group_name = bool(source.get("include_group_name", False))
    rows = []
    candidate_names = _candidate_name_set(source)
    for group in selected_groups:
        group_name = str(group.get("name", "")).strip()
        for item in group.get("items", []):
            name = str(item.get("name", "")).strip()
            votes = item.get("voteNum")
            if not name or votes is None:
                continue
            if candidate_names and name not in candidate_names:
                continue
            if include_group_name and group_name:
                name = f"{group_name} / {name}"
            rows.append({"name": name, "votes": int(votes)})

    if not rows:
        raise ScrapeError("Hupu vote detail returned no vote rows")

    return rows


def _candidate_name_set(source):
    names = source.get("candidate_names", [])
    return {str(name).strip() for name in names if str(name).strip()}


def _select_hupu_groups(groups, group_id=None, group_name=None):
    selected = []

    for group in groups:
        if _hupu_group_matches(group, group_id, group_name):
            selected.append(group)
        selected.extend(
            _select_hupu_groups(
                group.get("subGroups", []),
                group_id=group_id,
                group_name=group_name,
            )
        )

    if group_id is None and group_name is None:
        return groups

    return selected


def _hupu_group_matches(group, group_id, group_name):
    if group_id is not None and str(group.get("id")) == str(group_id):
        return True
    if group_name is not None and str(group.get("name", "")).strip() == str(group_name):
        return True
    return group_id is None and group_name is None


def _with_query(url, values):
    parsed = urllib.parse.urlparse(url)
    query = dict(urllib.parse.parse_qsl(parsed.query))
    query.update({key: str(value) for key, value in values.items()})
    return urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(query)))


def _fetch_json_with_retries(url, headers=None, timeout=20, attempts=3, pause_seconds=3, label="JSON"):
    last_exc = None
    for attempt in range(1, attempts + 1):
        try:
            request = urllib.request.Request(url, headers=headers or {})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                return json.loads(response.read().decode(charset, errors="replace"))
        except Exception as exc:
            last_exc = exc
            if attempt == attempts:
                break
            time.sleep(pause_seconds * attempt)

    raise ScrapeError(f"Failed to fetch {label}: {last_exc}") from last_exc


def _clean_text(value):
    value = re.sub(r"<[^>]+>", "", value)
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def _parse_votes(value):
    if value is None:
        return None
    digits = re.sub(r"[^\d]", "", html.unescape(value))
    return int(digits) if digits else None
