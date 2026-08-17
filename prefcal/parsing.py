from __future__ import annotations

import re

from .common import extract_json_object
from .tasks import FAMILY_IDS


def parse_identifier(text: str, valid_identifiers: list[str]):
    valid = [str(x).strip().upper() for x in valid_identifiers]
    obj = extract_json_object(text)
    if isinstance(obj, dict):
        for key in ('choice', 'answer', 'selected'):
            value = str(obj.get(key, '')).strip().upper()
            if value in valid:
                return value
    upper = text.strip().upper()
    for identifier in valid:
        if re.search(rf'(?<![A-Z0-9_]){re.escape(identifier)}(?![A-Z0-9_])', upper):
            return identifier
    return None


def parse_ranking(text: str):
    obj = extract_json_object(text)
    values = obj.get('ranking') if isinstance(obj, dict) else obj
    if isinstance(values, list):
        values = [str(x).strip().upper() for x in values]
        if len(values) == len(FAMILY_IDS) and set(values) == set(FAMILY_IDS):
            return values
    tokens = re.findall(r'DEBUG|MATH|CREATIVE|REFLECT|TRANSFORM', text.upper())
    seen = []
    for token in tokens:
        if token not in seen:
            seen.append(token)
    return seen if len(seen) == len(FAMILY_IDS) else None


def parse_allocation(text: str):
    obj = extract_json_object(text)
    if isinstance(obj, dict) and isinstance(obj.get('allocation'), dict):
        obj = obj['allocation']
    if not isinstance(obj, dict):
        return None
    try:
        out = {fam: int(obj[fam]) for fam in FAMILY_IDS}
    except Exception:
        return None
    if set(obj) != set(FAMILY_IDS) or any(value < 0 for value in out.values()) or sum(out.values()) != 100:
        return None
    return out
