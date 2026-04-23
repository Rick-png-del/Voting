const palette = ["#146c75", "#b23a48"];

const statusText = document.querySelector("#statusText");
const summary = document.querySelector("#summary");
const chart = document.querySelector("#chart");

async function refresh() {
  const response = await fetch(`./data/history.json?t=${Date.now()}`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error("公开数据还没有生成");
  }

  const data = await response.json();
  renderStatus(data);
  renderSummary(data.latest?.rows || []);
  renderChart(data.series || []);
}

function renderStatus(data) {
  const pieces = [];
  if (data.tracked_candidates?.length) {
    pieces.push(`关注：${data.tracked_candidates.join("、")}`);
  }
  if (data.poll_interval_seconds) {
    pieces.push(`更新：约每${formatInterval(data.poll_interval_seconds)}`);
  }
  if (data.updated_at) {
    pieces.push(`最近采样：${formatTime(data.updated_at)}`);
  }
  statusText.textContent = pieces.join(" / ") || "暂无公开数据";
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

  series.forEach((item, index) => {
    const color = palette[index % palette.length];
    const points = item.points.map(point => ({
      x: x(new Date(point.checked_at).getTime()),
      y: y(Number(point.votes)),
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

function formatInterval(seconds) {
  const minutes = Math.round(Number(seconds) / 60);
  return minutes >= 1 ? `${minutes}分钟` : `${seconds}秒`;
}

window.addEventListener("resize", () => refresh().catch(() => {}));
refresh().catch(error => {
  statusText.textContent = `加载失败：${error.message}`;
});

