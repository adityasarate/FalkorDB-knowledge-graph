"""
PEP Corpus Parser for Company Brain on FalkorDB (Schema v1.1).

Parses 744 PEP reStructuredText files into structured nodes and relationships
according to the governance specification in Company_Brain.md:
- Nodes: PEP, Person, Section, Release, Venue
- Links: WROTE, DELEGATE_FOR, SPONSORED, HAS_SECTION, REPLACES, CITES, REQUIRES,
         TARGETS_RELEASE, DISCUSSED_IN, CO_WROTE_WITH
"""

import os
import re
import sys
import glob
import json
import hashlib
import unicodedata
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime
from dateutil import parser as date_parser

# Known non-person strings found in Author / Delegate / Sponsor headers
NON_PERSONS = {
    'the python core team and community',
    'the python core team',
    'community',
    'c api working group',
    'steering council',
    'python steering council',
    'todo',
}

# Known aliases across author, sponsor, and delegate headers (D23)
ALIAS_TABLE = {
    'seth larson': 'seth michael larson',
    'mariatta': 'mariatta wijaya',
}

def normalize_text(text: str) -> str:
    """Folds accents to ASCII equivalents using Unicode NFKD."""
    text = unicodedata.normalize('NFKD', text)
    return "".join(c for c in text if not unicodedata.combining(c))

def make_person_key(name: str) -> str:
    """
    Computes a repeatable unique key for a Person:
    Removes email, parentheticals, Jr., folds accents, and applies alias resolution.
    """
    clean = re.sub(r'<[^>]+>', '', name)
    clean = re.sub(r'\([^)]+\)', '', clean)
    clean = normalize_text(clean).lower()
    clean = re.sub(r'\bjr\.?\b', '', clean).strip()
    clean = re.sub(r'[\.,]', '', clean).strip()
    clean = re.sub(r'\s+', ' ', clean).strip()
    return ALIAS_TABLE.get(clean, clean)

def clean_person_name(name: str) -> str:
    """Returns display name with emails and brackets removed."""
    clean = re.sub(r'<[^>]+>', '', name)
    clean = re.sub(r'\([^)]+\)', '', clean)
    return re.sub(r'\s+', ' ', clean).strip()

def parse_header_block(content: str) -> Tuple[Dict[str, str], str]:
    """
    Parses RFC 822 style headers from the beginning of a PEP file.
    Returns (headers_dict, body_text).
    """
    lines = content.splitlines()
    headers = {}
    cur_key = None
    cur_val = []
    body_start_idx = 0

    for i, line in enumerate(lines):
        if not line.strip():
            if cur_key:
                headers[cur_key] = " ".join(cur_val).strip()
            body_start_idx = i + 1
            break
        m = re.match(r'^([A-Za-z\-]+):\s*(.*)$', line)
        if m:
            if cur_key:
                headers[cur_key] = " ".join(cur_val).strip()
            cur_key = m.group(1)
            cur_val = [m.group(2).strip()]
        elif cur_key and line.startswith((' ', '\t')):
            cur_val.append(line.strip())
        else:
            if cur_key:
                headers[cur_key] = " ".join(cur_val).strip()
            body_start_idx = i
            break

    body = "\n".join(lines[body_start_idx:])
    return headers, body

def parse_pep_numbers(raw: str) -> List[int]:
    """Extracts integer PEP numbers from headers like Replaces, Requires, etc."""
    if not raw:
        return []
    nums = []
    for token in re.split(r'[,;\s]+', raw):
        token = token.strip()
        if token.isdigit():
            nums.append(int(token))
    return sorted(list(set(nums)))

def parse_release_versions(raw: str) -> List[str]:
    """
    Parses and normalizes target Python versions from Python-Version header.
    Normalizes '2.7.9, 3.4.3, 3.5' -> ['2.7', '3.4', '3.5'].
    """
    if not raw:
        return []
    versions = set()
    for token in re.split(r'[,;\s]+', raw):
        token = token.strip().rstrip('.')
        m = re.match(r'^(\d+\.\d+)', token)
        if m:
            versions.add(m.group(1))
    return sorted(list(versions))

def parse_venue(raw: str) -> Optional[Dict[str, str]]:
    """
    Parses Discussions-To header into a Venue node representation:
    - forum: discuss.python.org thread URL
    - mailing_list: mail.python.org archive URL or email address
    """
    if not raw:
        return None
    raw = raw.strip()
    if raw.lower() in ['pending', 'tbd', 'none', 'n/a', '']:
        return None

    first_url_m = re.search(r'https?://[^\s>]+', raw)
    if first_url_m:
        url = first_url_m.group(0).rstrip('`_>')
        if 'discuss.python.org' in url:
            return {'name': 'discuss.python.org', 'kind': 'forum', 'url': url}
        elif 'mail.python.org' in url:
            return {'name': 'mail.python.org', 'kind': 'mailing_list', 'url': url}
        else:
            domain = re.sub(r'^https?://([^/]+).*', r'\1', url)
            return {'name': domain, 'kind': 'forum', 'url': url}

    # Check for mailing list email (e.g. distutils-sig@python.org)
    email_m = re.search(r'([A-Za-z0-9\._\-]+@[A-Za-z0-9\._\-]+)', raw)
    if email_m:
        addr = email_m.group(1).lower()
        return {'name': addr, 'kind': 'mailing_list', 'url': ''}

    return {'name': raw.lower(), 'kind': 'mailing_list', 'url': ''}

def extract_sections(body: str, pep_number: int) -> List[Dict[str, Any]]:
    """
    Extracts high-signal section nodes from PEP body text:
    - abstract
    - motivation
    - rationale
    - rejection_notice
    """
    lines = body.splitlines()
    headings = []
    for i in range(len(lines) - 1):
        line = lines[i].strip()
        next_line = lines[i+1].strip()
        if line and next_line and len(next_line) >= len(line) and len(set(next_line)) == 1 and next_line[0] in '=-~`:^"*+#_<>':
            headings.append((i, line))

    found_sections = {}
    for idx, (line_idx, heading_text) in enumerate(headings):
        h_norm = heading_text.lower().strip()
        kind = None
        if h_norm == 'abstract':
            kind = 'abstract'
        elif h_norm == 'motivation':
            kind = 'motivation'
        elif h_norm == 'rationale':
            kind = 'rationale'
        elif h_norm in ['rejection notice', 'rejection', 'notice of rejection', 'why this pep was rejected']:
            kind = 'rejection_notice'

        if kind and kind not in found_sections:
            start_line = line_idx + 2
            end_line = headings[idx+1][0] if idx + 1 < len(headings) else len(lines)
            sec_text = "\n".join(lines[start_line:end_line]).strip()
            # Non-trivial text threshold per Company_Brain.md
            if len(sec_text) >= 55:
                anchor = re.sub(r'[^a-z0-9]+', '-', h_norm).strip('-')
                sec_id = f"{pep_number}:{kind}"
                url = f"https://peps.python.org/pep-{pep_number:04d}/#{anchor}"
                found_sections[kind] = {
                    'id': sec_id,
                    'pep_number': pep_number,
                    'kind': kind,
                    'title': heading_text,
                    'anchor': anchor,
                    'url': url,
                    'text': sec_text,
                    'chars': len(sec_text)
                }

    return list(found_sections.values())

def extract_cites(body: str, source_pep: int, valid_peps: Set[int]) -> List[int]:
    """
    Extracts distinct valid PEP numbers cited via the `:pep:` role.
    Handles Sphinx explicit target syntax (`:pep:`title <target>``).
    Self-citations are excluded per Company_Brain.md rules.
    """
    matches = re.findall(r':pep:`([^`]+)`', body)
    cited = set()
    for raw in matches:
        target_str = raw
        angle_m = re.search(r'<([^>]+)>', raw)
        if angle_m:
            target_str = angle_m.group(1)
        target_str = target_str.split('#')[0]
        num_m = re.search(r'\b(\d+)\b', target_str)
        if num_m:
            target = int(num_m.group(1))
            if target != source_pep and target in valid_peps:
                cited.add(target)
    return sorted(list(cited))

def parse_persons_from_header(raw_header: str) -> List[Tuple[str, str]]:
    """
    Parses person names from an author / delegate / sponsor string.
    Protects 'Jr.' so suffixes like 'Fred L. Drake, Jr.' are not erroneously split.
    Returns a list of (display_name, unique_key).
    """
    if not raw_header:
        return []
    persons = []
    # Temporarily mask ', Jr.' or ', Jr' to avoid splitting
    masked = re.sub(r',\s*(Jr\.?)', r' __JR__', raw_header, flags=re.IGNORECASE)
    tokens = re.split(r',\s*|\s+and\s+', masked)
    for t in tokens:
        unmasked = t.replace('__JR__', 'Jr.').strip()
        name = clean_person_name(unmasked)
        if not name:
            continue
        key = make_person_key(name)
        if not key or key in NON_PERSONS or len(key) <= 1:
            continue
        persons.append((name, key))
    return persons

@dataclass
class ParsedPEP:
    number: int
    title: str
    status: str
    pep_type: str
    created: str
    url: str
    templated: bool
    resolution_url: str
    content_hash: str
    file_path: str
    authors: List[Tuple[str, str]] = field(default_factory=list)
    delegates: List[Tuple[str, str, str]] = field(default_factory=list)
    sponsors: List[Tuple[str, str]] = field(default_factory=list)
    replaces: List[int] = field(default_factory=list)
    superseded_by: List[int] = field(default_factory=list)
    requires: List[int] = field(default_factory=list)
    releases: List[str] = field(default_factory=list)
    raw_python_version: str = ""
    venue: Optional[Dict[str, str]] = None
    sections: List[Dict[str, Any]] = field(default_factory=list)
    cites: List[int] = field(default_factory=list)


def parse_all_peps(data_dir: str = "data/peps/peps") -> Dict[str, Any]:
    """
    Loads and parses all PEP files from the specified folder.
    Returns the complete structured graph entities and relationships.
    """
    files = sorted(glob.glob(os.path.join(data_dir, "pep-*.rst")))
    if not files:
        raise FileNotFoundError(f"No PEP files found in {data_dir}")

    # Pass 1: Gather file hashes and valid PEP numbers
    raw_peps = []
    valid_peps: Set[int] = set()

    for fpath in files:
        with open(fpath, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
        headers, body = parse_header_block(content)
        pep_str = headers.get("PEP", "")
        if not pep_str.isdigit():
            continue
        pep_num = int(pep_str)
        valid_peps.add(pep_num)
        raw_peps.append((fpath, content_hash, headers, body, pep_num))

    # Pass 2: Extract all structured entities and links
    parsed_peps: Dict[int, ParsedPEP] = {}
    persons: Dict[str, str] = {}
    venues: Dict[str, Dict[str, str]] = {}
    releases: Set[str] = set()

    wrote_links: Set[Tuple[str, int]] = set()
    delegate_links: Set[Tuple[str, int, str]] = set()
    sponsor_links: Set[Tuple[str, int]] = set()
    replaces_declarations: Dict[Tuple[int, int], Dict[str, bool]] = {}
    requires_links: Set[Tuple[int, int]] = set()
    targets_release_links: Set[Tuple[int, str, str]] = set()
    discussed_in_links: Set[Tuple[int, str, str]] = set()
    all_sections: List[Dict[str, Any]] = []
    cites_links: Set[Tuple[int, int]] = set()

    for fpath, content_hash, headers, body, pep_num in raw_peps:
        title = headers.get("Title", f"PEP {pep_num}").strip()

        status = headers.get("Status", "Draft").strip()
        if "april fool" in status.lower():
            status = "Rejected"

        pep_type = headers.get("Type", "Standards Track").strip()

        created_raw = headers.get("Created", "").strip()
        created_iso = "1970-01-01"
        if created_raw:
            try:
                dt = date_parser.parse(created_raw)
                created_iso = dt.strftime("%Y-%m-%d")
            except Exception:
                created_iso = created_raw

        url = f"https://peps.python.org/pep-{pep_num:04d}/"

        topic = headers.get("Topic", "").strip().lower()
        templated = (topic == "release" or "release schedule" in title.lower())

        res_header = headers.get("Resolution", "").strip()
        res_m = re.search(r'https?://[^\s>]+', res_header)
        resolution_url = res_m.group(0).rstrip('`_>') if res_m else ""

        # Authors (PEP 13 organization is excluded)
        authors = []
        if pep_num != 13:
            raw_authors = headers.get("Author", "")
            for name, key in parse_persons_from_header(raw_authors):
                authors.append((name, key))
                persons[key] = name
                wrote_links.add((key, pep_num))

        # Delegates
        delegates = []
        for header_name in ["BDFL-Delegate", "PEP-Delegate"]:
            raw_del = headers.get(header_name, "")
            for name, key in parse_persons_from_header(raw_del):
                delegates.append((name, key, header_name))
                persons[key] = name
                delegate_links.add((key, pep_num, header_name))

        # Sponsors
        sponsors = []
        raw_sponsor = headers.get("Sponsor", "")
        for name, key in parse_persons_from_header(raw_sponsor):
            sponsors.append((name, key))
            persons[key] = name
            sponsor_links.add((key, pep_num))

        # Replaces / Superseded-By
        replaces_list = [n for n in parse_pep_numbers(headers.get("Replaces", "")) if n in valid_peps]
        for old_pep in replaces_list:
            pair = (pep_num, old_pep)
            if pair not in replaces_declarations:
                replaces_declarations[pair] = {"by_new": False, "by_old": False}
            replaces_declarations[pair]["by_new"] = True

        superseded_list = [n for n in parse_pep_numbers(headers.get("Superseded-By", "")) if n in valid_peps]
        for new_pep in superseded_list:
            pair = (new_pep, pep_num)
            if pair not in replaces_declarations:
                replaces_declarations[pair] = {"by_new": False, "by_old": False}
            replaces_declarations[pair]["by_old"] = True

        # Requires
        requires_list = [n for n in parse_pep_numbers(headers.get("Requires", "")) if n in valid_peps]
        for req_pep in requires_list:
            requires_links.add((pep_num, req_pep))

        # Releases
        raw_py_ver = headers.get("Python-Version", "").strip()
        pep_releases = parse_release_versions(raw_py_ver)
        for rel in pep_releases:
            releases.add(rel)
            targets_release_links.add((pep_num, rel, raw_py_ver))

        # Venue
        venue_info = parse_venue(headers.get("Discussions-To", ""))
        if venue_info:
            v_name = venue_info["name"]
            venues[v_name] = {"name": v_name, "kind": venue_info["kind"]}
            discussed_in_links.add((pep_num, v_name, venue_info.get("url", "")))

        # Sections
        sections = extract_sections(body, pep_num)
        all_sections.extend(sections)

        # Citations
        cites = extract_cites(body, pep_num, valid_peps)
        for target_pep in cites:
            cites_links.add((pep_num, target_pep))

        pep_obj = ParsedPEP(
            number=pep_num,
            title=title,
            status=status,
            pep_type=pep_type,
            created=created_iso,
            url=url,
            templated=templated,
            resolution_url=resolution_url,
            content_hash=content_hash,
            file_path=fpath,
            authors=authors,
            delegates=delegates,
            sponsors=sponsors,
            replaces=replaces_list,
            superseded_by=superseded_list,
            requires=requires_list,
            releases=pep_releases,
            raw_python_version=raw_py_ver,
            venue=venue_info,
            sections=sections,
            cites=cites
        )
        parsed_peps[pep_num] = pep_obj

    # Derive CO_WROTE_WITH (bidirectional pairs with shared_pep counts)
    co_author_counts: Dict[Tuple[str, str], int] = {}
    for pep in parsed_peps.values():
        author_keys = sorted(list(set(k for _, k in pep.authors)))
        for i in range(len(author_keys)):
            for j in range(i + 1, len(author_keys)):
                k1, k2 = author_keys[i], author_keys[j]
                co_author_counts[(k1, k2)] = co_author_counts.get((k1, k2), 0) + 1

    co_wrote_links: List[Dict[str, Any]] = []
    for (k1, k2), shared_cnt in co_author_counts.items():
        co_wrote_links.append({'source': k1, 'target': k2, 'shared_peps': shared_cnt})
        co_wrote_links.append({'source': k2, 'target': k1, 'shared_peps': shared_cnt})

    final_replaces = []
    for (new_pep, old_pep), decl in replaces_declarations.items():
        by_new, by_old = decl["by_new"], decl["by_old"]
        if by_new and by_old:
            declared_in = "both"
        elif by_new:
            declared_in = "replaces"
        else:
            declared_in = "superseded_by"
        final_replaces.append({
            'newer': new_pep,
            'older': old_pep,
            'declared_in': declared_in,
            'by_new': by_new,
            'by_old': by_old
        })

    return {
        "nodes": {
            "peps": parsed_peps,
            "persons": persons,
            "venues": venues,
            "releases": releases,
            "sections": all_sections,
        },
        "links": {
            "wrote": wrote_links,
            "delegate_for": delegate_links,
            "sponsored": sponsor_links,
            "replaces": final_replaces,
            "requires": requires_links,
            "targets_release": targets_release_links,
            "discussed_in": discussed_in_links,
            "cites": cites_links,
            "co_wrote_with": co_wrote_links,
        }
    }


def main():
    print("=" * 70)
    print("PARSING PYTHON PEP CORPUS (Schema v1.1)")
    print("=" * 70)

    data_dir = "data/peps/peps"
    graph_data = parse_all_peps(data_dir)

    nodes = graph_data["nodes"]
    links = graph_data["links"]

    # Load expected counts for comparison
    expected_file = Path("eval/expected_counts.json")
    expected = {}
    if expected_file.exists():
        with open(expected_file, "r", encoding="utf-8") as f:
            expected = json.load(f)

    exp_nodes = expected.get("nodes", {})
    exp_links = expected.get("relationships", {})

    print("\n--- Extracted Node Counts ---")
    node_counts = {
        "PEP": len(nodes["peps"]),
        "Person": len(nodes["persons"]),
        "Section": len(nodes["sections"]),
        "Release": len(nodes["releases"]),
        "Venue": len(nodes["venues"]),
    }
    all_nodes_matched = True
    for label, count in node_counts.items():
        target = exp_nodes.get(label, "?")
        diff = count - target if isinstance(target, int) else "?"
        is_ok = (diff == 0)
        if not is_ok:
            all_nodes_matched = False
        status = "[OK]" if is_ok else f"[DIFF {diff:+d}]"
        print(f"  {status:<10} {label:<10} -> Parsed: {count:>5} | Expected: {target:>5}")

    print("\n--- Extracted Relationship Counts ---")
    link_counts = {
        "WROTE": len(links["wrote"]),
        "REPLACES": len(links["replaces"]),
        "CITES": len(links["cites"]),
        "HAS_SECTION": len(nodes["sections"]),
        "DELEGATE_FOR": len(links["delegate_for"]),
        "SPONSORED": len(links["sponsored"]),
        "REQUIRES": len(links["requires"]),
        "TARGETS_RELEASE": len(links["targets_release"]),
        "DISCUSSED_IN": len(links["discussed_in"]),
        "CO_WROTE_WITH": len(links["co_wrote_with"]),
    }
    all_links_matched = True
    for rel, count in link_counts.items():
        target = exp_links.get(rel, "?")
        diff = count - target if isinstance(target, int) else "?"
        is_ok = (diff == 0)
        if not is_ok:
            all_links_matched = False
        status = "[OK]" if is_ok else f"[DIFF {diff:+d}]"
        print(f"  {status:<10} {rel:<15} -> Parsed: {count:>5} | Expected: {target:>5}")

    print("\n" + "=" * 70)
    if all_nodes_matched and all_links_matched:
        print("[SUCCESS] 100% of Node and Relationship Counts Match Master Specification!")
    else:
        print("[AUDIT COMPLETED] Verified against Schema v1.1 targets.")
    print("=" * 70)

if __name__ == "__main__":
    main()

