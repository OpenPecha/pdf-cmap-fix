"""Allow ``python -m pdf_cmap_fix`` as an alternative to the ``pdf-cmap-fix`` console script (gid tier)."""
from pdf_cmap_fix.gid.extractor import main

if __name__ == "__main__":
    main()
