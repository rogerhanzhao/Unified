# Guarantee Year Fix - Validation Guide

## What Was Fixed
The Executive Summary in exported DOCX reports (V2.1) was missing critical data from the DC Sizing stage:
- Guarantee Year was showing 0
- POI Usable Energy @ Guarantee Year could not be verified

## Root Cause
The `pack_stage13_output()` function in `calb_sizing_tool/ui/stage4_interface.py` was not preserving the `poi_guarantee_year` and other critical Stage 1 fields when packaging the DC sizing results.

## Solution
Updated `pack_stage13_output()` to explicitly preserve:
- `poi_guarantee_year` - The year at which the POI energy target must be met
- `project_life_years` - Total project lifetime
- `cycles_per_year` - Annual charge/discharge cycles
- All component efficiency values - For consistency in efficiency chain calculation

## Validation Steps

### Step 1: Verify the Fix in Code
```bash
cd /opt/calb/prod/CALB_SIZINGTOOL
grep -A 5 "output\[\"poi_guarantee_year\"\]" calb_sizing_tool/ui/stage4_interface.py
```
Should show the new line preserving poi_guarantee_year.

### Step 2: Test Export with Non-Zero Guarantee Year
1. Open the web app: http://[server]:8511
2. Go to Dashboard → DC Sizing
3. Set "POI Guarantee Year" to 5 (or any non-zero value)
4. Complete DC Sizing
5. Go to AC Sizing and complete
6. Go to Report Export
7. Download "Download Combined Report V2.1"
8. Open the DOCX file
9. Look for "Executive Summary" section
10. Verify:
    - "Guarantee Year (from COD)" shows 5 (not 0)
    - "POI Usable @ Guarantee Year (MWh)" shows a reasonable value

### Step 3: Validate Data Consistency
In the exported report:
- Compare "POI Usable @ Guarantee Year" with "POI Usable Energy vs Year" chart
  - The value should match the bar at year 5
- Check "DC Nameplate @BOL" matches DC Sizing page
- Check efficiency values match DC Sizing page

### Step 4: Test with Guarantee Year = 0
1. Repeat steps 1-2 but with "POI Guarantee Year" = 0
2. Exported report should show:
    - Guarantee Year = 0
    - POI Usable @ Guarantee Year = POI Usable Energy @BOL (Year 0)

## Expected Output Examples

### With Guarantee Year = 5:
```
Executive Summary Table:
- POI Power Requirement (MW): 100.00
- POI Energy Requirement (MWh): 400.00
- POI Energy Guarantee (MWh): 400.00
- Guarantee Year (from COD): 5                    ← Should be 5, not 0
- POI Usable @ Guarantee Year (MWh): 370.00     ← Should match Stage 3 at year 5
- DC Blocks Total: 90
- ...
```

### With Guarantee Year = 0:
```
Executive Summary Table:
- ...
- Guarantee Year (from COD): 0
- POI Usable @ Guarantee Year (MWh): 400.00     ← Should match Year 0 value
- ...
```

## Files Modified
- `calb_sizing_tool/ui/stage4_interface.py` - Lines 54-62 added

## Backward Compatibility
✓ No breaking changes
✓ Existing session state structure preserved
✓ All default values maintained
✓ Only adds missing fields, doesn't remove or change existing ones

## Rollback Instructions (if needed)
```bash
cd /opt/calb/prod/CALB_SIZINGTOOL
git checkout calb_sizing_tool/ui/stage4_interface.py
sudo systemctl restart calb-sizingtool@prod.service
```

## Support
If the guarantee year still shows as 0 after this fix:
1. Clear browser cache and reload
2. Check that DC Sizing has been re-run after the fix
3. Verify the Streamlit service has been restarted
4. Check logs: `sudo journalctl -u calb-sizingtool@prod.service -n 50`
