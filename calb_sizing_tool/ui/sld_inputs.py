import streamlit as st


def _safe_float(value, default):
    try:
        return float(value)
    except Exception:
        return default


def render_electrical_inputs(defaults: dict, key_prefix: str | None = None) -> dict:
    defaults = defaults or {}
    key_prefix = key_prefix or "sld_inputs"
    labels = defaults.get("mv_labels", {}) if isinstance(defaults.get("mv_labels"), dict) else {}
    rmu_defaults = defaults.get("rmu", {}) if isinstance(defaults.get("rmu"), dict) else {}
    tr_defaults = (
        defaults.get("transformer", {}) if isinstance(defaults.get("transformer"), dict) else {}
    )
    bus_defaults = (
        defaults.get("lv_busbar", {}) if isinstance(defaults.get("lv_busbar"), dict) else {}
    )
    cable_defaults = defaults.get("cables", {}) if isinstance(defaults.get("cables"), dict) else {}
    fuse_defaults = defaults.get("dc_fuse", {}) if isinstance(defaults.get("dc_fuse"), dict) else {}

    st.subheader("SLD Electrical Inputs")

    def _key(field: str) -> str:
        return f"{key_prefix}.{field}"

    label_c1, label_c2 = st.columns(2)
    to_switchgear = label_c1.text_input(
        "MV label: to switchgear",
        value=labels.get("to_switchgear") or "To Switchgear",
        key=_key("mv_label_to_switchgear"),
    )
    to_other_rmu = label_c2.text_input(
        "MV label: to other RMU",
        value=labels.get("to_other_rmu") or "To Other RMU",
        key=_key("mv_label_to_other_rmu"),
    )

    st.markdown("**RMU**")
    r1, r2, r3 = st.columns(3)
    rmu_rated_kv = r1.number_input(
        "Rated voltage (kV)",
        min_value=0.0,
        value=_safe_float(rmu_defaults.get("rated_kv"), 24.0),
        key=_key("rmu_rated_kv"),
        step=0.1,
    )
    rmu_rated_a = r2.number_input(
        "Rated current (A)",
        min_value=0.0,
        value=_safe_float(rmu_defaults.get("rated_a"), 630.0),
        key=_key("rmu_rated_a"),
        step=10.0,
    )
    rmu_short_circuit_ka = r3.number_input(
        "Short-circuit (kA/3s)",
        min_value=0.0,
        value=_safe_float(rmu_defaults.get("short_circuit_ka_3s"), 25.0),
        key=_key("rmu_short_circuit_ka_3s"),
        step=1.0,
    )
    r4, r5, r6 = st.columns(3)
    rmu_ct_ratio = r4.text_input(
        "CT ratio",
        value=rmu_defaults.get("ct_ratio") or "200/1",
        key=_key("rmu_ct_ratio"),
    )
    rmu_ct_class = r5.text_input(
        "CT class",
        value=rmu_defaults.get("ct_class") or "5P20",
        key=_key("rmu_ct_class"),
    )
    rmu_ct_va = r6.number_input(
        "CT burden (VA)",
        min_value=0.0,
        value=_safe_float(rmu_defaults.get("ct_va"), 10.0),
        key=_key("rmu_ct_va"),
        step=1.0,
    )

    st.markdown("**Transformer**")
    t1, t2, t3, t4 = st.columns(4)
    tr_vector_group = t1.text_input(
        "Vector group",
        value=tr_defaults.get("vector_group") or "Dyn11",
        key=_key("tr_vector_group"),
    )
    tr_uk_percent = t2.number_input(
        "Uk (%)",
        min_value=0.0,
        value=_safe_float(tr_defaults.get("uk_percent"), 7.0),
        key=_key("tr_uk_percent"),
        step=0.1,
    )
    tr_tap_range = t3.text_input(
        "Tap range",
        value=tr_defaults.get("tap_range") or "+/-2x2.5%",
        key=_key("tr_tap_range"),
    )
    tr_cooling = t4.text_input(
        "Cooling",
        value=tr_defaults.get("cooling") or "ONAN",
        key=_key("tr_cooling"),
    )

    st.markdown("**LV Busbar**")
    b1, b2 = st.columns(2)
    lv_rated_a = b1.number_input(
        "Rated current (A)",
        min_value=0.0,
        value=_safe_float(bus_defaults.get("rated_a"), 2500.0),
        key=_key("lv_rated_a"),
        step=10.0,
    )
    lv_short_circuit_ka = b2.number_input(
        "Short-circuit (kA)",
        min_value=0.0,
        value=_safe_float(bus_defaults.get("short_circuit_ka"), 25.0),
        key=_key("lv_short_circuit_ka"),
        step=1.0,
    )

    st.markdown("**Cables**")
    c1, c2, c3 = st.columns(3)
    mv_cable_spec = c1.text_input(
        "MV cable spec",
        value=cable_defaults.get("mv_cable_spec") or "TBD",
        key=_key("mv_cable_spec"),
    )
    lv_cable_spec = c2.text_input(
        "LV cable spec",
        value=cable_defaults.get("lv_cable_spec") or "TBD",
        key=_key("lv_cable_spec"),
    )
    dc_cable_spec = c3.text_input(
        "DC cable spec",
        value=cable_defaults.get("dc_cable_spec") or "TBD",
        key=_key("dc_cable_spec"),
    )

    st.markdown("**DC Fuse**")
    fuse_spec = st.text_input(
        "Fuse spec",
        value=fuse_defaults.get("fuse_spec") or "TBD",
        key=_key("dc_fuse_spec"),
    )

    return {
        "mv_labels": {"to_switchgear": to_switchgear, "to_other_rmu": to_other_rmu},
        "rmu": {
            "rated_kv": rmu_rated_kv,
            "rated_a": rmu_rated_a,
            "short_circuit_ka_3s": rmu_short_circuit_ka,
            "ct_ratio": rmu_ct_ratio,
            "ct_class": rmu_ct_class,
            "ct_va": rmu_ct_va,
        },
        "transformer": {
            "vector_group": tr_vector_group,
            "uk_percent": tr_uk_percent,
            "tap_range": tr_tap_range,
            "cooling": tr_cooling,
        },
        "lv_busbar": {"rated_a": lv_rated_a, "short_circuit_ka": lv_short_circuit_ka},
        "cables": {
            "mv_cable_spec": mv_cable_spec,
            "lv_cable_spec": lv_cable_spec,
            "dc_cable_spec": dc_cable_spec,
        },
        "dc_fuse": {"fuse_spec": fuse_spec},
    }
