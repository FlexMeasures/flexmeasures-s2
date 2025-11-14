#!/bin/bash
# Script to run the ITHO example with debug logging
# Usage: ./run_itho_with_debug.sh [output_file]

OUTPUT_FILE="${1:-itho_debug_output.log}"

echo "Running ITHO DHW Heat Pump planning example with DEBUG logging..."
echo "Output will be saved to: $OUTPUT_FILE"
echo ""

# Navigate to the examples directory
cd "$(dirname "$0")"

# Run the example and save output
python example_schedule_itho.py 2>&1 | tee "$OUTPUT_FILE"

echo ""
echo "================================================================"
echo "Debug output saved to: $OUTPUT_FILE"
echo "================================================================"
echo ""
echo "To view the log:"
echo "  less $OUTPUT_FILE"
echo ""
echo "To search for specific patterns:"
echo "  grep 'GENERATING TIMESTEPS' $OUTPUT_FILE"
echo "  grep 'Bucket' $OUTPUT_FILE"
echo "  grep 'fill_level' $OUTPUT_FILE"
echo ""

