"use strict";

function distance(a, b) {
  return Math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2);
}

function collectAnchors(objects, anchors) {
  objects.forEach((obj) => {
    if (obj.type === "group" && obj.sld && obj.sld.anchors) {
      const left = obj.left || 0;
      const top = obj.top || 0;
      Object.entries(obj.sld.anchors).forEach(([name, pt]) => {
        anchors.push({ name, x: left + pt.x, y: top + pt.y, type: obj.sld.type });
      });
    }
  });
}

function collectLines(objects, lines) {
  objects.forEach((obj) => {
    if (obj.type === "group" && Array.isArray(obj.objects)) {
      const left = obj.left || 0;
      const top = obj.top || 0;
      obj.objects.forEach((child) => {
        if (child.type === "line" && child.sld && child.sld.role) {
          const x1 = left + (child.left || 0) + child.x1;
          const y1 = top + (child.top || 0) + child.y1;
          const x2 = left + (child.left || 0) + child.x2;
          const y2 = top + (child.top || 0) + child.y2;
          lines.push({ x1, y1, x2, y2, role: child.sld.role });
        }
      });
    }
  });
}

function lineContainsPoint(line, pt, tol) {
  const minX = Math.min(line.x1, line.x2) - tol;
  const maxX = Math.max(line.x1, line.x2) + tol;
  const minY = Math.min(line.y1, line.y2) - tol;
  const maxY = Math.max(line.y1, line.y2) + tol;
  if (pt.x < minX || pt.x > maxX || pt.y < minY || pt.y > maxY) {
    return false;
  }
  if (Math.abs(line.x1 - line.x2) < tol) {
    return Math.abs(pt.x - line.x1) <= tol;
  }
  if (Math.abs(line.y1 - line.y2) < tol) {
    return Math.abs(pt.y - line.y1) <= tol;
  }
  return false;
}

function validateConnections(json) {
  const errors = [];
  if (!json || !Array.isArray(json.objects)) {
    return { ok: false, errors: ["Invalid JSON: missing objects array."] };
  }

  const anchors = [];
  const lines = [];
  collectAnchors(json.objects, anchors);
  collectLines(json.objects, lines);

  const tol = 1;
  lines.forEach((line) => {
    const endPoints = [
      { x: line.x1, y: line.y1 },
      { x: line.x2, y: line.y2 },
    ];
    endPoints.forEach((pt) => {
      const snapped = anchors.some((a) => distance(a, pt) <= tol);
      if (!snapped) {
        errors.push(`Conductor endpoint not snapped: (${pt.x.toFixed(1)}, ${pt.y.toFixed(1)})`);
      }
    });
  });

  json.objects.forEach((obj) => {
    if (!obj || obj.type !== "group" || !obj.sld || !obj.sld.anchors) {
      return;
    }
    if (["Conductor", "Busbar", "NodeDot"].includes(obj.sld.type)) {
      return;
    }
    const left = obj.left || 0;
    const top = obj.top || 0;
    const anchorPoints = Object.values(obj.sld.anchors).map((pt) => ({
      x: left + pt.x,
      y: top + pt.y,
    }));
    const connected = anchorPoints.some((pt) =>
      lines.some((line) => distance(pt, { x: line.x1, y: line.y1 }) <= tol || distance(pt, { x: line.x2, y: line.y2 }) <= tol)
    );
    if (!connected) {
      errors.push(`Floating symbol: ${obj.sld.type || "Unknown"} at (${left}, ${top})`);
    }
  });

  const lvBusbars = json.objects.filter(
    (obj) => obj.sld && obj.sld.type === "Busbar" && obj.sld.bus === "LV"
  );
  if (lvBusbars.length > 1) {
    const coupler = json.objects.find((obj) => obj.sld && obj.sld.type === "BusCoupler");
    if (!coupler) {
      errors.push("LV bus is split but no Bus Coupler symbol present.");
    }
  }

  return { ok: errors.length === 0, errors };
}

function validate_sld(json) {
  const errors = [];
  if (!json || !Array.isArray(json.objects)) {
    return { ok: false, errors: ["Invalid JSON: missing objects array."] };
  }

  const anchors = [];
  const lines = [];
  collectAnchors(json.objects, anchors);
  collectLines(json.objects, lines);

  const tol = 1;
  lines.forEach((line) => {
    const endPoints = [
      { x: line.x1, y: line.y1 },
      { x: line.x2, y: line.y2 },
    ];
    endPoints.forEach((pt) => {
      const snapped = anchors.some((a) => distance(a, pt) <= tol);
      if (!snapped) {
        errors.push(`Conductor endpoint not snapped: (${pt.x.toFixed(1)}, ${pt.y.toFixed(1)})`);
      }
    });
  });

  const lvBus = json.objects.find((obj) => obj.sld && obj.sld.type === "Busbar" && obj.sld.bus === "LV");
  if (!lvBus) {
    errors.push("LV busbar missing.");
  }
  const mvBus = json.objects.find((obj) => obj.sld && obj.sld.type === "Busbar" && obj.sld.bus === "MV");
  if (!mvBus) {
    errors.push("MV busbar missing.");
  }

  const transformer = json.objects.find((obj) => obj.sld && obj.sld.type === "Transformer");
  if (transformer && lvBus) {
    const lvAnchor = transformer.sld.anchors.lv;
    const lvX = transformer.left + lvAnchor.x;
    const lvY = transformer.top + lvAnchor.y;
    const lvBusY = lvBus.top;
    const lvBusLeft = lvBus.left;
    const lvBusRight = lvBus.left + (lvBus.objects[0]?.x2 || 0);
    const onBus = Math.abs(lvY - lvBusY) <= tol && lvX >= lvBusLeft - tol && lvX <= lvBusRight + tol;
    if (!onBus) {
      const connected = lines.some((line) => {
        const p1 = { x: line.x1, y: line.y1 };
        const p2 = { x: line.x2, y: line.y2 };
        return (
          distance(p1, { x: lvX, y: lvY }) <= tol ||
          distance(p2, { x: lvX, y: lvY }) <= tol
        );
      });
      if (!connected) {
        errors.push("Transformer LV not connected to LV bus.");
      }
    }
  }

  const ctSymbols = json.objects.filter((obj) => obj.sld && obj.sld.type === "CT");
  ctSymbols.forEach((ct) => {
    const inAnchor = ct.sld.anchors.in;
    const outAnchor = ct.sld.anchors.out;
    const inPoint = { x: ct.left + inAnchor.x, y: ct.top + inAnchor.y };
    const outPoint = { x: ct.left + outAnchor.x, y: ct.top + outAnchor.y };
    const inline = lines.some((line) => lineContainsPoint(line, inPoint, tol) && lineContainsPoint(line, outPoint, tol));
    if (!inline) {
      errors.push("CT symbol not inline with a conductor.");
    }
  });

  return { ok: errors.length === 0, errors };
}

module.exports = { validate_sld, validateConnections };
