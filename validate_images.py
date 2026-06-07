"""
Validate that all image references in JSON files point to actual image files.
Also fixes edge cases like empty string "image": "".
"""
import json
import re
from pathlib import Path

BASE_DIR = Path(r"c:\Users\user\Desktop\Chemistry-Question-Bank")
QUESTIONS_DIR = BASE_DIR / "questions" / "DSE"
IMAGES_DIR = BASE_DIR / "images" / "DSE"


def validate_year(year):
    """Check all image references for a year's JSON against actual files."""
    json_path = QUESTIONS_DIR / year / "1A.json"
    images_dir = IMAGES_DIR / year / "1A"
    
    if not json_path.exists():
        return
    
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    actual_files = set()
    if images_dir.exists():
        actual_files = {f.name for f in images_dir.iterdir() if f.is_file()}
    
    missing = []
    fixed_empty = 0
    
    for question in data.get("questions", []):
        q_num = question.get("number")
        
        # Check question_images
        for img in question.get("question_images", []):
            if img and img not in actual_files:
                missing.append(f"Q{q_num} question_images: {img}")
        
        # Check [IMG:...] in question_text
        for m in re.finditer(r'\[IMG:([^\]]+)\]', question.get("question_text", "")):
            img = m.group(1)
            if img not in actual_files:
                missing.append(f"Q{q_num} question_text [IMG]: {img}")
        
        # Check options
        for opt in question.get("options", []):
            label = opt.get("label", "")
            
            # Fix empty string image
            if opt.get("image") == "":
                opt["image"] = None
                fixed_empty += 1
                print(f"  Q{q_num} option {label}: fixed empty image string -> null")
            
            # Check option image
            if opt.get("image") and isinstance(opt["image"], str):
                if opt["image"] not in actual_files:
                    missing.append(f"Q{q_num} option {label} image: {opt['image']}")
            
            # Check [IMG:...] in option text
            if opt.get("text") and isinstance(opt["text"], str):
                for m in re.finditer(r'\[IMG:([^\]]+)\]', opt["text"]):
                    img = m.group(1)
                    if img not in actual_files:
                        missing.append(f"Q{q_num} option {label} text [IMG]: {img}")
    
    if missing:
        print(f"  MISSING FILES ({len(missing)}):")
        for m in missing:
            print(f"    - {m}")
    
    if fixed_empty > 0:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"  SAVED: {fixed_empty} empty image strings fixed")
    
    return len(missing), fixed_empty


def main():
    years = sorted([d.name for d in QUESTIONS_DIR.iterdir() if d.is_dir()])
    
    total_missing = 0
    total_fixed = 0
    
    for year in years:
        print(f"Checking {year}...")
        m, f = validate_year(year)
        total_missing += m
        total_fixed += f
        print()
    
    print(f"SUMMARY: {total_missing} missing images, {total_fixed} empty strings fixed")


if __name__ == "__main__":
    main()
