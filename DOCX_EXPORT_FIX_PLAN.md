# DOCX Export Report Fix Plan

## Current Issues Analysis

### Issue A: Efficiency Chain Data Inconsistency (HIGH PRIORITY)
**Problem**: Report uses hardcoded defaults instead of actual DC SIZING values
- Current code in `report_v2.py` lines 264-268 uses `.get("key", 0.97)` defaults
- These defaults are used because `report_context.py` doesn't properly capture actual DC sizing efficiency values
- Result: "one-way Efficiency Chain" table shows placeholder values, not actual DC computed values

**Root Cause**:
- DC SIZING page computes: `eff_dc_cables`, `eff_pcs`, `eff_mvt`, `eff_ac_sw`, `eff_hvt`, `eff_chain`
- These are stored in `stage1` dict but `report_context.py` only captures them with weak defaults
- When report exports, it uses `.get(key, default)` which pulls the default instead of actual value

**Solution**:
1. Ensure `report_context.py` correctly reads all component efficiencies from `stage1`
2. Add validation that all efficiency values are present before export
3. Modify `report_v2.py` to assert efficiency values exist (not use defaults)
4. Add disclaimer: "Efficiency chain values do not include Auxiliary losses"

### Issue B: AC Configuration Details - Verbose Per-Block Listing (MEDIUM PRIORITY)
**Problem**: Report lists every single AC Block with identical config (creates long tables)
- Current code in `report_v2.py` lines 413-419 iterates over all blocks
- For 23 AC Blocks with identical config, this produces 23 identical rows

**Solution**:
1. Implement AC config aggregation by "signature"
2. Signature = (pcs_per_block, pcs_kw, transformer_mva, ac_block_size_mw)
3. Generate summary row: "23 AC Blocks with 2×2500kW config"
4. Only list exception blocks separately

### Issue C: SLD/Layout Drawing Issues (MEDIUM PRIORITY - drawing only, not data)
**Problem**: 
- SLD shows DC BUSBAR as if shared between PCS (circuit coupling visual error)
- Layout shows DC Block internal with 2×3 modules + small box (should be 1×6, no box)

**Solution**: Modify drawing generation logic only (no data/sizing changes):
1. SLD: Ensure each PCS has independent DC BUSBAR (no shared busbar visual)
2. Layout: Change DC Block internal from 2×3 to 1×6 single row, remove left side small box

### Issue D: Physical/Unit Consistency Validation (MEDIUM PRIORITY)
**Problem**: No validation that exported values are self-consistent
- Could have mismatches between AC blocks × size ≠ total AC power
- Could have unit inconsistencies in efficiency expressions

**Solution**:
1. Add validator function: `_validate_report_consistency(ctx) -> List[str]`
2. Checks:
   - `ac_blocks_total × ac_block_size_mw ≈ sum of individual AC powers`
   - Efficiency chain total ≈ product of components (same mouth)
   - All efficiency values present and in (0, 1]
   - Energy/power units and labels consistent throughout
3. Log warnings but do not block export (data already confirmed by user)

---

## Modules to Modify

### 1. `report_context.py`
- **Fix**: Ensure all efficiency component fracs are read from `stage1` without weak defaults
- **Function**: `build_report_context()` (lines 206-213)
- **Change**: Remove `.or` fallback defaults; instead validate presence

### 2. `report_v2.py`
- **Fix A**: Efficiency chain table (lines 262-270)
  - Remove `.get("key", default)` pattern
  - Assert values are present
  - Add notice about not including Auxiliary
  
- **Fix B**: AC Block configuration details (lines 413-419)
  - Implement AC config aggregation
  - Group blocks by signature
  - Show count per signature instead of per-block
  
- **Fix C**: Add validation function (new)
  - Insert call before export
  - Log warnings but continue

### 3. `export_docx.py` (if needed for validation hook)
- Add pre-export validation step

---

## Data Sources (Truth)

### Efficiency Components - From DC SIZING (stage1):
```
eff_dc_cables_frac    <- DC SIZING computed from user input (default 0.995)
eff_pcs_frac          <- DC SIZING computed from user input (default 0.985)
eff_mvt_frac          <- DC SIZING computed from user input (default 0.995)
eff_ac_cables_sw_rmu_frac  <- DC SIZING computed (default 0.992)
eff_hvt_others_frac   <- DC SIZING computed (default 1.0)
eff_dc_to_poi_frac    <- DC SIZING computed = product of all above
```

### AC Configuration - From AC SIZING (ac_output):
```
num_blocks            <- Number of AC Blocks
pcs_per_block         <- PCS quantity per block
pcs_kw                <- PCS rated power
pcs_count_by_block    <- PCS count per individual block (may vary)
dc_blocks_per_ac      <- DC blocks allocated to each AC block
selected_ratio        <- DC:AC ratio string (e.g., "1:4")
```

---

## Tests to Add/Update

### Test: Efficiency Chain Consistency
- Build context with known DC sizing values
- Assert report shows those exact values (not defaults)
- Assert all components present in table

### Test: AC Config Aggregation
- 10 AC blocks with 2 PCS each → report shows "10 blocks, 2×PCS_kW"
- 5 blocks with 2 PCS, 5 blocks with 4 PCS → report shows both signatures separately

### Test: Validation Function
- Consistency checks pass for valid context
- Consistency checks log warnings for edge cases (but don't block)

---

## Acceptance Criteria

1. **Efficiency Chain**:
   - ✅ Values match DC SIZING page exactly
   - ✅ All components present (not defaults)
   - ✅ Notice: "Does not include Auxiliary losses"
   - ✅ Total efficiency ≈ product of components (same mouth/scope)

2. **AC Configuration**:
   - ✅ No per-block repetition for identical configs
   - ✅ Summary shows count + signature
   - ✅ Only exceptions listed separately
   - ✅ Information complete and accurate

3. **SLD/Layout**:
   - ✅ Each PCS has independent DC BUSBAR (no visual coupling)
   - ✅ DC Block internal: 1×6 single row, no left side small box
   - ✅ Diagram SVG/PNG generated correctly

4. **Validation**:
   - ✅ Consistency checks run pre-export (logged, not blocking)
   - ✅ No missing data in export
   - ✅ All user-confirmed details preserved

5. **Backward Compatibility**:
   - ✅ Export filename, format, entry point unchanged
   - ✅ Existing chapter structure preserved
   - ✅ Sizing logic untouched
   - ✅ No "Auxiliary" mentioned in report

