import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from discovery.run import main  # noqa: E402

if __name__ == "__main__":
    main()
