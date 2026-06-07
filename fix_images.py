"""
Fix image references in Chemistry Question Bank JSON files.

Problem: JSON files reference images with generic names like "0.jpg", "1.jpg"
but actual image files are named like "q17_stem_0.jpg" or "q30_optA.jpg".

Additionally, the indices in JSON come from OCR page-level numbering and may
not match the per-question 0-based indices used in the actual file names.

This script:
1. Collects all unique stem image indices per question (from qN_stem_X.jpg patterns)
2. Renumbers them from 0 per question to match actual file names
3. Updates all references: question_images, [IMG:...] in text, and option image fields
"""
import json
import re
import os
from pathlib import Path

BASE_DIR = Path(r"c:\Users\user\Desktop\Chemistry-Question-Bank")
QUESTIONS_DIR = BASE_DIR / "questions" / "DSE"
IMAGES_DIR = BASE_DIR / "images" / "DSE"


def collect_stem_indices(question):
    """Collect all unique stem image OLD indices from already-prefixed qN_stem_X.jpg patterns."""
    indices = set()
    q_num = question.get("number")

    # From question_images array: qN_stem_X.jpg or X.jpg
    for img in question.get("question_images", []):
        # Match "qN_stem_X.jpg" pattern
        m = re.match(r'q\d+_stem_(\d+)\.(jpg|png|gif)$', img)
        if m:
            indices.add(int(m.group(1)))
        else:
            # Match plain "X.jpg" pattern
            m2 = re.match(r'^(\d+)\.(jpg|png|gif)$', img)
            if m2:
                indices.add(int(m2.group(1)))

    # From [IMG:...] in question_text
    for m in re.finditer(r'\[IMG:(?:q\d+_stem_)?(\d+)\.(?:jpg|png|gif)\]', question.get("question_text", "")):
        indices.add(int(m.group(1)))

    # From [IMG:...] in option text
    for opt in question.get("options", []):
        if opt.get("text") and isinstance(opt["text"], str):
            for m in re.finditer(r'\[IMG:(?:q\d+_stem_)?(\d+)\.(?:jpg|png|gif)\]', opt["text"]):
                indices.add(int(m.group(1)))

    return sorted(indices)


def build_stem_map(question):
    """Build a mapping from old index to new 0-based stem filename prefix."""
    old_indices = collect_stem_indices(question)
    q_num = question.get("number")
    stem_map = {}
    for new_idx, old_idx in enumerate(old_indices):
        stem_map[old_idx] = f"q{q_num}_stem_{new_idx}"
    return stem_map


def fix_question_images(question, q_num, stem_map):
    """Fix image references in a single question."""
    changes_made = []

    # 1. Fix question_images array: renumber from 0
    if question.get("question_images"):
        new_images = []
        for img in question["question_images"]:
            # Match "qN_stem_X.jpg" (already prefixed)
            m = re.match(r'q\d+_stem_(\d+)\.(jpg|png|gif)$', img)
            if m:
                old_idx = int(m.group(1))
                ext = m.group(2)
            else:
                # Match plain "X.jpg"
                m = re.match(r'^(\d+)\.(jpg|png|gif)$', img)
                if m:
                    old_idx = int(m.group(1))
                    ext = m.group(2)
                else:
                    new_images.append(img)
                    continue

            if old_idx in stem_map:
                new_name = f"{stem_map[old_idx]}.{ext}"
            else:
                new_name = f"q{q_num}_stem_{old_idx}.{ext}"

            if new_name != img:
                new_images.append(new_name)
                changes_made.append(f"question_images: {img} -> {new_name}")
            else:
                new_images.append(img)
        question["question_images"] = new_images

    # 2. Fix [IMG:...] in question_text
    if question.get("question_text"):
        def replace_stem_img(match):
            old_idx = int(match.group(1))
            ext = match.group(2)
            old_text = match.group(0)
            if old_idx in stem_map:
                new_ref = f"{stem_map[old_idx]}.{ext}"
            else:
                new_ref = f"q{q_num}_stem_{old_idx}.{ext}"
            new_text = f"[IMG:{new_ref}]"
            if new_text != old_text:
                changes_made.append(f"question_text [IMG]: {old_text} -> {new_text}")
            return new_text
        question["question_text"] = re.sub(
            r'\[IMG:(?:q\d+_stem_)?(\d+)\.(jpg|png|gif)\]',
            replace_stem_img,
            question["question_text"]
        )

    # 3. Fix options
    if question.get("options"):
        for opt in question["options"]:
            label = opt.get("label", "")

            # 3a. Fix [IMG:...] in option text
            if opt.get("text") and isinstance(opt["text"], str):
                def replace_opt_text_img(match):
                    old_idx = int(match.group(1))
                    ext = match.group(2)
                    old_text = match.group(0)
                    if old_idx in stem_map:
                        new_ref = f"{stem_map[old_idx]}.{ext}"
                    else:
                        new_ref = f"q{q_num}_stem_{old_idx}.{ext}"
                    new_text = f"[IMG:{new_ref}]"
                    if new_text != old_text:
                        changes_made.append(f"option {label} text [IMG]: {old_text} -> {new_text}")
                    return new_text
                opt["text"] = re.sub(
                    r'\[IMG:(?:q\d+_stem_)?(\d+)\.(jpg|png|gif)\]',
                    replace_opt_text_img,
                    opt["text"]
                )

            # 3b. Fix "image": "X.jpg" in option -> qN_opt{L}.jpg
            if opt.get("image") and isinstance(opt["image"], str):
                img = opt["image"]
                # Match plain "X.jpg"
                m = re.match(r'^(\d+)\.(jpg|png|gif)$', img)
                if m:
                    ext = m.group(2)
                    new_name = f"q{q_num}_opt{label}.{ext}"
                    if new_name != img:
                        changes_made.append(f"option {label} image: {img} -> {new_name}")
                        opt["image"] = new_name

    return changes_made


def process_year(year):
    """Process a single year's JSON file."""
    json_path = QUESTIONS_DIR / year / "1A.json"
    if not json_path.exists():
        print(f"  SKIP: {json_path} not found")
        return 0

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    total_changes = 0
    for question in data.get("questions", []):
        q_num = question.get("number")
        if q_num is None:
            continue

        stem_map = build_stem_map(question)
        changes = fix_question_images(question, q_num, stem_map)
        if changes:
            print(f"  Q{q_num}: {len(changes)} change(s)")
            for c in changes:
                print(f"    - {c}")
            total_changes += len(changes)

    if total_changes > 0:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"  SAVED: {total_changes} total changes written to {json_path}")
    else:
        print(f"  No changes needed for {year}")

    return total_changes


def main():
    years = sorted([d.name for d in QUESTIONS_DIR.iterdir() if d.is_dir()])
    print(f"Found {len(years)} years: {years}")
    print()

    grand_total = 0
    for year in years:
        print(f"Processing {year}...")
        changes = process_year(year)
        if changes:
            grand_total += changes
        print()

    print(f"DONE. Total changes across all years: {grand_total}")


if __name__ == "__main__":
    main()
