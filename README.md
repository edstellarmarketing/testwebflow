# Edstellar Course → Webflow CMS Pusher (v2)

Push course content from **Google Docs** to Webflow CMS "Courses" collection with one click.

## What's New in v2
- **Google Docs integration** — Fetch content directly from a Google Doc URL
- **Two auth modes** — Public docs (zero setup) or Service Account (private docs)
- **Batch mode** — Push multiple courses from multiple Google Docs at once
- **Structured parsing** — Automatically maps Google Doc headings to Webflow fields
- **Rich text conversion** — Bullets, sub-headings, and paragraphs auto-convert to HTML

## Quick Start

### 1. Install
```bash
pip install -r requirements.txt
```

### 2. Run
```bash
streamlit run app.py
```

### 3. Configure (in the sidebar)
- Paste your **Webflow API Token**
- Choose Google auth method (Public or Service Account)

## Google Docs Integration

### Option A: Public Docs (Zero Setup)
1. Create your course doc using the template
2. Click **Share** → **Anyone with the link** → **Viewer**
3. Paste the URL in the app → Click **Fetch Document**

This is the easiest option. No API keys or service accounts needed. The only requirement is the doc must be publicly viewable.

### Option B: Service Account (Private Docs)
For docs that can't be made public:

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project (or use existing)
3. Enable **Google Docs API** and **Google Drive API**
4. Go to **IAM & Admin** → **Service Accounts** → **Create Service Account**
5. Create a key (JSON format) and download it
6. Share each Google Doc with the service account email (e.g., `my-sa@project.iam.gserviceaccount.com`)
7. Upload the JSON key in the app's sidebar

### Google Doc Format
Writers should use this structure:

```
## Course Name          ← Heading 2 (section separator)
The actual course name

## Meta Title           ← Another Heading 2
SEO title here...

## Course Description   ← Heading 2
Description text...

### Module 1: Intro     ← Heading 3 (sub-heading within section)
- Bullet point 1       ← Becomes <li> in rich text
- Bullet point 2
```

**Key rules:**
- **Heading 2** = Field separator (maps to Webflow CMS field)
- **Heading 3** = Sub-heading (becomes `<h3>` in rich text)
- **Bullets** = List items (become `<ul><li>`)
- **Plain text** = Paragraphs (become `<p>`)

## Webflow Setup

### Get Your API Token
1. Webflow project → **Project Settings** → **API access**
2. Click **Generate API token**
3. Copy and paste into the app

### Get Collection ID
Your Courses collection ID: `698afc4a706f88cce608a4ac`
(Visible in CMS → Courses → Collection Settings)

### Verify Field Slugs
**IMPORTANT**: On first run, click **Fetch Collection Schema** in the sidebar. This shows the exact field slugs Webflow uses. If any differ from what's in the app, update the `FIELD_MAP` dictionary in `app.py`.

## Field Mapping

| Google Doc Section | Webflow Field Slug | Type |
|---|---|---|
| Course Name | `name` | Plain Text |
| Slug | `slug` | Plain Text (auto-generated) |
| Meta Title | `meta-title` | Plain Text |
| Meta Description | `meta-description` | Plain Text |
| Canonical Link | `canonical-link` | Plain Text |
| Primary Keyword | `primary-keyword` | Plain Text |
| Keyword Search Volume | `keyword-search-volume` | Plain Text |
| Main Heading | `main-heading` | Plain Text |
| Dynamic Course Name | `dynamic-course-name` | Plain Text |
| Delivery Type | `delivery-type` | Plain Text |
| Duration | `duration` | Plain Text |
| Course Description | `course-description` | Rich Text → HTML |
| Skill Data Header | `skill-data-header` | Plain Text |
| Skill Data Paragraph | `skill-data-paragraph` | Plain Text |
| Skill Data Pointers | `skill-data-pointers` | Rich Text → HTML |
| Courses Card Pointers | `courses-card-pointers` | Rich Text → HTML |
| Key Highlights | `key-highlights` | Rich Text → HTML |
| Target Audience | `target-audience` | Rich Text → HTML |
| Target Audience Points | `target-audience-points` | Rich Text → HTML |
| Pre-Requisites | `pre-requisites` | Rich Text → HTML |
| Learning Outcomes | `learning-outcomes` | Rich Text → HTML |
| Overview | `overview` | Rich Text → HTML |
| Course Outlines | `course-outlines-rich-text` | Rich Text → HTML |
| Conclusion | `conclusion` | Rich Text → HTML |
| Why Choose Edstellar | `why-choose-edstellar` | Rich Text → HTML |
| What Sets Us Apart | `what-sets-us-apart` | Rich Text → HTML |
| Drive Team Excellence Heading | `drive-team-excellence-heading` | Rich Text → HTML |
| Testimonials Heading and Paragraph | `testimonials-heading-and-paragraph` | Rich Text → HTML |
| Internal Links for Courses | `internal-links-for-courses` | Rich Text → HTML |

## Batch Mode

To push multiple courses at once:
1. Create one Google Doc per course (using the template)
2. Go to the **Google Doc Input** tab → **Batch Mode** section
3. Paste all doc URLs (one per line)
4. Click **Fetch All & Push to Webflow**

All items are created as drafts. You can review and publish them in Webflow.

## What's NOT Automated

| Field | Why | Workaround |
|---|---|---|
| Images (Thumbnail, OG, Twitter, Banner, Logo) | Webflow needs file uploads via Assets API | Upload manually in Webflow |
| Course Level / Type / Category / Subcategory | These are Option/Reference fields needing IDs | Set manually in Webflow |
| Popular toggle | Boolean field | Set manually |
| PORTAL ID | System field — DO NOT TOUCH | Never modify |
| Trainers For Course | Multi-reference to Trainers collection | Set manually |

## Deployment Options

### Streamlit Cloud (Recommended)
1. Push to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your repo
4. Add secrets in Streamlit Cloud settings:
   ```toml
   [webflow]
   api_token = "your-token-here"
   collection_id = "698afc4a706f88cce608a4ac"
   ```

### Local
```bash
streamlit run app.py
```

## Troubleshooting

**"Could not fetch document"**
- Check the doc is shared (Anyone with the link → Viewer)
- Or ensure the service account email has access

**"Error 400: Invalid field"**
- Run **Fetch Collection Schema** to check exact field slugs
- Update `FIELD_MAP` in `app.py` if slugs differ

**"Error 401: Unauthorized"**
- Regenerate your Webflow API token
- Ensure the token has CMS:write scope

**"Error 429: Too Many Requests"**
- Webflow rate limit: 60 requests/min
- Wait a minute and retry, or reduce batch size
