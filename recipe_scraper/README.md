# Recipe Manager

A desktop app for saving, organizing, and scaling recipes scraped from any cooking website.

---

## Download & Run (no install needed)

1. Go to the [**Releases**](../../releases) page
2. Download **RecipeManager.exe**
3. Double-click it — that's it

Your recipes are stored in `recipes.db` next to the .exe file and persist across updates.

---

## Features

- **Scrape any recipe URL** – paste a link, get ingredients & instructions instantly
- **My Recipes** – save, categorize, sort, and search your collection
- **Scale servings** – adjusts all ingredient amounts automatically
- **Make Default** – bake a scaled serving size into the recipe permanently
- **Shopping List** – combine ingredients across multiple recipes/meals, smart unit conversion, printable
- **Meals** – group recipes into meals with categories
- **Create recipes from scratch** – type everything in manually

---

## For Developers

### Run locally (requires Python 3.10+)

```bash
git clone https://github.com/YOUR_USERNAME/recipe-manager.git
cd recipe-manager
pip install -r requirements.txt
python launcher.py
```

### Build the .exe yourself

```bash
pip install -r requirements.txt
pip install pyinstaller
pyinstaller recipe_manager.spec
# Output: dist/RecipeManager.exe
```

### Release a new version

1. Commit your changes
2. Create and push a version tag:
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```
3. GitHub Actions automatically builds the .exe and attaches it to a Release

---

## Tech stack

- **Backend:** Python, Flask, SQLite
- **Scraping:** [recipe-scrapers](https://github.com/hhursev/recipe-scrapers)
- **Desktop window:** [pywebview](https://pywebview.flowrl.com/)
- **Packaging:** PyInstaller
- **CI/CD:** GitHub Actions
