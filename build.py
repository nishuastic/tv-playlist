"""Merge free Indian IPTV playlists and rewrite tvg-ids so they match the epgshare01 India guides."""
import gzip
import re
import urllib.request

PLAYLISTS = [
    ("Free-TV", "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8"),
    ("iptv-org", "https://iptv-org.github.io/iptv/countries/in.m3u"),
]
LANGUAGES = ["hin", "guj", "eng"]
GUIDES = [
    "https://epgshare01.online/epgshare01/epg_ripper_IN1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_IN4.xml.gz",
]


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    data = urllib.request.urlopen(req, timeout=60).read()
    return gzip.decompress(data) if url.endswith(".gz") else data


def norm(s):
    s = s.replace("&amp;", "and").replace("&", "and")
    s = re.sub(r"@.*$", "", s)
    s = re.sub(r"\.in$", "", s, flags=re.I)
    s = re.sub(r"\(.*?\)|\[.*?\]", "", s)
    s = re.sub(r"[^a-z0-9]", "", s.lower())
    return re.sub(r"(hd|sd)$", "", s)


def guide_ids():
    ids = {}
    for url in GUIDES:
        xml = get(url).decode("utf-8", "replace")
        for gid, name in re.findall(r'<channel id="([^"]+)">\s*<display-name[^>]*>([^<]+)', xml):
            for key in (norm(gid), norm(name)):
                ids.setdefault(key, gid.replace("&amp;", "&"))
    return ids


def entries(source, text):
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if not line.startswith("#EXTINF"):
            continue
        if source == "Free-TV" and 'group-title="India"' not in line:
            continue
        url = next((l for l in lines[i + 1:] if l and not l.startswith("#")), None)
        if url:
            yield line, url.strip()


def wanted_language():
    """Normalized names and stream URLs of channels in the wanted languages."""
    names, urls = set(), set()
    for lang in LANGUAGES:
        text = get(f"https://iptv-org.github.io/iptv/languages/{lang}.m3u").decode("utf-8", "replace")
        for info, stream in entries("iptv-org", text):
            names.add(norm(info.rsplit(",", 1)[-1]))
            urls.add(stream)
    return names, urls


def main():
    ids = guide_ids()
    lang_names, lang_urls = wanted_language()
    seen, out = set(), []
    for source, url in PLAYLISTS:
        for info, stream in entries(source, get(url).decode("utf-8", "replace")):
            name = info.rsplit(",", 1)[-1].strip()
            tid = re.search(r'tvg-id="([^"]*)"', info)
            key = norm(name)
            if not key or key in seen or "Geo-blocked" in name:
                continue
            if stream not in lang_urls and key not in lang_names:
                continue
            gid = ids.get(norm(tid.group(1))) if tid else None
            gid = gid or ids.get(key)
            # Only channels listed in the India guides count as popular.
            if not gid:
                continue
            seen.add(key)
            info = re.sub(r'tvg-id="[^"]*"', f'tvg-id="{gid}"', info) if tid else info.replace(
                "#EXTINF:-1", f'#EXTINF:-1 tvg-id="{gid}"', 1)
            out.append(f"{info}\n{stream}")
    matched = len(out)
    header = f'#EXTM3U x-tvg-url="{",".join(GUIDES)}"'
    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write(header + "\n" + "\n".join(out) + "\n")
    print(f"{len(out)} channels, {matched} with guide")


if __name__ == "__main__":
    main()
