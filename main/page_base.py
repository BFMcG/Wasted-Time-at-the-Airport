from html import escape
from string import Template

LAYOUT = Template(
    """<!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>$title | Time Wasted at San Diego Airport</title>
      <link rel="stylesheet" href="style.css">
    </head>
    <body>
      <nav>
          $nav
      </nav>
      <main>
    $body
        <p class="footnote">Data for $data_date (updated each morning)</p>
      </main>
    $scripts
    </body>
    </html>
    """
)

class Page:
    '''
    Base class for every web_page on the website.
    '''

    def __init__(self, key, title, nav_label, page_content, scripts=()):
        self.key = key
        self.title = title
        self.nav_label = nav_label
        self.page_content = page_content
        self.scripts = scripts

    def nav_html(self, site_pages):
        '''
        Building a navigation bar that will be for every page.
        '''
        links = []
        for page in site_pages:
            active = ' class="active"' if page.key == self.key else ""
            links.append(f'<a href="{page.key}"{active}>{escape(page.nav_label)}</a>')
        return "\n    ".join(links)

    def render(self, document, site_pages):
        '''
        Wraps this page's body in shared layout.
        '''
        script_tags = "\n".join(f'  <script src="{src}"></script>' for src in self.scripts)
        return LAYOUT.substitute(
            title=escape(self.title),
            nav=self.nav_html(site_pages),
            body=self.page_content.body(document),
            data_date=escape(document["data_date"]),
            scripts=script_tags
        )

class Site:
    '''
    The pages that make up the website
    '''
    def __init__(self, pages):
        # Something wrong page.key
        self.pages = [page.page_params() for page in pages]

        # Check for duplicates
        keys = [page.key for page in self.pages]
        if len(keys) != len(set(keys)):
            raise ValueError(f"Duplicate page keys: {keys}")
        if len(self.pages) != len(set(keys)):
            raise ValueError(f"Missing key for a page")
        
    def render_all(self, document):
        '''
        Returns {page key: page HTML} for every page.
        '''

        return {page.key: page.render(document, self.pages) 
                for page in self.pages}
