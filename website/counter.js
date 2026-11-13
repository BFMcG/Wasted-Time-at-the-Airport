// time for count-up
const DURATION_MS = 2000;   

class CountUpCounter {
  constructor(element) {
    this.valueSpans = element.querySelectorAll(".value");
    this.totalSecs = Number(element.dataset.total);
  }

  // Fast at the start, slow at the end
  static easeOut(progress) {
    return 1 - Math.pow(1 - progress, 3);
  }

  static split(totalSecs) {
    return [
      Math.floor(totalSecs / 86400),
      Math.floor((totalSecs % 86400) / 3600),
      Math.floor((totalSecs % 3600) / 60),
      totalSecs % 60,
    ];
  }

  // progress from 0 to 1
  render(progress) {
    const secs = Math.floor(this.totalSecs * CountUpCounter.easeOut(progress));
    CountUpCounter.split(secs).forEach((value, i) => {
      this.valueSpans[i].textContent = String(value).padStart(2, "0");
    });
  }
}


const counters = [...document.querySelectorAll(".counter")]
  .map((element) => new CountUpCounter(element));

let startTime = null;

function frame(timestamp) {
  if (startTime === null) {
    startTime = timestamp;
  }
  const progress = Math.min((timestamp - startTime) / DURATION_MS, 1);
  counters.forEach((counter) => counter.render(progress));

  if (progress < 1) {
    requestAnimationFrame(frame);
  }
}

const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

if (reduceMotion) {
  counters.forEach((counter) => counter.render(1));
} else {
  requestAnimationFrame(frame);
}