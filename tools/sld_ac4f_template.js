"use strict";

const fs = require("fs");
const path = require("path");

const COLORS = {
  background: "#000000",
  line: "#e5e7eb",
  dash: "#22d3ee",
  busbar: "#ef4444",
  text: "#e5e7eb",
};

const FONT_FAMILY = "Arial";

function commonProps() {
  return {
    selectable: false,
    evented: false,
    objectCaching: false,
    strokeUniform: true,
  };
}

function lineAbs(x1, y1, x2, y2, opts = {}) {
  const left = Math.min(x1, x2);
  const top = Math.min(y1, y2);
  return {
    type: "line",
    left,
    top,
    x1: x1 - left,
    y1: y1 - top,
    x2: x2 - left,
    y2: y2 - top,
    originX: "left",
    originY: "top",
    fill: null,
    stroke: COLORS.line,
    strokeWidth: 2,
    strokeLineCap: "round",
    strokeLineJoin: "round",
    ...commonProps(),
    ...opts,
  };
}

function lineLocal(x1, y1, x2, y2, opts = {}) {
  return lineAbs(x1, y1, x2, y2, opts);
}

function rectAbs(x, y, w, h, opts = {}) {
  return {
    type: "rect",
    left: x,
    top: y,
    width: w,
    height: h,
    originX: "left",
    originY: "top",
    fill: "rgba(0,0,0,0)",
    stroke: COLORS.line,
    strokeWidth: 2,
    strokeLineJoin: "round",
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
    stroke: COLORS.line,
    strokeWidth: 2,
    ...commonProps(),
    ...opts,
  };
}

function textAbs(text, x, y, opts = {}) {
  return {
    type: "text",
    text,
    left: x,
    top: y,
    originX: opts.originX || "left",
    originY: opts.originY || "top",
    fontFamily: FONT_FAMILY,
    fontSize: opts.fontSize || 18,
    fill: COLORS.text,
    fontWeight: opts.fontWeight || "normal",
    ...commonProps(),
  };
}

function group(objects, left, top, opts = {}) {
  return {
    type: "group",
    left,
    top,
    originX: "left",
    originY: "top",
    objects,
    ...commonProps(),
    ...opts,
  };
}

function drawDashedContainerBox(x, y, w, h, labelOptional, fontSize) {
  const rect = rectAbs(0, 0, w, h, {
    stroke: COLORS.dash,
    strokeDashArray: [6, 4],
  });
  const items = [rect];
  if (labelOptional) {
    items.push(
      textAbs(labelOptional, 8, 6, {
        fontSize: fontSize || 16,
      })
    );
  }
  return group(items, x, y);
}

function drawBusbarRed(x1, y, x2, thickness) {
  const left = Math.min(x1, x2);
  const length = Math.abs(x2 - x1);
  const line = lineLocal(0, 0, length, 0, {
    stroke: COLORS.busbar,
    strokeWidth: thickness || 4,
  });
  return group([line], left, y);
}

function drawSwitchDisconnector(x, y, w, h) {
  const cx = w / 2;
  const base = [
    lineLocal(cx, 0, cx, h, {}),
    lineLocal(cx, h * 0.45, w * 0.85, h * 0.2, {}),
  ];
  return group(base, x, y);
}

function drawBreaker(x, y, w, h) {
  const size = Math.min(w, h) * 0.55;
  const rect = rectAbs((w - size) / 2, (h - size) / 2, size, size, {});
  return group([rect], x, y);
}

function drawTransformer(x, y, w, h) {
  const r = Math.min(w, h) * 0.18;
  const c1 = circleLocal(w * 0.35, h * 0.35, r, {});
  const c2 = circleLocal(w * 0.65, h * 0.35, r, {});
  const c3 = circleLocal(w * 0.5, h * 0.7, r, {});
  const link = lineLocal(w * 0.35 + r, h * 0.35, w * 0.65 - r, h * 0.35, {});
  return group([c1, c2, c3, link], x, y);
}

function drawPCSBlock(x, y, w, h) {
  const body = rectAbs(0, 0, w, h, {});
  const diag = lineLocal(w * 0.2, h * 0.2, w * 0.8, h * 0.8, {});
  return group([body, diag], x, y);
}

function drawBatteryString(x, y, w, h) {
  const items = [];
  const cx = w / 2;
  items.push(lineLocal(cx, 0, cx, h, {}));
  const cells = 4;
  const cellPitch = h / (cells + 1);
  const longW = w * 0.7;
  const shortW = w * 0.45;
  const gap = Math.max(3, h * 0.04);
  for (let i = 0; i < cells; i += 1) {
    const cy = cellPitch * (i + 1);
    items.push(lineLocal(cx - longW / 2, cy - gap, cx + longW / 2, cy - gap, {}));
    items.push(lineLocal(cx - shortW / 2, cy + gap, cx + shortW / 2, cy + gap, {}));
  }
  return group(items, x, y);
}

function generateSLD_AC4F_DC1(options = {}) {
  const feederCount = Math.max(2, Math.min(6, Number(options.feederCount || 4)));
  const showLabels = options.showLabels !== false;
  const scale = Number(options.scale || 1);
  const s = (v) => v * scale;

  const canvasWidth = s(1600);
  const canvasHeight = s(900);

  const acBox = { x: s(650), y: s(70), w: s(420), h: s(560) };
  const dcBox = { x: s(650), y: s(660), w: s(420), h: s(170) };
  const xCenter = acBox.x + acBox.w / 2;

  const objects = [];

  objects.push(drawDashedContainerBox(acBox.x, acBox.y, acBox.w, acBox.h));
  objects.push(drawDashedContainerBox(dcBox.x, dcBox.y, dcBox.w, dcBox.h));

  const mvTopY = acBox.y + s(20);
  const mvBusY = acBox.y + s(90);
  const feederOffset = s(90);
  const leftFeederX = xCenter - feederOffset;
  const rightFeederX = xCenter + feederOffset;

  objects.push(lineAbs(leftFeederX, mvTopY, leftFeederX, mvBusY, {}));
  objects.push(lineAbs(rightFeederX, mvTopY, rightFeederX, mvBusY, {}));

  const mvBus = drawBusbarRed(leftFeederX, mvBusY, rightFeederX, s(4));
  objects.push(mvBus);

  const switchW = s(26);
  const switchH = s(32);
  objects.push(drawSwitchDisconnector(leftFeederX - switchW / 2, mvTopY + s(6), switchW, switchH));
  objects.push(drawSwitchDisconnector(rightFeederX - switchW / 2, mvTopY + s(6), switchW, switchH));

  const trW = s(90);
  const trH = s(70);
  const trX = xCenter - trW / 2;
  const trY = mvBusY + s(50);
  objects.push(lineAbs(xCenter, mvBusY, xCenter, trY, {}));

  const breakerW = s(24);
  const breakerH = s(24);
  objects.push(drawBreaker(xCenter - breakerW / 2, mvBusY + s(12), breakerW, breakerH));

  objects.push(drawTransformer(trX, trY, trW, trH));

  const lvBusY = trY + trH + s(60);
  objects.push(lineAbs(xCenter, trY + trH, xCenter, lvBusY, {}));

  const lvBusLeft = acBox.x + s(60);
  const lvBusRight = acBox.x + acBox.w - s(60);
  objects.push(drawBusbarRed(lvBusLeft, lvBusY, lvBusRight, s(4)));

  const pcsW = s(50);
  const pcsH = s(70);
  const pcsTopY = lvBusY + s(28);
  const feederSpan = lvBusRight - lvBusLeft;
  const feederStep = feederCount > 1 ? feederSpan / (feederCount - 1) : 0;

  const dcLineBottom = dcBox.y + s(40);
  const batteryW = s(26);
  const batteryH = s(70);
  const batteryTopY = dcBox.y + s(60);

  for (let i = 0; i < feederCount; i += 1) {
    const fx = lvBusLeft + feederStep * i;
    objects.push(lineAbs(fx, lvBusY, fx, pcsTopY, {}));
    objects.push(drawPCSBlock(fx - pcsW / 2, pcsTopY, pcsW, pcsH));
    objects.push(lineAbs(fx, pcsTopY + pcsH, fx, dcLineBottom, {}));
    objects.push(drawBatteryString(fx - batteryW / 2, batteryTopY, batteryW, batteryH));
  }

  const auxLineY = lvBusY + s(20);
  const auxLineX1 = xCenter + s(80);
  const auxLineX2 = acBox.x + acBox.w + s(10);
  objects.push(lineAbs(auxLineX1, auxLineY, auxLineX2, auxLineY, {}));
  objects.push(lineAbs(auxLineX2, auxLineY, auxLineX2 - s(8), auxLineY - s(5), {}));
  objects.push(lineAbs(auxLineX2, auxLineY, auxLineX2 - s(8), auxLineY + s(5), {}));

  if (showLabels) {
    const labelSize = s(18);
    const smallLabel = s(16);
    objects.push(
      textAbs("To 20kV Switchgear", leftFeederX, acBox.y + s(4), {
        fontSize: labelSize,
        originX: "center",
      })
    );
    objects.push(
      textAbs("To Other RMU", rightFeederX, acBox.y + s(4), {
        fontSize: labelSize,
        originX: "center",
      })
    );
    objects.push(
      textAbs("AC Block (PCS&MV SKID)", acBox.x + acBox.w + s(20), acBox.y + s(220), {
        fontSize: labelSize,
      })
    );
    objects.push(
      textAbs("DC Block (BESS)", dcBox.x + dcBox.w + s(20), dcBox.y + s(60), {
        fontSize: labelSize,
      })
    );
    objects.push(
      textAbs(
        "Power input from Auxiliary transformer for station",
        acBox.x + acBox.w + s(20),
        auxLineY - s(14),
        { fontSize: smallLabel }
      )
    );
  }

  return {
    version: "4.4.0",
    width: canvasWidth,
    height: canvasHeight,
    background: COLORS.background,
    objects,
  };
}

if (require.main === module) {
  const outPath =
    process.argv[2] || path.join("assets", "templates", "SLD_AC4F_DC1.json");
  const data = generateSLD_AC4F_DC1();
  fs.mkdirSync(path.dirname(outPath), { recursive: true });
  fs.writeFileSync(outPath, JSON.stringify(data, null, 2));
  process.stdout.write(`Wrote ${outPath}\n`);
}

module.exports = {
  generateSLD_AC4F_DC1,
};
