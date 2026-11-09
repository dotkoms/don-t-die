from dontdie.sources import rss

RSS_FIXTURE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Outlet</title>
    <item>
      <title>Rapamycin &amp; mouse <b>lifespan</b>: what the study says</title>
      <link>https://example-outlet.com/story/rapamycin-study?utm_source=feed</link>
      <pubDate>Mon, 03 Nov 2026 09:15:00 GMT</pubDate>
      <description><![CDATA[<p>A new paper on <a>mTOR</a> and aging.</p>]]></description>
    </item>
    <item>
      <title>No link, skipped</title>
      <description>entry without a url</description>
    </item>
  </channel>
</rss>
"""

ATOM_FIXTURE = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Atom Outlet</title>
  <entry>
    <title>Semaglutide coverage update</title>
    <link rel="alternate" type="text/html" href="https://atom-outlet.org/2026/11/semaglutide"/>
    <published>2026-11-01T08:00:00Z</published>
    <summary>GLP-1 receptor agonist news &amp; notes</summary>
  </entry>
</feed>
"""


def test_parse_rss_strips_html_and_dates():
    records = rss.parse_feed(RSS_FIXTURE, "testoutlet")
    assert len(records) == 1
    rec = records[0]
    assert rec["title"] == "Rapamycin & mouse lifespan: what the study says"
    assert rec["published"] == "2026-11-03"
    assert rec["summary"] == "A new paper on mTOR and aging."
    assert rec["source"] == "testoutlet"
    assert rec["url"] == ("https://example-outlet.com/story/rapamycin-study"
                          "?utm_source=feed")


def test_parse_atom():
    records = rss.parse_feed(ATOM_FIXTURE, "atomoutlet")
    assert len(records) == 1
    rec = records[0]
    assert rec["title"] == "Semaglutide coverage update"
    assert rec["url"] == "https://atom-outlet.org/2026/11/semaglutide"
    assert rec["published"] == "2026-11-01"
    assert rec["summary"] == "GLP-1 receptor agonist news & notes"


def test_item_id_ignores_tracking_params():
    a = rss.item_id("https://x.com/story?utm_source=feed&id=1")
    b = rss.item_id("https://x.com/story?id=1&utm_campaign=rss#frag")
    assert a == b


def test_item_id_differs_for_different_urls():
    assert rss.item_id("https://x.com/a") != rss.item_id("https://x.com/b")


def test_slug_is_readable_and_stable():
    slug = rss.slug_for("BPC-157: A Peptide On Trial!", "https://x.com/1")
    assert slug.startswith("bpc-157-a-peptide-on-trial")
    assert rss.slug_for("BPC-157: A Peptide On Trial!", "https://x.com/1") == slug


def test_fetch_feed_filters_old_entries(landing_dir, monkeypatch):
    """Items older than the window are not landed; undated items are kept."""
    import datetime

    old_date = (datetime.date.today() - datetime.timedelta(days=30))
    fresh_date = (datetime.date.today() - datetime.timedelta(days=1))
    feed = f"""<?xml version="1.0"?>
    <rss version="2.0"><channel><title>t</title>
      <item><title>Old news</title><link>https://x.com/old</link>
        <pubDate>{old_date.strftime('%a, %d %b %Y %H:%M:%S GMT')}</pubDate></item>
      <item><title>Fresh news</title><link>https://x.com/fresh</link>
        <pubDate>{fresh_date.strftime('%a, %d %b %Y %H:%M:%S GMT')}</pubDate></item>
      <item><title>Undated news</title><link>https://x.com/undated</link></item>
    </channel></rss>"""

    class FakeResponse:
        text = feed
        def raise_for_status(self):
            pass

    monkeypatch.setattr(
        "dontdie.sources.rss.requests.get",
        lambda url, timeout=None, headers=None: FakeResponse(),
    )
    summary = rss.fetch_feed("x", "X", "https://x.com/feed", days=7, limit=10)
    landed = {p.stem for p in landing_dir.glob("x/*.json")}
    assert summary["total"] == 2  # fresh + undated kept, old dropped
    assert rss.item_id("https://x.com/old") not in landed
    assert rss.item_id("https://x.com/fresh") in landed
