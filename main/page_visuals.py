from html import escape

# Funtions for multiple classes
def get_rows(views, name):
    '''
    Returns every row in a view or []
    if missing/empty.
    '''
    return views.get(name) or []


def get_one_row(views, name):
    '''
    Only return first row in a view,
    {} if missing/empty
    '''

    rows = views.get(name) or []
    return rows[0] if rows else {}

def short_date(date):
    '''
    2026-11-01 -> 11/01
    '''
    _, month, day = date.split("-")
    return f"{month}/{day}"



# Action Classes
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
            (self.minutes, "minutes"),
            (self.seconds, "seconds")
        ]

        blocks = [
            f'<div class="unit"><span class="value">{value:02d}</span>'
            f'<span class="label">{label}</span></div>'
            for value, label in units
        ]

        return '<span class="colon">:</span>'.join(blocks)

class LineChart:
    '''
    Line Chart for total_delay_week.
    '''
    PAD = 70

    def __init__(self, title, labels, values, above_max_value=0, x_title="", 
                 y_title="", fmt=str, width=640, height=290):
        if len(labels) != len(values):
            raise ValueError(f"{len(labels)} labels but {len(values)} values")
        self.title = title
        self.labels = [str(label) for label in labels]
        self.values = [value or 0 for value in values]
        self.above_max_value = above_max_value
        self.x_title = x_title
        self.y_title = y_title
        self.fmt = fmt
        self.width=width
        self.height=height


    @property
    def y_max(self):
        '''
        Top of y axis. Avoids 0 so y doesn't divide by 0.
        '''
        max_v = max(self.values)
        if max_v == 0:
            ValueError("Max value is 0.")
        return max(self.values) + self.above_max_value

    def _x(self, i):
        '''
        x position at i-th point
        '''
        usable = self.width - (2 * self.PAD) - 20 #Space at the end
        if len(self.values) == 1:
            return self.PAD + usable / 2
        return self.PAD + i * usable / (len(self.values) - 1)

    def _y(self, value):
        '''
        y position according to the value.
        '''
        usable = self.height - 2 * self.PAD
        return self.height - self.PAD - (value / self.y_max) * usable

    def _coords(self):
        '''
        Where each dot is located.
        '''
        return " ".join(f"{self._x(i):.1f},{self._y(value):.1f}"
                          for i, value in enumerate(self.values))

    def _line_svg(self):
        '''
        Writing html for each line between coordinates.
        '''
        return f'<polyline class="line" points="{self._coords()}"/>'

    def _dots_svg(self):
        '''
        Writing html for each dot on line graph, including what
        is seen when it's being hovered over.
        '''
        groups = []
        for i, (label, value) in enumerate(zip(self.labels, self.values)):
            cx, cy = f"{self._x(i):.1f}", f"{self._y(value):.1f}"
            text = self.fmt(value)
            seen_text = escape(text)
            aria_text = escape(f"{label}: {text}")
            groups.append(
                f'<g class="point" tabindex="0" data-text="{seen_text}" aria-label="{aria_text}">'
                f'<circle class="hit" cx="{cx}" cy="{cy}" r="12"/>'
                f'<circle class="dot" cx="{cx}" cy="{cy}" r="4"/>'
                f'</g>'
            )
        return "".join(groups)

    def _x_ticks_svg(self):
        '''
        Writing the dates for each point on the x-axis.
        '''
        bottom =self.height - self.PAD
        return "".join(
            f'<text class="tick" x="{self._x(i):.1f}" y="{bottom + 20}" '
            f'text-anchor="middle">{escape(label)}</text>'
            for i, label in enumerate(self.labels)
        )

    def _axis_titles_svg(self):
        '''
        Writing in titles of x and y axis (as a whole).
        '''
        titles = ""
        if self.x_title:
            x_mid = self.width / 2
            titles += (f'<text class="axis-title" x="{x_mid:.1f}" y="{self.height - 25}" '
                       f'text-anchor="middle">{escape(self.x_title)}</text>')
        if self.y_title:
            x = self.PAD - 10
            y = self.height / 2
            titles += (f'<text class="axis-title" x="{x}" y="{y}" '
                       f'transform="rotate(-90 {x} {y})" ' # Rotate 90 degrees
                       f'text-anchor="middle">{escape(self.y_title)}</text>')
        return titles

    def _axes_svg(self):
        left, top = self.PAD, self.PAD
        plot_w = self.width - 2 * self.PAD
        plot_h = self.height - 2 * self.PAD
        return (
            f'<rect class="axis" x="{left}" y="{top}" width="{plot_w}" height="{plot_h}"/>'
            + self._x_ticks_svg()
            + f'<text class="tick" x="{left - 6}" y="{self._y(self.y_max) + 4:.1f}" text-anchor="end">{self.y_max}</text>'
            f'<text class="tick" x="{left - 6}" y="{self._y(0) + 4:.1f}" text-anchor="end">0</text>'
            + self._axis_titles_svg()
        )

    def _area_svg(self):
        bottom = self._y(0)
        first_x = self._x(0)
        last_x = self._x(len(self.values) - 1)

        points = (
            f"{self._coords()} "
            f"{last_x:.1f},{bottom:.1f} {first_x:.1f},{bottom:.1f}"
            )
        return f'<polygon class="area" points="{points}"/>'

    def _vlines_svg(self):
        bottom = self._y(0)
        lines = []
        for i, value in enumerate(self.values):
            x = f"{self._x(i):.1f}"
            lines.append(
                f'<line class="vline" x1="{x}" y1="{self._y(value):.1f}" '
                f'x2="{x}" y2="{bottom:.1f}"/>'
            )
        return "".join(lines)

    def to_html(self):
        crop = self.PAD - 20
        if not self.values:
            return (f'<section class="chart"><h2>{escape(self.title)}</h2>'
                    f'<p>No data recorded</p></section>')
        return f"""
        <section class="chart">
          <h2>{escape(self.title)}</h2>
          <svg viewBox="10 {crop} {self.width - self.PAD} {self.height - crop}" role="img"
              aria-label="{escape(self.title)}">
            {self._area_svg()}{self._vlines_svg()}
            {self._axes_svg()}{self._line_svg()}{self._dots_svg()}
          </svg>
        </section>"""


class Column:
    '''
    Builds one column for an eventual Table,
    give desired column name, and the view
    title to pull from.
    '''

    def __init__(self, col_name, view_col, fmt=str, default=""):
        if isinstance(view_col, str):
            view_col = (view_col,)
        self.col_name = col_name
        self.view_col = view_col
        self.fmt = fmt
        self.default = default

    def col_name_html(self):
        return f"<th>{escape(self.col_name)}</th>"

    def _value(self, row, key):
        '''
        One value from the row. NULLs and missing keys use the default.
        '''
        value = row.get(key)
        return self.default if value is None else value

    def column_creation(self, row):
        '''
        Returns this column's cell for one row.
        '''
        values = [self._value(row, key) for key in self.view_col]
        return f"<td>{escape(self.fmt(*values))}</td>"

class ImageColumn(Column):
    def __init__(self, col_name, view_col, images, default=""):
        super().__init__(col_name, view_col, default=default)
        self.images = images

    def column_creation(self, row):
        value = self._value(row, self.view_col[0])
        src = self.images.get(value)

        if src is None:
            return super().column_creation(row)

        return (f'<td><img class="cell-img" src="{escape(src)}" '
                f'alt="{escape(str(value))}" loading="lazy"></td>')

class Table:
    '''
    Creating a table using columns built
    in the Column class.
    '''

    def __init__(self, document, table_name, columns, view_title,
                 css_class=""):
        if not columns:
            raise ValueError("No Columns")
        self.table_name = table_name
        self.columns = columns
        self.rows = get_rows(document["views"], view_title)
        self.css_class = css_class

    def _table_name_html(self):
        return "".join(col.col_name_html() for col in self.columns)

    def _row_html(self, row):
        cells = "".join(col.column_creation(row) for col in self.columns)
        return f"<tr>{cells}</tr>"

    def _body_html(self):
        if not self.rows:
            return (f'<tr><td colspan="{len(self.columns)}">No data recorded</td></tr>')
        return "\n            ".join(self._row_html(row) for row in self.rows)

    def to_html(self):
        return f"""
      <section class="data-table {self.css_class}">
        <h2>{escape(self.table_name)}</h2>
        <table>
          <thead><tr>{self._table_name_html()}</tr></thead>
          <tbody>
            {self._body_html()}
          </tbody>
        </table>
      </section>"""
