from html import escape
from page_base import Page, Site



def missing_check(views, name):
    '''
    Checks if the view has data,
    returns {} if not. 
    '''

    rows = views.get(name) or []
    return rows[0] if rows else {}


class DelayCounter:
    '''
    Representing days:hours:minutes:seconds counter
    in Home page.
    '''

    def __init__(self, days, hours, minutes, seconds):
        self.days = days
        self.hours = hours
        self.minutes = minutes
        self.seconds = seconds

    @property
    def total_seconds(self):
        return self.days * 86400 + self.hours * 3600 + self.minutes * 60 + self.seconds

    def to_html(self):
        '''
        Returns digits as HTML.
        '''

        units = [
            (self.days, "days"),
            (self.hours, "hours"),
            (self.minutes, "min"),
            (self.seconds, "sec")
        ]

        blocks = [
            f'<div class="unit"><span class="value">{value:02d}</span>'
            f'<span class="label">{label}</span></div>'
            for value, label in units
        ]

        return '<span class="colon">:</span>'.join(blocks)


class HomePage:
    '''
    Creating Home Page.
    '''
    @staticmethod
    def _get_row_total_delay(document, view_title):
        '''
        Returns necissary parameters for DelayCounter from
        the total_delay views. NULLs and missing values
        become 0.
        '''
        row = missing_check(document["views"], view_title)
        
        days = row.get("days_wasted") or 0
        hours = row.get("hours_wasted") or 0
        minutes = row.get("minutes_wasted") or 0
        seconds = row.get("secs_wasted") or 0

        return days, hours, minutes, seconds

    @staticmethod
    def _counter_block(heading, counter):
        return f"""
    <section class="counter-block">
      <h2>{escape(heading)}</h2>
      <div class="counter" data-total="{counter.total_seconds}">{counter.to_html()}</div>
    </section>
    """

    def body(self, document):
        total_delay_yest = self._get_row_total_delay(document, "total_delay_yesterday")
        total_delay_month = self._get_row_total_delay(document, "total_delay_month")

        yesterday = DelayCounter(*total_delay_yest)
        month = DelayCounter(*total_delay_month)

        return (
            "    <h1>Time Wasted at the Airport</h1>\n"
            + self._counter_block("Yesterday", yesterday)
            + self._counter_block("This Month", month)
        )

    def page_params(self):
        return Page(key="index.html", 
                    title="Home", 
                    nav_label="Home", 
                    scripts=("counter.js",),
                    page_content=self)
    

SITE = Site([HomePage()])
    

        

