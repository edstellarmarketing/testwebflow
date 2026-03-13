# Edstellar Course → Webflow CMS Pusher

Push course content from structured text (Google Docs) to Webflow CMS "Courses" collection with one click.

## Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Get Your Webflow API Token
1. Go to your Webflow project → **Project Settings** → **API access**
2. Click **"Generate API token"**
3. Copy the token (you'll paste it in the app)

### 3. Get Your Collection ID
Your Courses collection ID is visible in the CMS → Courses → Collection Settings.
From your screenshot: `698afc4a706f88cce608a4ac`

### 4. Run the App
```bash
streamlit run app.py
```

## How It Works

### For Writers
1. Copy the Google Doc template (available in the app's "Template Guide" tab)
2. Fill in each `## Section` with course content
3. Paste the completed content into the app
4. Click **Push to Webflow CMS**

### Field Mapping
The app maps section headers to Webflow CMS field slugs:

| Doc Section | Webflow Field Slug |
|---|---|
| Course Name | `name` |
| Slug | `slug` (auto-generated if blank) |
| Meta Title | `meta-title` |
| Meta Description | `meta-description` |
| Main Heading | `main-heading` |
| Course Description | `course-description` |
| Key Highlights | `key-highlights` |
| Target Audience | `target-audience` |
| Learning Outcomes | `learning-outcomes` |
| Course Outlines | `course-outlines-rich-text` |
| ... | ... (30+ fields supported) |

### Rich Text Conversion
Fields like Course Description, Key Highlights, etc. are automatically converted from Markdown-style text to HTML:
- Bullet points (`-` or `•`) → `<ul><li>...</li></ul>`
- Bold text (`**text**`) → `<h4>text</h4>`
- Sub-headings (`### Title`) → `<h3>Title</h3>`
- Plain paragraphs → `<p>text</p>`

## Important Notes

### Field Slug Verification
The field slugs in this app are based on the CMS screenshots. When you first run the app:
1. Enter your API token in the sidebar
2. Click **"Fetch Collection Schema"** to see the actual field slugs
3. If any slugs differ, update the `FIELD_MAP` dictionary in `app.py`

### Fields NOT Handled by This App
These fields require manual setup in Webflow:
- **Images** (Course Thumbnail, OG Image, Twitter Image, Banner, Brand Logo) — upload via Webflow UI
- **Reference fields** (Which Course Level, Type, Category, Subcategory, Trainers) — set via Webflow UI
- **Popular** toggle — set manually
- **PORTAL ID** — system field, don't touch

### API Limits
- Webflow API rate limit: 60 requests/minute
- Collection items can be created as drafts or published immediately
- Max 100 items per bulk request

## Next Steps / Enhancements
- [ ] Google Docs API integration (read directly from a Doc)
- [ ] Batch upload from CSV/Excel
- [ ] Image upload via Webflow Assets API
- [ ] Reference field auto-linking (categories, subcategories)
- [ ] Google Apps Script sidebar button for one-click push from Docs
