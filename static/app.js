const palette = ["#146c75", "#b23a48", "#7c5c15", "#4e67c8", "#1f7a4d", "#8a4fb0"];

const statusText = document.querySelector("#statusText");
const summary = document.querySelector("#summary");
const chart = document.querySelector("#chart");
const checkNow = document.querySelector("#checkNow");

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || payload.last_error || "请求失败");
  }
  return payload;
}

async function refresh() {
  const [status, latest, history] = await Promise.all([
    fetchJson("/api/status"),
    fetchJson("/api/latest"),
    fetchJson("/api/history"),
  ]);

  renderStatus(status, latest);
  renderSummary(latest.rows || []);
  renderChart(history.series || []);
}

function renderStatus(status, latest) {
  const pieces = [];
  pieces.push(`数据源：${status.source_type}`);
  if (status.tracked_candidates && status.tracked_candidates.length) {
    pieces.push(`关注：${status.tracked_candidates.join("、")}`);
  }
  if (status.poll_interval_seconds) {
    pieces.push(`间隔：${formatInterval(status.poll_interval_seconds)}`);
  }
  pieces.push(`样本数：${status.snapshot_count}`);
  if (latest.checked_at) {
    pieces.push(`最近检查：${formatTime(latest.checked_at)}`);
  }
  if (status.last_error) {
    pieces.push(`错误：${status.last_error}`);
  }
  statusText.textContent = pieces.join(" / ");
}

function renderSummary(rows) {
  summary.innerHTML = "";
  for (const row of rows) {
    const node = document.createElement("article");
    node.className = "candidate";
    node.innerHTML = `<strong></strong><span></span>`;
    node.querySelector("strong").textContent = row.name;
    node.querySelector("span").textContent = Number(row.votes).toLocaleString();
    summary.appendChild(node);
  }

  const gapCard = buildGapCard(rows);
  if (gapCard) {
    summary.appendChild(gapCard);
  }
}

function renderChart(series) {
  chart.replaceChildren();
  const width = chart.clientWidth || 900;
  const height = chart.clientHeight || 520;
  chart.setAttribute("viewBox", `0 0 ${width} ${height}`);

  if (!series.length || !series.some(item => item.points.length)) {
    addText(width / 2, height / 2, "暂无历史数据", "label", "middle");
    return;
  }

  const margin = { top: 34, right: 34, bottom: 54, left: 74 };
  const plotW = width - margin.left - margin.right;
  const plotH = height - margin.top - margin.bottom;
  const allPoints = series.flatMap(item => item.points.map(point => ({
    name: item.name,
    time: new Date(point.checked_at).getTime(),
    votes: Number(point.votes),
  })));

  const minTime = Math.min(...allPoints.map(point => point.time));
  const maxTime = Math.max(...allPoints.map(point => point.time));
  const minVotes = Math.min(...allPoints.map(point => point.votes));
  const maxVotes = Math.max(...allPoints.map(point => point.votes));
  const votePadding = Math.max(10, Math.round((maxVotes - minVotes) * 0.12));
  const yMin = Math.max(0, minVotes - votePadding);
  const yMax = maxVotes + votePadding;

  const x = time => {
    if (maxTime === minTime) return margin.left + plotW / 2;
    return margin.left + ((time - minTime) / (maxTime - minTime)) * plotW;
  };
  const y = votes => {
    if (yMax === yMin) return margin.top + plotH / 2;
    return margin.top + plotH - ((votes - yMin) / (yMax - yMin)) * plotH;
  };

  drawGrid(width, height, margin, plotW, plotH, yMin, yMax);
  drawHourlyTicks(width, height, margin, minTime, maxTime, x);

  series.forEach((item, index) => {
    const color = palette[index % palette.length];
    const points = item.points.map(point => ({
      x: x(new Date(point.checked_at).getTime()),
      y: y(Number(point.votes)),
      votes: Number(point.votes),
    }));

    if (points.length === 1) {
      addCircle(points[0].x, points[0].y, 5, color, "point");
    } else {
      addPath(points.map((point, pointIndex) => `${pointIndex === 0 ? "M" : "L"} ${point.x} ${point.y}`).join(" "), color);
      points.forEach(point => addCircle(point.x, point.y, 4, color, "point"));
    }

    const last = points[points.length - 1];
    if (last) {
      addText(Math.min(last.x + 8, width - 96), last.y - 8, item.name, "legend", "start", color);
    }
  });

  addText(margin.left, height - 18, formatTime(new Date(minTime).toISOString()), "label", "start");
  addText(width - margin.right, height - 18, formatTime(new Date(maxTime).toISOString()), "label", "end");
}

function drawGrid(width, height, margin, plotW, plotH, yMin, yMax) {
  for (let index = 0; index <= 4; index += 1) {
    const ratio = index / 4;
    const y = margin.top + plotH * ratio;
    const value = Math.round(yMax - (yMax - yMin) * ratio);
    addLine(margin.left, y, width - margin.right, y, "grid");
    addText(margin.left - 10, y + 4, value.toLocaleString(), "label", "end");
  }

  addLine(margin.left, margin.top, margin.left, height - margin.bottom, "axis");
  addLine(margin.left, height - margin.bottom, width - margin.right, height - margin.bottom, "axis");
}

function drawHourlyTicks(width, height, margin, minTime, maxTime, x) {
  const hourMs = 60 * 60 * 1000;
  const ticks = [];
  const start = Math.ceil(minTime / hourMs) * hourMs;

  for (let current = start; current <= maxTime; current += hourMs) {
    ticks.push(current);
  }

  if (!ticks.length) {
    return;
  }

  const labelEvery = pickTickLabelStep(ticks, width - margin.left - margin.right);
  ticks.forEach((tick, index) => {
    const xPos = x(tick);
    addLine(xPos, margin.top, xPos, height - margin.bottom, "grid grid-hour");
    addLine(xPos, height - margin.bottom, xPos, height - margin.bottom + 6, "axis");
    addCircle(xPos, height - margin.bottom, 2.8, "#9aa8ba", "hour-point");
    if (index % labelEvery === 0) {
      addText(xPos, height - 18, formatHour(tick), "label", "middle");
    }
  });
}

function pickTickLabelStep(ticks, plotWidth) {
  if (ticks.length <= 1) {
    return 1;
  }
  const minSpacing = 54;
  const rawSpacing = plotWidth / Math.max(1, ticks.length - 1);
  return rawSpacing >= minSpacing ? 1 : Math.ceil(minSpacing / rawSpacing);
}

function buildGapCard(rows) {
  if (rows.length < 2) {
    return null;
  }

  const [first, second] = [...rows].sort((a, b) => Number(b.votes) - Number(a.votes));
  const gap = Math.abs(Number(first.votes) - Number(second.votes));
  const node = document.createElement("article");
  node.className = "candidate candidate-gap";
  node.innerHTML = `<strong></strong><span></span><small></small>`;
  node.querySelector("strong").textContent = "票数差距";
  node.querySelector("span").textContent = gap.toLocaleString();
  node.querySelector("small").textContent = `${first.name} 领先 ${second.name}`;
  return node;
}

function addPath(d, color) {
  const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
  path.setAttribute("d", d);
  path.setAttribute("stroke", color);
  path.setAttribute("class", "series-line");
  chart.appendChild(path);
}

function addLine(x1, y1, x2, y2, className) {
  const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
  line.setAttribute("x1", x1);
  line.setAttribute("y1", y1);
  line.setAttribute("x2", x2);
  line.setAttribute("y2", y2);
  line.setAttribute("class", className);
  chart.appendChild(line);
}

function addCircle(cx, cy, r, fill, className) {
  const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
  circle.setAttribute("cx", cx);
  circle.setAttribute("cy", cy);
  circle.setAttribute("r", r);
  circle.setAttribute("fill", fill);
  circle.setAttribute("class", className);
  chart.appendChild(circle);
}

function addText(x, y, text, className, anchor = "start", fill = null) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", "text");
  node.setAttribute("x", x);
  node.setAttribute("y", y);
  node.setAttribute("text-anchor", anchor);
  node.setAttribute("class", className);
  if (fill) node.setAttribute("fill", fill);
  node.textContent = text;
  chart.appendChild(node);
}

function formatTime(value) {
  return new Date(value).toLocaleString("zh-CN", { hour12: false });
}

function formatHour(value) {
  return new Date(value).toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function formatInterval(seconds) {
  const minutes = Math.round(Number(seconds) / 60);
  return minutes >= 1 ? `${minutes}分钟` : `${seconds}秒`;
}

checkNow.addEventListener("click", async () => {
  checkNow.disabled = true;
  try {
    await fetchJson("/api/check", { method: "POST" });
    await refresh();
  } catch (error) {
    statusText.textContent = `检查失败：${error.message}`;
  } finally {
    checkNow.disabled = false;
  }
});

window.addEventListener("resize", () => refresh().catch(() => {}));
refresh().catch(error => {
  statusText.textContent = `加载失败：${error.message}`;
});
