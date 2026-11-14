import pytest
from unittest.mock import MagicMock
from page_base import Page, Site

DOCUMENT = {
        "data_date": "2026-01-01",
        "views": {"flights": [{"FLT1": "1234", "FLT2": "5678"}]},
        "generated_at": "2026-01-01"
    }

def make_content(key):
    page_content = MagicMock()
    page_content.body.return_value = f"<p>{key} body</p>"
    return page_content


# Page
@pytest.fixture
def mock_page():
    content_1 = make_content("1.html")
    content_2 = make_content("2.html")
    page_1 = Page("1.html", "test_title1", "test_nav1", content_1, ("test_script1.js",))
    page_2 = Page("2.html", "test_title2", "test_nav2", content_2)

    return page_1, [page_1, page_2]

def test_nav_html(mock_page):

    c_page, f_site_pages = mock_page

    result = c_page.nav_html(f_site_pages) 

    expected = (
        '<a href="1.html" class="active">test_nav1</a>'
        '\n    '
        '<a href="2.html">test_nav2</a>'
    )

    assert result == expected

def test_render(mock_page):

    c_page, f_site_pages = mock_page

    result = c_page.render(DOCUMENT, f_site_pages)

    assert "<title>test_title1 | Time Wasted at San Diego Airport</title>" in result
    assert '<a href="1.html" class="active">test_nav1</a>' in result
    assert '<a href="2.html">test_nav2</a>' in result
    assert "<p>1.html body</p>" in result    
    assert "Data for 2026-01-01" in result
    assert '<script src="test_script1.js"></script>' in result

    # Checking render passed body(document)
    c_page.page_content.body.assert_called_once_with(DOCUMENT)


# Site
@pytest.fixture
def mock_site(mock_page):

    _, pages = mock_page

    contents = []
    for page in pages:
        page.page_content.page_params.return_value = page
        contents.append(page.page_content)

    return Site(contents), contents

def test_render_all(mock_site):

    f_site, f_contents = mock_site

    result = f_site.render_all(DOCUMENT)

    assert set(result) == {"1.html", "2.html"}

    assert "<title>test_title1 | Time Wasted at San Diego Airport</title>" in result["1.html"]
    assert "<title>test_title2 | Time Wasted at San Diego Airport</title>" in result["2.html"]

    assert "<p>1.html body</p>" in result["1.html"]
    assert "<p>2.html body</p>" in result["2.html"]

    assert '<script src="test_script1.js"></script>' in result["1.html"]
    assert "<script" not in result["2.html"]

    # Checking if the mock content ran through render and site properly
    for content in f_contents:
        content.page_params.assert_called_once_with()
        content.body.assert_called_once_with(DOCUMENT)