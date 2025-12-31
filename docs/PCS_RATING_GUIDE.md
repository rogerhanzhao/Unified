# PCS Rating Selection Guide

## Overview
The AC Sizing page now supports five standard PCS ratings plus unlimited custom values for maximum flexibility in system design.

## Standard PCS Ratings

### Available Options
- **1250 kW** - Smallest modular option
- **1500 kW** - Common industrial standard  
- **1725 kW** - Optimized for 3-phase balance
- **2000 kW** - ✨ NEW - Mid-range option
- **2500 kW** - High-capacity option

## How to Select PCS Configuration

### Step 1: Choose AC:DC Ratio
- **1:1** - 1 AC Block per 1 DC Block (maximum modularity)
- **1:2** - 1 AC Block per 2 DC Blocks (balanced, recommended)
- **1:4** - 1 AC Block per 4 DC Blocks (compact design)

### Step 2: Select PCS Configuration

#### Option A: Use Recommended Configuration
1. Click the "Select PCS Configuration" dropdown
2. Choose from available combinations:
   - **2 PCS per Block**: 2×1250, 2×1500, 2×1725, 2×2000, 2×2500
   - **4 PCS per Block**: 4×1250, 4×1500, 4×1725, 4×2000, 4×2500
3. System automatically calculates container size and total power

#### Option B: Use Custom PCS Rating ✨
1. Click the "Select PCS Configuration" dropdown
2. Scroll to bottom and select **"🔧 Custom PCS Rating..."**
3. Right column displays two input fields:
   - **PCS Count per AC Block**: Enter 1-6 PCS per block
   - **PCS Rating (kW)**: Enter any value 1000-5000 kW (step: 100 kW)
4. System automatically validates and calculates container size

### Step 3: Container Size Determination
Container type is automatically selected based on **single AC Block power**:

```
Single AC Block Power = (PCS Count) × (PCS Rating) / 1000

If Single AC Block Power > 5.0 MW → 40ft container
If Single AC Block Power ≤ 5.0 MW → 20ft container
```

**Examples:**
| PCS Count | PCS Rating | Block Power | Container |
|-----------|-----------|------------|-----------|
| 2 × 1250  | 2500 kW   | 2.5 MW    | 20ft      |
| 2 × 2000  | 4000 kW   | 4.0 MW    | 20ft      |
| 2 × 2500  | 5000 kW   | 5.0 MW    | 20ft      |
| 4 × 1250  | 5000 kW   | 5.0 MW    | 20ft      |
| 4 × 1500  | 6000 kW   | 6.0 MW    | 40ft ✅   |
| 4 × 2000  | 8000 kW   | 8.0 MW    | 40ft ✅   |

## Power Validation

### Overhead Calculation
```
Power Overhead = (Total AC Power) - (POI Power Requirement)
Overhead % = Power Overhead / POI Power Requirement × 100%
```

### Warnings
- ⚠️ **Power Overhead Warning**: If overhead > 30% of POI requirement
- ⚠️ **Energy Deficit**: If DC energy < 95% of POI energy requirement
- ⚠️ **Energy Excess**: If DC energy > 105% of POI energy requirement

### Errors
- ❌ **Insufficient Power**: If total AC power < 95% of POI requirement
- ❌ **Insufficient Energy**: If DC energy < 95% of POI energy requirement

## Custom PCS Rating Examples

### Example 1: Optimized 6 MW System
- **Custom Config**: 3 PCS × 2000 kW = 6000 kW per block
- **Total Power**: 6.0 MW per block
- **Container**: 40ft (exceeds 5 MW threshold)
- **Use Case**: When you need exactly 6 MW and 3 PCS is feasible

### Example 2: Mid-Range Efficiency
- **Custom Config**: 2 PCS × 1800 kW = 3600 kW per block
- **Total Power**: 3.6 MW per block
- **Container**: 20ft
- **Use Case**: Specific equipment ratings not in standard list

### Example 3: Large-Scale Project
- **Custom Config**: 5 PCS × 1600 kW = 8000 kW per block
- **Total Power**: 8.0 MW per block
- **Container**: 40ft
- **Use Case**: When exact 8 MW is required with 5-unit configuration

## Tips & Best Practices

1. **Start with Recommended Options**: They're optimized for typical projects
2. **Use Custom for Exceptions**: Only when standard configs don't fit your needs
3. **Consider Container Economics**: 40ft adds cost; ensure > 5 MW justifies it
4. **Review Overhead**: Keep overhead under 30% for cost efficiency
5. **Validate Energy Match**: Ensure DC energy covers full MWh requirement
6. **Check DC Block Allocation**: Verify DC blocks distribute evenly across PCS units

## Troubleshooting

### "Power overhead: X MW (>30% of POI requirement)"
- **Cause**: Selected PCS configuration results in excess capacity
- **Solution**: Try custom config with lower PCS count or smaller rating

### "Insufficient power: X MW < Y MW"
- **Cause**: Total AC power is below requirement
- **Solution**: Increase PCS count or rating; reconsider DC:AC ratio

### "Excess energy: X MWh > Y MWh"
- **Cause**: DC blocks provide more energy than required
- **Solution**: Return to DC Sizing page and reduce DC block count

### Custom Input Not Accepting Value
- **Check Range**: PCS count 1-6, Rating 1000-5000 kW
- **Step Validation**: PCS count uses 1 kW steps, Rating uses 100 kW steps
- **Reload Page**: If UI freezes, press F5 or restart browser

## FAQs

**Q: Can I use PCS ratings outside 1000-5000 kW?**
A: Currently limited to 1000-5000 kW for system constraints. Contact support for edge cases.

**Q: Will custom configs be saved for future projects?**
A: Not yet. Consider documenting your custom config for team reference.

**Q: How does 2000 kW compare to 1725 kW?**
A: 2000 kW is ~16% higher capacity, useful when 1725 leaves too much overhead.

**Q: What happens if I exceed 40ft container limits?**
A: System validates that 40ft can fit all equipment. See system warnings during Run AC Sizing.

## Support & Feedback

For issues or feature requests related to PCS rating selection:
- Check this guide for common scenarios
- Review validation warnings in AC Sizing results
- Contact technical support with your project file
