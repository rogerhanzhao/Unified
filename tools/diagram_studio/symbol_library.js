"use strict";

const UNIT = 10;

const STYLE = {
  unit: UNIT,
  lineColor: "#e5e7eb",
  busbarColor: "#ef4444",
  busbarStrokeWidth: 0.35 * UNIT,
  conductorStrokeWidth: 0.2 * UNIT,
  symbolStrokeWidth: 0.2 * UNIT,
  fontFamily: "Arial",
  fontSize: 14,
};

function commonProps() {
  return {
    selectable: false,
    evented: false,
    objectCaching: false,
    strokeUniform: true,
  };
}

function lineLocal(x1, y1, x2, y2, opts = {}) {
  return {
    type: "line",
    left: Math.min(x1, x2),
    top: Math.min(y1, y2),
    x1: x1 - Math.min(x1, x2),
    y1: y1 - Math.min(y1, y2),
    x2: x2 - Math.min(x1, x2),
    y2: y2 - Math.min(y1, y2),
    originX: "left",
    originY: "top",
    fill: null,
    stroke: STYLE.lineColor,
    strokeWidth: STYLE.conductorStrokeWidth,
    strokeLineCap: "round",
    strokeLineJoin: "round",
    ...commonProps(),
    ...opts,
  };
}

function rectLocal(x, y, w, h, opts = {}) {
  return {
    type: "rect",
    left: x,
    top: y,
    width: w,
    height: h,
    originX: "left",
    originY: "top",
    fill: "rgba(0,0,0,0)",
    stroke: STYLE.lineColor,
    strokeWidth: STYLE.symbolStrokeWidth,
    ...commonProps(),
    ...opts,
  };
}

function circleLocal(cx, cy, r, opts = {}) {
  return {
    type: "circle",
    left: cx - r,
    top: cy - r,
    radius: r,
    originX: "left",
    originY: "top",
    fill: "rgba(0,0,0,0)",
    stroke: STYLE.lineColor,
    strokeWidth: STYLE.symbolStrokeWidth,
    ...commonProps(),
    ...opts,
  };
}

function polygonLocal(points, opts = {}) {
  return {
    type: "polygon",
    points,
    left: 0,
    top: 0,
    originX: "left",
    originY: "top",
    fill: "rgba(0,0,0,0)",
    stroke: STYLE.lineColor,
    strokeWidth: STYLE.symbolStrokeWidth,
    ...commonProps(),
    ...opts,
  };
}

function group(objects, anchors, sldType, extra = {}) {
  return {
    group: {
      type: "group",
      left: 0,
      top: 0,
      originX: "left",
      originY: "top",
      objects,
      sld: {
        type: sldType,
        anchors,
        ...extra,
      },
      ...commonProps(),
    },
    anchors,
  };
}

function createBusbarHorizontal(length, opts = {}) {
  const stroke = opts.color || STYLE.busbarColor;
  const line = lineLocal(0, 0, length, 0, {
    stroke,
    strokeWidth: STYLE.busbarStrokeWidth,
    sld: { role: "busbar" },
  });
  return group(
    [line],
    { left: { x: 0, y: 0 }, right: { x: length, y: 0 } },
    "Busbar",
    { bus: opts.bus || "LV" }
  );
}

function createConductor(length, orientation = "vertical") {
  const line =
    orientation === "vertical"
      ? lineLocal(0, 0, 0, length, { sld: { role: "conductor" } })
      : lineLocal(0, 0, length, 0, { sld: { role: "conductor" } });
  const anchors =
    orientation === "vertical"
      ? { start: { x: 0, y: 0 }, end: { x: 0, y: length } }
      : { start: { x: 0, y: 0 }, end: { x: length, y: 0 } };
  return group([line], anchors, "Conductor");
}

function createNodeDot(radius = 4, fill = STYLE.lineColor) {
  const circle = circleLocal(0, 0, radius, { fill });
  return group([circle], { center: { x: 0, y: 0 } }, "NodeDot");
}

function createKnifeSwitch(length = 30, orientation = "horizontal") {
  const blade = length * 0.35;
  const offset = length * 0.4;
  const objects = [];
  if (orientation === "horizontal") {
    objects.push(lineLocal(0, 0, offset, 0));
    objects.push(lineLocal(offset, 0, offset + blade, -blade * 0.4));
    objects.push(lineLocal(offset + blade * 0.95, 0, length, 0));
    return group(objects, { in: { x: 0, y: 0 }, out: { x: length, y: 0 } }, "Switch");
  }
  objects.push(lineLocal(0, 0, 0, offset));
  objects.push(lineLocal(0, offset, blade * 0.4, offset + blade));
  objects.push(lineLocal(0, offset + blade * 0.95, 0, length));
  return group(objects, { in: { x: 0, y: 0 }, out: { x: 0, y: length } }, "Switch");
}

function createCircuitBreaker(length = STYLE.unit * 1.4, orientation = "horizontal") {
  const box = length * 0.35;
  const gap = (length - box) / 2;
  const objects = [];
  if (orientation === "horizontal") {
    objects.push(lineLocal(0, 0, gap, 0));
    objects.push(rectLocal(gap, -box / 2, box, box));
    objects.push(lineLocal(gap + box, 0, length, 0));
    return group(objects, { in: { x: 0, y: 0 }, out: { x: length, y: 0 } }, "CircuitBreaker");
  }
  objects.push(lineLocal(0, 0, 0, gap));
  objects.push(rectLocal(-box / 2, gap, box, box));
  objects.push(lineLocal(0, gap + box, 0, length));
  return group(objects, { in: { x: 0, y: 0 }, out: { x: 0, y: length } }, "CircuitBreaker");
}

function createGround() {
  const objects = [];
  objects.push(lineLocal(0, 0, 0, 8));
  objects.push(lineLocal(-6, 8, 6, 8));
  objects.push(lineLocal(-4, 11, 4, 11));
  objects.push(lineLocal(-2, 14, 2, 14));
  return group(objects, { ground: { x: 0, y: 14 } }, "Ground");
}

function createEarthingSwitch(height = 30) {
  const objects = [];
  const switchOffset = height * 0.4;
  objects.push(lineLocal(0, 0, 0, switchOffset));
  objects.push(lineLocal(0, switchOffset, -8, switchOffset + 8));
  objects.push(lineLocal(0, switchOffset + 8, 0, height - 10));
  const ground = createGround();
  ground.group.left = 0;
  ground.group.top = height - 10;
  objects.push(...ground.group.objects);
  return group(objects, { in: { x: 0, y: 0 }, ground: { x: 0, y: height + 4 } }, "EarthingSwitch");
}

function createCT(length = STYLE.unit * 3.0, orientation = "horizontal") {
  const r = STYLE.unit * 0.6;
  const objects = [];
  if (orientation === "horizontal") {
    objects.push(lineLocal(0, 0, length, 0));
    objects.push(circleLocal(length * 0.4, 0, r));
    objects.push(circleLocal(length * 0.5, 0, r));
    objects.push(circleLocal(length * 0.6, 0, r));
    return group(objects, { in: { x: 0, y: 0 }, out: { x: length, y: 0 } }, "CT");
  }
  objects.push(lineLocal(0, 0, 0, length));
  objects.push(circleLocal(0, length * 0.4, r));
  objects.push(circleLocal(0, length * 0.5, r));
  objects.push(circleLocal(0, length * 0.6, r));
  return group(objects, { in: { x: 0, y: 0 }, out: { x: 0, y: length } }, "CT");
}

function createSurgeArrester(height = STYLE.unit * 3.2) {
  const objects = [];
  objects.push(lineLocal(0, 0, 0, height * 0.4));
  objects.push(lineLocal(-6, height * 0.4, 6, height * 0.4));
  objects.push(lineLocal(-6, height * 0.5, 6, height * 0.5));
  objects.push(circleLocal(0, height * 0.7, 6));
  objects.push(lineLocal(0, height * 0.76, 0, height));
  const ground = createGround();
  ground.group.left = 0;
  ground.group.top = height;
  objects.push(...ground.group.objects);
  return group(
    objects,
    { tap: { x: 0, y: 0 }, ground: { x: 0, y: height + 14 } },
    "SurgeArrester"
  );
}

function createTransformerSymbol(radius = STYLE.unit * 1.5, spacing = STYLE.unit * 0.6) {
  const r = radius;
  const topCx = r;
  const topCy = r;
  const botCy = r * 3 + spacing;
  const height = botCy + r;
  const objects = [];
  objects.push(circleLocal(topCx, topCy, r));
  objects.push(circleLocal(topCx, botCy, r));
  const delta = [
    { x: topCx, y: topCy - r * 0.5 },
    { x: topCx - r * 0.5, y: topCy + r * 0.4 },
    { x: topCx + r * 0.5, y: topCy + r * 0.4 },
  ];
  objects.push(polygonLocal(delta));
  objects.push(lineLocal(topCx, botCy, topCx, botCy - r * 0.6));
  objects.push(lineLocal(topCx, botCy, topCx - r * 0.45, botCy + r * 0.35));
  objects.push(lineLocal(topCx, botCy, topCx + r * 0.45, botCy + r * 0.35));
  return group(
    objects,
    { hv: { x: topCx, y: 0 }, lv: { x: topCx, y: height } },
    "Transformer",
    { width: r * 2, height }
  );
}

function createPCSBox(width = 70, height = 70) {
  const objects = [];
  objects.push(rectLocal(0, 0, width, height));
  objects.push(lineLocal(width * 0.2, height * 0.2, width * 0.8, height * 0.8));
  objects.push(lineLocal(width * 0.2, height * 0.7, width * 0.45, height * 0.7));
  objects.push(lineLocal(width * 0.2, height * 0.62, width * 0.45, height * 0.62));
  objects.push(lineLocal(width * 0.6, height * 0.3, width * 0.8, height * 0.3));
  return group(objects, { top: { x: width / 2, y: 0 } }, "PCS");
}

module.exports = {
  STYLE,
  createBusbarHorizontal,
  createConductor,
  createNodeDot,
  createKnifeSwitch,
  createCircuitBreaker,
  createEarthingSwitch,
  createGround,
  createCT,
  createSurgeArrester,
  createTransformerSymbol,
  createPCSBox,
};
