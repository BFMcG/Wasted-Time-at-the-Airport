class ChartTooltip {
  constructor(chart) {
    this.chart = chart;
    this.activePoint = null;

    // One tooltip box per chart, hidden until a point is hovered
    this.tip = document.createElement("div");
    this.tip.className = "chart-tooltip";
    this.tip.hidden = true;
    chart.appendChild(this.tip);

    chart.querySelectorAll(".point").forEach((point) => {
      point.addEventListener("mouseenter", () => this.show(point));
      point.addEventListener("focus", () => this.show(point));
      point.addEventListener("mouseleave", () => this.hide());
      point.addEventListener("blur", () => this.hide());
    });
  }

  show(point) {
    this.hide();
    this.tip.textContent = point.dataset.text;   // e.g. "1h 10m"
    this.tip.hidden = false;

    // Place the tooltip above the dot, kept inside the chart's edges
    const dot = point.querySelector(".dot").getBoundingClientRect();
    const box = this.chart.getBoundingClientRect();
    const half = this.tip.offsetWidth / 2;
    const x = dot.left + dot.width / 2 - box.left;
    this.tip.style.left = `${Math.min(Math.max(x, half), box.width - half)}px`;
    this.tip.style.top = `${dot.top - box.top}px`;

    point.classList.add("active");
    this.activePoint = point;
  }

  hide() {
    this.tip.hidden = true;
    if (this.activePoint) {
      this.activePoint.classList.remove("active");
      this.activePoint = null;
    }
  }
}

document.querySelectorAll(".chart").forEach((chart) => new ChartTooltip(chart));