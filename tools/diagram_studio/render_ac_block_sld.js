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
  const align = options.align || "left";
  if (align === "center") {
    labelX = x - width / 2;
  } else if (align === "right") {
    labelX = x - width;
  }

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
  const U = STYLE.unit;

  const xLeft = 200;
  const xRight = width - 200;
  const xCenter = (xLeft + xRight) / 2;
  const yMV = 140;

  const transformer = createTransformerSymbol();
  const tHeight = transformer.group.sld.height || 80;
  const yChainStart = yMV;
  const leadBusToSwitch = Math.round(U * 0.6);
  const switchLen = Math.round(U * 2.0);
  const leadSwitchToBreaker = Math.round(U * 0.6);
  const breakerLen = Math.round(U * 1.4);
  const leadBreakerToCT = Math.round(U * 0.8);
  const ctLen = Math.round(U * 3.0);
  const leadCTToTap = Math.round(U * 0.8);
  const leadTapToTransformer = Math.round(U * 4.0);
  const tapBranchLen = Math.round(U * 4.0);

  const tY =
    yChainStart +
    leadBusToSwitch +
    switchLen +
    leadSwitchToBreaker +
    breakerLen +
    leadBreakerToCT +
    ctLen +
    leadCTToTap +
    leadTapToTransformer;
  const yLV = tY + tHeight + Math.round(U * 8.0);
  const yPCS = yLV + Math.round(U * 2.8);

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

  const rmuStubLen = Math.round(U * 2.4);
  const rmuStub = createConductor(rmuStubLen, "vertical");
  objects.push(placeSymbol(rmuStub, rmuInX, yMV - rmuStubLen));
  objects.push(placeSymbol(rmuStub, rmuOutX, yMV - rmuStubLen));
  const rmuSwitchLen = Math.round(U * 2.0);
  const rmuSwitch = createKnifeSwitch(rmuSwitchLen, "vertical");
  objects.push(placeSymbol(rmuSwitch, rmuInX, yMV - rmuStubLen - rmuSwitchLen));
  objects.push(placeSymbol(rmuSwitch, rmuOutX, yMV - rmuStubLen - rmuSwitchLen));

  const rmuLabel = addLabel(labels, "RMU", rmuInX - 24, yMV - rmuStubLen - 40);
  objects.push(rmuLabel);

  objects.push(addLabel(labels, "To 20kV Switchgear", rmuInX - 70, yMV - 90));
  objects.push(addLabel(labels, "To Other RMU", rmuOutX - 40, yMV - 90));

  const switchSymbol = createKnifeSwitch(switchLen, "vertical");
  const cbSymbol = createCircuitBreaker(breakerLen, "vertical");
  const ctSymbol = createCT(ctLen, "vertical");
  const earthSwitch = createEarthingSwitch(Math.round(U * 3.0));
  const surge = createSurgeArrester(Math.round(U * 3.2));

  let yCursor = yChainStart;
  objects.push(placeSymbol(createConductor(leadBusToSwitch, "vertical"), xCenter, yCursor));
  yCursor += leadBusToSwitch;
  objects.push(placeSymbol(switchSymbol, xCenter, yCursor));
  yCursor += switchLen;
  objects.push(placeSymbol(createConductor(leadSwitchToBreaker, "vertical"), xCenter, yCursor));
  yCursor += leadSwitchToBreaker;
  objects.push(placeSymbol(cbSymbol, xCenter, yCursor));
  yCursor += breakerLen;
  objects.push(placeSymbol(createConductor(leadBreakerToCT, "vertical"), xCenter, yCursor));
  yCursor += leadBreakerToCT;
  objects.push(placeSymbol(ctSymbol, xCenter, yCursor));
  yCursor += ctLen;
  objects.push(placeSymbol(createConductor(leadCTToTap, "vertical"), xCenter, yCursor));
  yCursor += leadCTToTap;

  const tapDot = createNodeDot(4);
  objects.push(placeSymbol(tapDot, xCenter, yCursor));
  objects.push(placeSymbol(createConductor(tapBranchLen, "horizontal"), xCenter - tapBranchLen, yCursor));
  objects.push(placeSymbol(createConductor(tapBranchLen, "horizontal"), xCenter, yCursor));
  objects.push(placeSymbol(earthSwitch, xCenter - tapBranchLen, yCursor));
  objects.push(placeSymbol(surge, xCenter + tapBranchLen, yCursor));

  objects.push(placeSymbol(createConductor(leadTapToTransformer, "vertical"), xCenter, yCursor));
  const transformerX = xCenter - (transformer.group.sld.width || U * 3) / 2;
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
  const lvAnchorY = tY + transformer.anchors.lv.y;
  const lvConductor = createConductor(yLV - lvAnchorY, "vertical");
  objects.push(placeSymbol(lvConductor, lvNodeX, lvAnchorY));

  const pcsBoxSize = Math.round(U * 7.0);
  const pcsBox = createPCSBox(pcsBoxSize, pcsBoxSize);
  const feederSwitch = createCircuitBreaker(breakerLen, "vertical");
  const feederLead = Math.round(U * 0.6);
  const feederGap = Math.round(U * 0.8);
  for (let i = 0; i < pcsCount; i += 1) {
    const x = feederStart + feederStep * i;
    const node = createNodeDot(4);
    objects.push(placeSymbol(node, x, yLV));
    objects.push(placeSymbol(createConductor(feederLead, "vertical"), x, yLV));
    objects.push(placeSymbol(feederSwitch, x, yLV + feederLead));
    objects.push(
      placeSymbol(
        createConductor(feederGap, "vertical"),
        x,
        yLV + feederLead + breakerLen
      )
    );
    objects.push(placeSymbol(pcsBox, x - pcsBoxSize / 2, yPCS));
    objects.push(
      addLabel(labels, `PCS-${i + 1}`, x, yLV - Math.round(U * 1.4), { align: "center" })
    );
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
