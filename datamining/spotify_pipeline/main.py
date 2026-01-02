import traceback

from extract_library import load_library
from extract_playlists import load_playlists
from write_zilver import write_zilver
from goud import build_goud
from write_goud import write_goud


def step(name, func, *args, critical=True):
    """
    Voer een pipeline-stap uit met logging en error-handling.
    """
    print("\n=== Stap: " + name + " ===")

    try:
        result = func(*args)
        print("[OK] Succes: " + name)
        return result

    except Exception as e:
        print("[FOUT] In stap '" + name + "': " + str(e))
        traceback.print_exc()

        if critical:
            print("Pipeline gestopt wegens kritieke fout.")
            raise SystemExit(1)
        else:
            print("Niet-kritieke fout. Pipeline gaat verder.")
            return None


def main():
    print("\n==============================")
    print("   SPOTIFY PIPELINE START")
    print("==============================\n")

    # 1. Library laden
    df_library = step("Library laden", load_library)

    # 2. Library naar Zilver
    step("Library wegschrijven naar Zilver", write_zilver, df_library, "library_astrid.xlsx")

    # 3. Playlists laden
    df_playlists = step("Playlists laden", load_playlists)

    # 4. Playlists naar Zilver
    step("Playlists wegschrijven naar Zilver", write_zilver, df_playlists, "playlist_astrid.xlsx")

    # 5. Goud bouwen
    df_goud = step("Goud-laag bouwen", build_goud)

    # 6. Goud naar Excel
    step("Goud wegschrijven", write_goud, df_goud, "goud_master.xlsx")

    print("\n==============================")
    print("   PIPELINE SUCCESVOL AFGEROND")
    print("==============================\n")


if __name__ == "__main__":
    main()
