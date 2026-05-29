import os
import time
from pathlib import Path
from PIL import Image
from collections import deque

def clean_file_transparency(path: Path) -> int:
    try:
        img = Image.open(path).convert("RGBA")
    except Exception as e:
        print(f"Error loading {path.name}: {e}")
        return 0
        
    width, height = img.size
    pixels = img.load()
    
    # 1D bytearray for visited check (O(1) flat access, 0 object allocation)
    visited = bytearray(width * height)
    queue = deque()
    
    # Enqueue all border pixels (flat indices)
    for x in range(width):
        queue.append(x)  # y = 0
        visited[x] = 1
        queue.append((height - 1) * width + x)
        visited[(height - 1) * width + x] = 1
        
    for y in range(1, height - 1):
        idx_left = y * width
        queue.append(idx_left)
        visited[idx_left] = 1
        
        idx_right = y * width + (width - 1)
        queue.append(idx_right)
        visited[idx_right] = 1

    bg_pixels = []
    
    # BFS (Inlined for speed, avoiding function calls)
    while queue:
        idx = queue.popleft()
        cy = idx // width
        cx = idx % width
        
        r, g, b, a = pixels[cx, cy]
        if a == 0 or (a == 255 and r >= 230 and g >= 230 and b >= 230 and abs(r - g) <= 6 and abs(r - b) <= 6 and abs(g - b) <= 6):
            bg_pixels.append(idx)
            # Check 4-neighbors
            for nx, ny in [(cx-1, cy), (cx+1, cy), (cx, cy-1), (cx, cy+1)]:
                if 0 <= nx < width and 0 <= ny < height:
                    nidx = ny * width + nx
                    if not visited[nidx]:
                        visited[nidx] = 1
                        queue.append(nidx)
                        
    # Set background pixels to transparent
    modified_count = 0
    for idx in bg_pixels:
        cy = idx // width
        cx = idx % width
        if pixels[cx, cy][3] != 0:
            pixels[cx, cy] = (0, 0, 0, 0)
            modified_count += 1
            
    if modified_count > 0:
        img.save(path, "PNG")
        print(f"Cleaned {path.relative_to(Path.cwd())}: Modified {modified_count} pixels.")
    else:
        print(f"Skipped {path.relative_to(Path.cwd())}: Already clean.")
        
    return modified_count

def main():
    assets_dir = Path("assets/private").resolve()
    if not assets_dir.exists():
        print(f"Directory {assets_dir} does not exist.")
        return
        
    print("Starting optimized transparency cleanup on custom assets...")
    png_files = list(assets_dir.rglob("*.png"))
    print(f"Found {len(png_files)} PNG files to inspect.")
    
    t_start = time.time()
    total_cleaned = 0
    for file_path in png_files:
        modified = clean_file_transparency(file_path)
        if modified > 0:
            total_cleaned += 1
            
    t_elapsed = time.time() - t_start
    print(f"Finished transparency cleanup in {t_elapsed:.2f} seconds. Processed {total_cleaned}/{len(png_files)} files.")

if __name__ == "__main__":
    main()
