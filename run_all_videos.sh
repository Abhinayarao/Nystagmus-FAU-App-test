#!/bin/bash
videos=(
"/Users/muskanjoshi/Desktop/Test Videos/IMG_2856.MOV"
"/Users/muskanjoshi/Desktop/Test Videos/IMG_2858.MOV"
"/Users/muskanjoshi/Desktop/Test Videos/IMG_2861.MOV"
"/Users/muskanjoshi/Desktop/Test Videos/IMG_2864.MOV"
"/Users/muskanjoshi/Desktop/Test Videos/IMG_2992.MOV"
"/Users/muskanjoshi/Desktop/Test Videos/IMG_2993.MOV"
"/Users/muskanjoshi/Desktop/Test Videos/IMG_2995.MOV"
"/Users/muskanjoshi/Desktop/Test Videos/IMG_3299.MOV"
)
for video in "${videos[@]}"; do
    video_name=$(basename "$video" .MOV)
    echo "Processing $video_name..."
    /Users/muskanjoshi/Desktop/Nystagmus-FAU-App-/venv/bin/python3 python/Left_Beat.py "$video"
    mkdir -p "/Users/muskanjoshi/Desktop/Threshold 5"
    cp plot5_spv_analysis.png "/Users/muskanjoshi/Desktop/Threshold 5/SPV_${video_name}.png"
    echo "Saved: SPV_${video_name}.png"
done
echo "All done!"