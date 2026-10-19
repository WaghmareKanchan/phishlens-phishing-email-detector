from app.ml.heuristics import analyze_signals, iter_urls, split_body_segments
from app.ml.preprocessing import build_text


def titles(sender="", subject="", body=""):
    return [e["title"] for e in analyze_signals(sender, subject, body).evidence]


def test_wont_is_not_a_prize_word():
    assert titles(body="I won't be able to attend") == ["No warning signs found"]
    assert "Reward or prize language" in titles(body="You won a prize")


def test_keywords_need_word_boundaries():
    assert titles(body="We served hotpot; see the catalog installation guide") == ["No warning signs found"]
    assert "Asks for sensitive details" in titles(body="Please log in and verify your password")


def test_url_trailing_punctuation_is_stripped():
    assert [u for *_, u in iter_urls("see (http://example.com/path).")] == ["http://example.com/path"]
    t = titles(body="visit http://bad.xyz).")
    assert "Unusual domain ending" in t     # host is bad.xyz, not "bad.xyz)"


def test_numeric_subject_is_not_shouting():
    assert "Shouting subject line" not in titles(subject="123456789012")
    assert "Shouting subject line" in titles(subject="ACT ON THIS TODAY")


def test_segments_rebuild_the_original_text_even_with_emoji():
    body = "Dear Customer 😀 verify now: http://bad-login.xyz/a. Act now!"
    segs = split_body_segments(body)
    assert "".join(s["text"] for s in segs) == body
    assert {s["kind"] for s in segs} >= {"cred", "url", "urg"}


def test_classic_phishing_scores_high_signals():
    s = analyze_signals("HDFC Bank <a@hdfcbank-secure-login.com>", "URGENT: suspended",
                        "Dear Customer verify your password http://185.1.1.1/x")
    assert s.cats["text"] > 20 and s.cats["links"] >= 25 and s.cats["sender"] > 0


def test_preprocessing_strips_html_and_domains():
    t = build_text("Bob <b@x.com>", "Hi", "<p>Click <a href='x'>http://evil-site.xyz/p</a></p>")
    assert "<" not in t and "evil-site" not in t and "urltoken" in t and "tld_xyz" in t
