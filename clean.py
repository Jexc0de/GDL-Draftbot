INPUT_FILE = "pokemonlist_cleaned.txt"
OUTPUT_FILE = "pokemonlist_mega_swapped.txt"

with open(INPUT_FILE, "r", encoding="utf-8") as infile, \
     open(OUTPUT_FILE, "w", encoding="utf-8") as outfile:

    for line in infile:
        line = line.rstrip("\n")
        if not line:
            continue

        parts = [p.strip() for p in line.split(",")]
        name = parts[0]

        if "-Mega" in name:
            segments = name.split("-")

            # Find the Mega segment safely
            if "Mega" in segments:
                mega_index = segments.index("Mega")

                base = "-".join(segments[:mega_index])
                suffix = segments[mega_index + 1:]  # X / Y / Z if present

                name = "Mega-" + base
                if suffix:
                    name += "-" + "-".join(suffix)

        parts[0] = name
        outfile.write(",".join(parts) + "\n")
