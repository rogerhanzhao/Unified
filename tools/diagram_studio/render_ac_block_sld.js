"use strict";

const {
  STYLE,
  createBusbarHorizontal,
  createConductor,
  createNodeDot,
  createKnifeSwitch,
  createCircuitBreaker,
  createEarthingSwitch,
  createCT,
  createSurgeArrester,
  createTransformerSymbol,
  createPCSBox,
} = require("./symbol_library");

function clone(obj) {
  return JSON.parse(JSON.stringify(obj));
}

function placeSymbol(symbol, x, y, extra = {}) {
  const group = clone(symbol.group);
  group.left = x;
  group.top = y;
  if (group.sld && extra.sld) {
    group.sld = { ...group.sld, ...extra.sld };
  }
  return group;
}

function addLabel(labels, text, x, y, options = {}) {
  const fontSize = options.fontSize || STYLE.fontSize;
  let labelX = x;
  let labelY = y;
  const width = Math.max(10, text.length * fontSize * 0.6);
  const height = fontSize * 1.2;

  let shifted = 0;
  while (
    labels.some(
      (box) =>
        labelX < box.x + box.w &&
        labelX + width > box.x &&
        labelY < box.y + box.h &&
        labelY + height > box.y
    )
  ) {
    labelY += 12;
    shifted += 1;
    if (shifted > 12) {
      break;
    }
  }
  labels.push({ x: labelX, y: labelY, w: width, h: height });
  return {
    type: "text",
    text,
    left: labelX,
    top: labelY,
    originX: "left",
    originY: "top",
    fontFamily: STYLE.fontFamily,
    fontSize,
    fill: STYLE.lineColor,
    selectable: false,
    evented: false,
  };
}

function buildSemanticGraph(pcsCount) {
  return {
    nodes: [
      "MV_BUS",
      "RMU_IN",
      "RMU_OUT",
      "TEE_NODE",
      "MV_SWITCH",
      "MV_CB",
      "EARTHING_SWITCH",
      "CT",
      "SURGE_ARRESTER",
      "TRANSFORMER_HV",
      "TRANSFORMER_LV",
      "LV_BUS",
      ...Array.from({ length: pcsCount }, (_, i) => `PCS_FEEDER_${i + 1}`),
    ],
    edges: [
      ["RMU_IN", "MV_BUS"],
      ["RMU_OUT", "MV_BUS"],
      ["TEE_NODE", "MV_BUS"],
      ["TEE_NODE", "MV_SWITCH"],
      ["MV_SWITCH", "MV_CB"],
      ["MV_CB", "CT"],
      ["CT", "TRANSFORMER_HV"],
      ["TRANSFORMER_LV", "LV_BUS"],
      ...Array.from({ length: pcsCount }, (_, i) => ["LV_BUS", `PCS_FEEDER_${i + 1}`]),
    ],
  };
}

function render_ac_block_sld(params = {}) {
  const pcsCount = Number(params.pcsCount || 4);
  const voltageLabel = params.kvLabel || "33.0 kV/690 V";
  const mvaLabel = params.mvaLabel || "7.7 MVA";

  const width = 1600;
  const height = 900;

  const xLeft = 200;
  const xRight = width - 200;
  const xCenter = (xLeft + xRight) / 2;
  const yMV = 140;

  const transformer = createTransformerSymbol(18, 8);
  const tHeight = transformer.group.sld.height || 80;
  const tY = yMV + 90;
  const yLV = tY + tHeight + 110;
  const yPCS = yLV + 50;

  const lvLeft = xLeft + 80;
  const lvRight = xRight - 80;
  const feederStart = lvLeft + 60;
  const feederEnd = lvRight - 60;
  const feederStep = pcsCount > 1 ? (feederEnd - feederStart) / (pcsCount - 1) : 0;

  const labels = [];
  const objects = [];

  const graph = buildSemanticGraph(pcsCount);

  const mvBus = createBusbarHorizontal(xRight - xLeft, { color: STYLE.lineColor, bus: "MV" });
  objects.push(placeSymbol(mvBus, xLeft, yMV));

  const teeDot = createNodeDot(4);
  objects.push(placeSymbol(teeDot, xCenter, yMV));

  const rmuDotLeft = createNodeDot(4);
  const rmuDotRight = createNodeDot(4);
  const rmuInX = xLeft + 60;
  const rmuOutX = xRight - 60;
  objects.push(placeSymbol(rmuDotLeft, rmuInX, yMV));
  objects.push(placeSymbol(rmuDotRight, rmuOutX, yMV));

  const rmuStubLen = 26;
  const rmuStub = createConductor(rmuStubLen, "vertical");
  objects.push(placeSymbol(rmuStub, rmuInX, yMV - rmuStubLen));
  objects.push(placeSymbol(rmuStub, rmuOutX, yMV - rmuStubLen));
  const rmuSwitch = createKnifeSwitch(22, "vertical");
  objects.push(placeSymbol(rmuSwitch, rmuInX, yMV - rmuStubLen - 22));
  objects.push(placeSymbol(rmuSwitch, rmuOutX, yMV - rmuStubLen - 22));

  const rmuLabel = addLabel(labels, "RMU", rmuInX - 24, yMV - rmuStubLen - 40);
  objects.push(rmuLabel);

  objects.push(addLabel(labels, "To 20kV Switchgear", rmuInX - 70, yMV - 90));
  objects.push(addLabel(labels, "To Other RMU", rmuOutX - 40, yMV - 90));

  const hvAnchorY = tY + transformer.anchors.hv.y;
  const mvConductor = createConductor(hvAnchorY - yMV, "vertical");
  objects.push(placeSymbol(mvConductor, xCenter, yMV));

  const switchSymbol = createKnifeSwitch(24, "vertical");
  const cbSymbol = createCircuitBreaker(26, "vertical");
  const ctSymbol = createCT(26, "vertical");
  const earthSwitch = createEarthingSwitch(30);
  const surge = createSurgeArrester(36);

  const chainTop = yMV + 12;
  const chainBottom = hvAnchorY - 12;
  const chainLen = chainBottom - chainTop;
  const switchY = chainTop;
  const cbY = chainTop + chainLen * 0.35;
  const ctY = chainTop + chainLen * 0.65;
  objects.push(placeSymbol(switchSymbol, xCenter, switchY));
  objects.push(placeSymbol(cbSymbol, xCenter, cbY));
  objects.push(placeSymbol(ctSymbol, xCenter, ctY));

  const earthX = xCenter - 40;
  const earthTap = createConductor(16, "horizontal");
  objects.push(placeSymbol(earthTap, earthX, cbY + 6));
  objects.push(placeSymbol(earthSwitch, earthX, cbY + 8));

  const surgeX = xCenter + 40;
  const surgeTap = createConductor(16, "horizontal");
  objects.push(placeSymbol(surgeTap, xCenter, ctY + 10));
  objects.push(placeSymbol(surge, surgeX, ctY + 6));

  const transformerX = xCenter - (transformer.group.sld.width || 36) / 2;
  objects.push(placeSymbol(transformer, transformerX, tY));

  const transformerLabelX = transformerX + (transformer.group.sld.width || 36) + 18;
  const transformerLabelY = tY + 10;
  objects.push(addLabel(labels, "Transformer", transformerLabelX, transformerLabelY));
  objects.push(addLabel(labels, voltageLabel, transformerLabelX, transformerLabelY + 18));
  objects.push(addLabel(labels, mvaLabel, transformerLabelX, transformerLabelY + 36));
  objects.push(addLabel(labels, "Dyn11", transformerLabelX, transformerLabelY + 54));
  objects.push(addLabel(labels, "Uk=7.0%", transformerLabelX, transformerLabelY + 72));

  const lvBus = createBusbarHorizontal(lvRight - lvLeft, { color: STYLE.busbarColor, bus: "LV" });
  objects.push(placeSymbol(lvBus, lvLeft, yLV));

  const lvDot = createNodeDot(4);
  const lvNodeX = xCenter;
  objects.push(placeSymbol(lvDot, lvNodeX, yLV));
  const lvConductor = createConductor(yLV - (tY + transformer.anchors.lv.y), "vertical");
  objects.push(placeSymbol(lvConductor, lvNodeX, tY + transformer.anchors.lv.y));

  const pcsBox = createPCSBox(70, 70);
  const feederSwitch = createCircuitBreaker(20, "vertical");
  for (let i = 0; i < pcsCount; i += 1) {
    const x = feederStart + feederStep * i;
    const node = createNodeDot(4);
    objects.push(placeSymbol(node, x, yLV));
    const feederLine = createConductor(yPCS - yLV, "vertical");
    objects.push(placeSymbol(feederLine, x, yLV));
    objects.push(placeSymbol(feederSwitch, x, yLV + 12));
    objects.push(placeSymbol(pcsBox, x - 35, yPCS));
    objects.push(addLabel(labels, `PCS-${i + 1}`, x - 22, yLV + 8));
  }

  return {
    version: "4.4.0",
    width,
    height,
    background: "#000000",
    objects,
    sld: {
      graph,
    },
  };
}

module.exports = {
  render_ac_block_sld,
};
