from html import escape

from page_base import Page, Site
from page_visuals import get_rows, get_one_row, short_date, DelayCounter
from page_visuals import LineChart, Column, ImageColumn, Table 


# Pages
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
        row = get_one_row(document["views"], view_title)
        
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

    @staticmethod
    def secs_to_hr_min(seconds):
        hours = seconds // 3600
        minutes = seconds % 3600 // 60
        return f"{hours}h {minutes}m"

    
    def _airlines_used(self):
        '''
        Text with airlines used at the bottom of 
        the page.
        '''
        images = (
            ("images/full_name/alaska.webp",    "Alaska Airlines"),
            ("images/full_name/american.webp",  "American Airlines"),
            ("images/full_name/delta.webp",     "Delta Air Lines"),
            ("images/full_name/frontier.webp",  "Frontier Airlines"),
            ("images/full_name/jetblue.webp",   "JetBlue"),
            ("images/full_name/skywest.webp",   "SkyWest Airlines"),
            ("images/full_name/southwest.webp", "Southwest Airlines"),
            ("images/full_name/united.webp",    "United Airlines")
        )

        if not images:
            return ""
        fmt_imgs = "".join(
            f'<img src="{escape(src)}" alt="{escape(alt)}" loading="lazy">'
            for src, alt in images
        )
        return (
            '    <section class="airlines">\n'
            '      <h2 class="airline-title">Airlines Tracked</h2>\n'
            f'      <div class="airline-grid">{fmt_imgs}</div>\n'
            '    </section>\n'
        )

    def body(self, document):
        '''
        Creating html strting to be added to website html.
        '''
        # Counter
        total_delay_yest = self._get_row_total_delay(document, "total_delay_yesterday")
        total_delay_month = self._get_row_total_delay(document, "total_delay_month")

        yesterday = DelayCounter(*total_delay_yest)
        month = DelayCounter(*total_delay_month)

        # Line Graph
        rows = sorted(get_rows(document["views"], "total_delay_week"),
                      key=lambda row: row.get("dt") or "")

        dates = [short_date(row.get("dt")) or "" for row in rows]
        delays_secs = [row.get("sum_delay_secs") for row in rows]


        chart = LineChart("Time Wasted per Day (Last 7 Days)",
                          labels = dates,
                          values = delays_secs,
                          above_max_value=10000,
                          x_title = "Dates (2026)",
                          y_title = "Total Seconds",
                          fmt=self.secs_to_hr_min,
                          width=540)

        return (
            '    <div class="home">\n'
            + '    <h1 class="site-title">Time Wasted<br>at San Diego Airport</h1>\n'
            + '    <h2 class="disclaimer">Delay is caluculated by combining the *gateway delay and the *runway delay.</h2>\n'
            + '    <div class="home-row">\n'
            + '      <div class="counters">'
            + self._counter_block(f"Yesterday ({short_date(document['data_date'])})", yesterday)
            + self._counter_block("This Month", month)
            + "      </div>"
            + chart.to_html()
            + "\n    </div>\n"
            + self._airlines_used()
            + "    </div>\n"
            + '    <div class="definitions">\n'
            + '      <p class="gate_run"><strong>*gateway delay:</strong> Every second exceeding 10 minutes after the scheduled departure time counts toward the delay.</p>\n'
            + '      <p class="gate_run"><strong>*runway delay:</strong> Every second exceeding 20 minutes after the aircraft departs from the gate counts toward the delay.</p>\n'
            + '    </div>\n'
            )

    def page_params(self):
        return Page(key="index.html", 
                    title="Home", 
                    nav_label="Home", 
                    scripts=("counter.js", "chart.js"),
                    page_content=self)


class LongestDelays:
    '''
    Creating longest delays webpage.
    '''

    @staticmethod
    def hr_min(hours, minutes):
        '''
        Formats hours and minutes to:
        "1h 1m"
        "0m"
        '''
        if hours == 0:
            return f"{minutes}m"

        return f"{hours}h {minutes}m"

    ABBV_LOGOS = {
        'SWA': "images/logo/southwest.webp",
        'ASA': "images/logo/alaska.webp",
        'QXE': "images/logo/alaska.webp",
        'SKW': "images/logo/skywest.webp",
        'UAL': "images/logo/united.webp",
        'AAL': "images/logo/american.webp",
        'DAL': "images/logo/delta.webp",
        'FFT': "images/logo/frontier.webp",
        'JBU': "images/logo/jetblue.webp"
    }


    COLUMNS_YEST = (
        ImageColumn("Airline", "airline_code", ABBV_LOGOS),
        Column("Airline Name", "airline_name"),
        Column("Flight", "flight_number"),
        Column("Delay", ("delay_hours", "delay_minutes"), fmt=hr_min, default=0)
    )

    COLUMNS_MON = (
        ImageColumn("Airline", "airline_code", ABBV_LOGOS),
        Column("Date", "dt"),
        Column("Flight", "flight_number"),
        Column("Delay", ("delay_hours", "delay_minutes"), fmt=hr_min, default=0)
    )

    

    def body(self, document):
        yesterday = Table(document, f"Yesterday ({short_date(document['data_date'])})", self.COLUMNS_YEST,
                          "top_delays_yesterday", css_class="delay")
        month = Table(document, "This Month", self.COLUMNS_MON,
                          "top_delays_month", css_class="delay")

        return (
            '    <h1 class="site-title">Longest Delays</h1>\n'
            '    <div class="table-row">'
            + yesterday.to_html()
            + month.to_html()
            + "\n    </div>\n"
        )

    def page_params(self):
        return Page(key="longest_delays.html",
                    title="Longest Delays",
                    nav_label="Longest Delays",
                    page_content=self)

class AirlineStats:
    @staticmethod
    def hr_min_secs(hours, minutes, seconds):
        '''
        Formats hours, minutes, and seconds to:
        "1h 1m 1s"
        "1m 1s"
        "0s"
        '''
        if hours == 0:
            if minutes == 0:
                return f"{seconds}s"
            return f"{minutes}m {seconds}s"
        return f"{hours}h {minutes}m {seconds}s"

    @staticmethod
    def pct(value):
        return f"{value}%"

    FULL_LOGOS = {
        'Southwest': "images/logo/southwest.webp",
        'Alaska/Horizon': "images/logo/alaska.webp",
        'SkyWest': "images/logo/skywest.webp",
        'United': "images/logo/united.webp",
        'American': "images/logo/american.webp",
        'Delta': "images/logo/delta.webp",
        'Frontier': "images/logo/frontier.webp",
        'JetBlue': "images/logo/jetblue.webp"
    }

    COLUMNS_AVG = (
        ImageColumn("Airline", "airline_name", FULL_LOGOS),
        Column("**Total # of Delays", "num_flights_delayed"),
        Column("Delay", ("avg_delay_hours", "avg_delay_minutes", "avg_delay_secs"), fmt=hr_min_secs, default=0)
    )

    COLUMNS_PCT = (
        ImageColumn("Airline", "airline_name", FULL_LOGOS),
        Column("Total # of Flights", "num_flights"),
        Column("Percent Delayed", "pct_of_flights_delayed", fmt=pct, default=0)
    )

    def body(self, document):
        yesterday_avg = Table(document, f"*Average Delay Yesterday ({short_date(document['data_date'])})", self.COLUMNS_AVG,
                          "avg_delay_al_yesterday", css_class="highlight-last")
        month_avg = Table(document, f"*Average Delay This Month", self.COLUMNS_AVG,
                          "avg_delay_al_month", css_class="highlight-last")
        yesterday_pct = Table(document, f"Percentage of Delays Yesterday ({short_date(document['data_date'])})", self.COLUMNS_PCT,
                              "pct_delays_yesterday", css_class="highlight-last pct")
        month_pct = Table(document, f"Percentage of Delays This Month", self.COLUMNS_PCT,
                              "pct_delays_month", css_class="highlight-last pct")
        

        return (
            '    <h1 class="site-title">Airline Statistics</h1>\n'
            '    <div class="table-row">'
            + yesterday_avg.to_html()
            + month_avg.to_html()
            + '    <div class="disclaimers">\n'
            + '      <p class="avg">*Average excludes flights delayed over 10 hours.</p>\n'
            + '      <p class="avg">**Includes flights delayed over 10 hours.</p>\n'
            + '    </div>\n'
            + yesterday_pct.to_html()
            + month_pct.to_html()
            + "\n    </div>\n"
        )

    def page_params(self):
        return Page(key="airline_stats.html",
                    title="Airline Statistics",
                    nav_label="Airline Statistics",
                    page_content=self)


SITE = Site([HomePage(), LongestDelays(), AirlineStats()])
    

        

