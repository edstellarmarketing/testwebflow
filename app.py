"""
Edstellar Course Content → Webflow CMS Pusher (v2)
====================================================
A Streamlit app that reads course content from:
  1. Google Docs (via URL or Google Service Account)
  2. Pasted structured text
and pushes it to the Webflow CMS "Courses" collection via the Webflow API v2.

Setup:
  pip install -r requirements.txt
  streamlit run app.py

Required:
  - Webflow Site API Token (generate from Project Settings → API access)
  - Collection ID for "Courses" (found in CMS → Collection Settings)
  - (Optional) Google Service Account JSON for private doc access
"""

import streamlit as st
import requests
import json
import re
import os
from slugify import slugify
from google.oauth2 import service_account
from googleapiclient.discovery import build

# ─── CONFIG ──────────────────────────────────────────────────────────────────

WEBFLOW_API_BASE = "https://api.webflow.com/v2"

# Google API scopes
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/documents.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

# ─── FIELD MAPPING ───────────────────────────────────────────────────────────
# Maps Google Doc section headers → Webflow CMS field slugs
# IMPORTANT: After first run, click "Fetch Collection Schema" in sidebar
# to verify exact slugs and update if needed.

FIELD_MAP = {
    # Basic Info
    "Course Name": "name",
    "Slug": "slug",

    # SEO / Meta
    "Meta Title": "meta-title",
    "Meta Description": "meta-description",
    "Canonical Link": "canonical-link",
    "Primary Keyword": "primary-keyword",
    "Keyword Search Volume": "keyword-search-volume",

    # Core Content
    "Main Heading": "main-heading",
    "Dynamic Course Name": "dynamic-course-name",
    "Course Description": "course-description",
    "Delivery Type": "delivery-type",
    "Duration": "duration",

    # Skill Data
    "Skill Data Header": "skill-data-header",
    "Skill Data Paragraph": "skill-data-paragraph",
    "Skill Data Pointers": "skill-data-pointers",

    # Course Details
    "Courses Card Pointers": "courses-card-pointers",
    "Key Highlights": "key-highlights",
    "Target Audience": "target-audience",
    "Target Audience Points": "target-audience-points",
    "Pre-Requisites": "pre-requisites",
    "Learning Outcomes": "learning-outcomes",
    "Overview": "overview",
    "Course Outlines": "course-outlines-rich-text",

    # Marketing
    "Conclusion": "conclusion",
    "Why Choose Edstellar": "why-choose-edstellar",
    "What Sets Us Apart": "what-sets-us-apart",
    "Drive Team Excellence Heading": "drive-team-excellence-heading",
    "Testimonials Heading and Paragraph": "testimonials-heading-and-paragraph",

    # Internal Links
    "Internal Links for Courses": "internal-links-for-courses",
}

# Fields that should be treated as Rich Text (HTML)
RICH_TEXT_FIELDS = {
    "course-description",
    "skill-data-pointers",
    "courses-card-pointers",
    "key-highlights",
    "target-audience",
    "target-audience-points",
    "pre-requisites",
    "learning-outcomes",
    "overview",
    "course-outlines-rich-text",
    "conclusion",
    "why-choose-edstellar",
    "what-sets-us-apart",
    "drive-team-excellence-heading",
    "testimonials-heading-and-paragraph",
    "internal-links-for-courses",
}


# ─── GOOGLE DOCS FUNCTIONS ───────────────────────────────────────────────────

def extract_doc_id(url: str) -> str | None:
    """Extract Google Doc ID from various URL formats."""
    patterns = [
        r'/document/d/([a-zA-Z0-9_-]+)',
        r'id=([a-zA-Z0-9_-]+)',
        r'^([a-zA-Z0-9_-]{20,})$',  # raw ID
    ]
    for pattern in patterns:
        match = re.search(pattern, url.strip())
        if match:
            return match.group(1)
    return None


def get_google_service(credentials_json: dict) -> tuple:
    """Build Google Docs and Drive service from credentials."""
    creds = service_account.Credentials.from_service_account_info(
        credentials_json, scopes=GOOGLE_SCOPES
    )
    docs_service = build("docs", "v1", credentials=creds)
    drive_service = build("drive", "v3", credentials=creds)
    return docs_service, drive_service


def fetch_doc_as_text_via_drive(drive_service, doc_id: str) -> str:
    """Export a Google Doc as plain text using Drive API."""
    request = drive_service.files().export_media(
        fileId=doc_id, mimeType="text/plain"
    )
    content = request.execute()
    if isinstance(content, bytes):
        return content.decode("utf-8")
    return content


def fetch_doc_structured(docs_service, doc_id: str) -> dict:
    """Fetch Google Doc content with structural information."""
    doc = docs_service.documents().get(documentId=doc_id).execute()
    return doc


def extract_text_from_doc(doc: dict) -> str:
    """
    Extract structured text from Google Docs API response.
    Converts headings to ## markers for our parser.
    """
    content = doc.get("body", {}).get("content", [])
    lines = []

    for element in content:
        if "paragraph" not in element:
            continue

        para = element["paragraph"]
        para_style = para.get("paragraphStyle", {}).get("namedStyleType", "NORMAL_TEXT")

        # Extract text from all runs in this paragraph
        text_parts = []
        for elem in para.get("elements", []):
            text_run = elem.get("textRun", {})
            text = text_run.get("content", "")
            text_parts.append(text)

        full_text = "".join(text_parts).rstrip("\n")
        if not full_text.strip():
            lines.append("")
            continue

        # Convert Google Docs heading styles to markdown
        if para_style == "HEADING_1":
            lines.append(f"# {full_text}")
        elif para_style == "HEADING_2":
            lines.append(f"## {full_text}")
        elif para_style == "HEADING_3":
            lines.append(f"### {full_text}")
        else:
            # Check if it's a list item
            bullet = para.get("bullet")
            if bullet:
                nesting = bullet.get("nestingLevel", 0)
                indent = "  " * nesting
                lines.append(f"{indent}- {full_text}")
            else:
                lines.append(full_text)

    return "\n".join(lines)


def fetch_public_doc_as_text(doc_id: str) -> str | None:
    """
    Fetch a publicly shared Google Doc as plain text.
    Works without any API credentials — doc must be shared as
    'Anyone with the link can view'.
    """
    export_url = f"https://docs.google.com/document/d/{doc_id}/export?format=txt"
    try:
        resp = requests.get(export_url, timeout=15)
        if resp.status_code == 200:
            return resp.text
        return None
    except Exception:
        return None


# ─── CONTENT PARSING ─────────────────────────────────────────────────────────

def parse_structured_content(text: str) -> dict:
    """
    Parse structured content from a Google Doc or pasted text.
    Expected format:
        ## Section Name
        Content goes here...

        ## Another Section
        More content...
    """
    sections = {}
    current_section = None
    current_content = []

    for line in text.split("\n"):
        stripped = line.strip()
        # Match section headers: ## Section Name or ### Section Name
        header_match = re.match(r'^#{2}\s+(.+)$', stripped)
        if header_match:
            # Save previous section
            if current_section:
                sections[current_section] = "\n".join(current_content).strip()
            current_section = header_match.group(1).strip()
            current_content = []
        else:
            if current_section:
                current_content.append(line)

    # Save last section
    if current_section:
        sections[current_section] = "\n".join(current_content).strip()

    return sections


def map_to_webflow_fields(sections: dict) -> dict:
    """Map parsed sections to Webflow field slugs."""
    field_data = {}

    for section_name, content in sections.items():
        # Try exact match first
        if section_name in FIELD_MAP:
            slug = FIELD_MAP[section_name]
            field_data[slug] = content
        else:
            # Try case-insensitive match
            for key, slug in FIELD_MAP.items():
                if key.lower() == section_name.lower():
                    field_data[slug] = content
                    break

    # Auto-generate slug from name if not provided
    if "name" in field_data and "slug" not in field_data:
        field_data["slug"] = slugify(field_data["name"])

    return field_data


def convert_plain_to_html(text: str, field_slug: str) -> str:
    """Convert plain text with bullet points to basic HTML for rich text fields."""
    if field_slug not in RICH_TEXT_FIELDS:
        return text

    lines = text.split("\n")
    html_parts = []
    in_list = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            continue

        # Check if line is a bullet point
        bullet_match = re.match(r'^[-•*]\s+(.+)$', stripped)
        if bullet_match:
            if not in_list:
                html_parts.append("<ul>")
                in_list = True
            html_parts.append(f"  <li>{bullet_match.group(1)}</li>")
        else:
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            # Check if it looks like a sub-heading
            if stripped.startswith("###"):
                html_parts.append(f"<h3>{stripped.lstrip('#').strip()}</h3>")
            elif stripped.startswith("**") and stripped.endswith("**"):
                html_parts.append(f"<h4>{stripped.strip('*').strip()}</h4>")
            else:
                html_parts.append(f"<p>{stripped}</p>")

    if in_list:
        html_parts.append("</ul>")

    return "\n".join(html_parts)


# ─── WEBFLOW API FUNCTIONS ───────────────────────────────────────────────────

def fetch_collection_schema(api_token: str, collection_id: str) -> dict:
    """Fetch the collection schema to verify field slugs."""
    headers = {
        "Authorization": f"Bearer {api_token}",
        "accept": "application/json",
    }
    resp = requests.get(
        f"{WEBFLOW_API_BASE}/collections/{collection_id}",
        headers=headers,
    )
    if resp.status_code == 200:
        return resp.json()
    return {"error": resp.status_code, "message": resp.text}


def create_cms_item(api_token: str, collection_id: str, field_data: dict, is_draft: bool = True) -> dict:
    """Create a new CMS item in Webflow."""
    headers = {
        "Authorization": f"Bearer {api_token}",
        "accept": "application/json",
        "content-type": "application/json",
    }
    payload = {
        "isArchived": False,
        "isDraft": is_draft,
        "fieldData": field_data,
    }
    resp = requests.post(
        f"{WEBFLOW_API_BASE}/collections/{collection_id}/items",
        headers=headers,
        json=payload,
    )
    return {"status": resp.status_code, "response": resp.json() if resp.text else {}}


def publish_cms_item(api_token: str, collection_id: str, item_id: str) -> dict:
    """Publish a CMS item."""
    headers = {
        "Authorization": f"Bearer {api_token}",
        "accept": "application/json",
        "content-type": "application/json",
    }
    payload = {"itemIds": [item_id]}
    resp = requests.post(
        f"{WEBFLOW_API_BASE}/collections/{collection_id}/items/publish",
        headers=headers,
        json=payload,
    )
    return {"status": resp.status_code, "response": resp.json() if resp.text else {}}


# ─── STREAMLIT APP ───────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Edstellar → Webflow CMS Pusher",
    page_icon="🚀",
    layout="wide",
)

st.title("🚀 Edstellar Course → Webflow CMS Pusher")
st.markdown("Push course content from **Google Docs** or structured text to the Webflow CMS **Courses** collection.")

# ─── SIDEBAR: Configuration ──────────────────────────────────────────────────

with st.sidebar:
    st.header("⚙️ Webflow Config")
    api_token = st.text_input(
        "Webflow API Token",
        type="password",
        help="Generate from Project Settings → API access"
    )
    collection_id = st.text_input(
        "Courses Collection ID",
        value="698afc4a706f88cce608a4ac",
        help="Found in CMS → Courses → Collection Settings"
    )

    st.divider()

    st.header("🔑 Google Docs Config")
    google_auth_method = st.radio(
        "Authentication Method",
        ["Public Doc (no auth needed)", "Service Account (private docs)"],
        help="Public: Doc must be shared with 'Anyone with the link'. Service Account: Upload your JSON key."
    )

    google_creds = None
    if google_auth_method == "Service Account (private docs)":
        creds_file = st.file_uploader(
            "Upload Service Account JSON",
            type=["json"],
            help="Download from Google Cloud Console → IAM → Service Accounts → Keys"
        )
        if creds_file:
            google_creds = json.load(creds_file)
            st.success(f"✅ Loaded: {google_creds.get('client_email', 'N/A')}")
            st.caption("Share your Google Docs with this email to grant access.")

    st.divider()

    st.header("🔍 Verify Setup")
    if st.button("Fetch Collection Schema"):
        if api_token and collection_id:
            with st.spinner("Fetching schema..."):
                schema = fetch_collection_schema(api_token, collection_id)
                if "error" not in schema:
                    st.success(f"✅ Connected! Collection: **{schema.get('displayName', 'N/A')}**")
                    fields = schema.get("fields", [])
                    st.markdown(f"**{len(fields)} fields found:**")
                    for f in fields:
                        st.text(f"  {f.get('displayName', '?')} → {f.get('slug', '?')} ({f.get('type', '?')})")
                else:
                    st.error(f"❌ Error {schema['error']}: {schema['message']}")
        else:
            st.warning("Enter API token and Collection ID first.")


# ─── MAIN CONTENT ────────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4 = st.tabs([
    "📄 Google Doc Input",
    "📝 Manual Input",
    "📋 Preview & Push",
    "📖 Template Guide",
])

# Initialize session state
if "parsed_content" not in st.session_state:
    st.session_state.parsed_content = ""
if "content_source" not in st.session_state:
    st.session_state.content_source = ""

# ─── TAB 1: Google Doc Input ─────────────────────────────────────────────────

with tab1:
    st.subheader("📄 Pull Content from Google Docs")

    doc_url = st.text_input(
        "Google Doc URL",
        placeholder="https://docs.google.com/document/d/1abc.../edit",
        help="Paste the full Google Doc URL. For public docs, ensure 'Anyone with the link can view' is enabled."
    )

    col_fetch, col_status = st.columns([1, 2])

    with col_fetch:
        fetch_clicked = st.button("📥 Fetch Document", type="primary", use_container_width=True)

    if fetch_clicked and doc_url:
        doc_id = extract_doc_id(doc_url)
        if not doc_id:
            st.error("❌ Could not extract Doc ID from URL. Please check the URL format.")
        else:
            with st.spinner("Fetching document..."):
                fetched_text = None
                fetch_method = ""

                if google_auth_method == "Service Account (private docs)" and google_creds:
                    # Use Google Docs API with service account
                    try:
                        docs_service, drive_service = get_google_service(google_creds)
                        doc = fetch_doc_structured(docs_service, doc_id)
                        fetched_text = extract_text_from_doc(doc)
                        fetch_method = "Google Docs API (Service Account)"
                    except Exception as e:
                        st.error(f"❌ Google API Error: {e}")
                        st.info("Make sure the doc is shared with the service account email.")
                else:
                    # Try public export
                    fetched_text = fetch_public_doc_as_text(doc_id)
                    fetch_method = "Public Export"

                if fetched_text:
                    st.session_state.parsed_content = fetched_text
                    st.session_state.content_source = f"Google Doc ({fetch_method})"
                    with col_status:
                        st.success(f"✅ Fetched via {fetch_method} ({len(fetched_text)} chars)")
                else:
                    st.error("❌ Could not fetch document. Check sharing settings or credentials.")

    # Show fetched content
    if st.session_state.parsed_content and "Google Doc" in st.session_state.content_source:
        st.markdown(f"**Source:** {st.session_state.content_source}")
        with st.expander("📄 Raw Document Content", expanded=False):
            st.text_area("Fetched content (editable)", st.session_state.parsed_content, height=400, key="gdoc_raw")

        # Parse and show sections
        sections = parse_structured_content(st.session_state.parsed_content)
        if sections:
            st.success(f"✅ Found **{len(sections)} sections** in the document")
            for name, content in sections.items():
                preview = content[:150] + "..." if len(content) > 150 else content
                st.markdown(f"- **{name}**: {preview}")
            st.info("👉 Go to the **Preview & Push** tab to review the mapping and push to Webflow.")
        else:
            st.warning("⚠️ No `## Section Name` headers found. Make sure the Google Doc uses Heading 2 style for section names.")
            st.markdown("""
            **Expected document structure:**
            - Use **Heading 2** (H2) for section names like "Course Name", "Meta Title", etc.
            - Content under each heading is the field value
            - Bullet points become rich text lists
            """)

    # Batch mode
    st.divider()
    st.subheader("📦 Batch Mode: Multiple Docs")
    st.markdown("Paste multiple Google Doc URLs (one per line) to push several courses at once.")

    batch_urls = st.text_area(
        "Google Doc URLs (one per line)",
        height=120,
        placeholder="https://docs.google.com/document/d/1abc.../edit\nhttps://docs.google.com/document/d/2def.../edit",
    )

    if st.button("📥 Fetch All & Push to Webflow", disabled=not api_token):
        if not batch_urls.strip():
            st.warning("Enter at least one URL.")
        else:
            urls = [u.strip() for u in batch_urls.strip().split("\n") if u.strip()]
            progress = st.progress(0)
            results = []

            for i, url in enumerate(urls):
                doc_id = extract_doc_id(url)
                if not doc_id:
                    results.append({"url": url, "status": "❌ Invalid URL"})
                    continue

                # Fetch
                fetched = None
                if google_auth_method == "Service Account (private docs)" and google_creds:
                    try:
                        docs_service, drive_service = get_google_service(google_creds)
                        doc = fetch_doc_structured(docs_service, doc_id)
                        fetched = extract_text_from_doc(doc)
                    except Exception as e:
                        results.append({"url": url, "status": f"❌ Fetch error: {e}"})
                        continue
                else:
                    fetched = fetch_public_doc_as_text(doc_id)

                if not fetched:
                    results.append({"url": url, "status": "❌ Could not fetch"})
                    continue

                # Parse and push
                sections = parse_structured_content(fetched)
                field_data = map_to_webflow_fields(sections)
                for slug in list(field_data.keys()):
                    field_data[slug] = convert_plain_to_html(field_data[slug], slug)

                result = create_cms_item(api_token, collection_id, field_data, is_draft=True)
                course_name = field_data.get("name", "Unknown")

                if result["status"] in [200, 201, 202]:
                    item_id = result["response"].get("id", "")
                    results.append({
                        "url": url,
                        "course": course_name,
                        "status": f"✅ Created (ID: {item_id})",
                    })
                else:
                    results.append({
                        "url": url,
                        "course": course_name,
                        "status": f"❌ Failed ({result['status']})",
                    })

                progress.progress((i + 1) / len(urls))

            st.subheader("Batch Results")
            for r in results:
                st.markdown(f"- **{r.get('course', r['url'])}**: {r['status']}")


# ─── TAB 2: Manual Input ─────────────────────────────────────────────────────

with tab2:
    st.subheader("📝 Paste Content Manually")
    st.markdown("Use `## Section Name` format. See the **Template Guide** tab for the full template.")

    sample_content = """## Course Name
Retrieval Augmented Generation (RAG) Training

## Meta Title
Retrieval Augmented Generation (RAG) Training | Corporate Training | Edstellar

## Meta Description
Master RAG techniques with Edstellar's corporate training. Learn to build AI systems that combine retrieval and generation for accurate, context-aware responses.

## Canonical Link
https://www.edstellar.com/course/retrieval-augmented-generation-rag-training

## Primary Keyword
RAG Training

## Keyword Search Volume
1200

## Main Heading
Retrieval Augmented Generation (RAG) Training

## Dynamic Course Name
Retrieval Augmented Generation (RAG)

## Delivery Type
Instructor-Led

## Duration
16 Hours

## Course Description
Retrieval Augmented Generation (RAG) is a powerful approach that combines information retrieval with text generation to produce more accurate and contextually relevant AI outputs. This corporate training program equips teams with hands-on skills to design, build, and optimize RAG pipelines.

## Skill Data Header
Skills Covered in RAG Training

## Skill Data Paragraph
Participants will learn vector databases, embedding models, prompt engineering for retrieval, and end-to-end RAG pipeline architecture.

## Skill Data Pointers
- Vector Database Management
- Embedding Model Selection
- Prompt Engineering for Retrieval
- RAG Pipeline Architecture
- Context Window Optimization
- Response Quality Evaluation

## Key Highlights
- Hands-on labs with real-world datasets
- Build a complete RAG pipeline from scratch
- Learn best practices for production deployment
- Expert instructors with industry experience

## Target Audience
AI/ML Engineers, Data Scientists, Software Developers, Technical Leads, and CTOs looking to implement RAG-based solutions in their organizations.

## Target Audience Points
- AI/ML Engineers building intelligent applications
- Data Scientists working with large language models
- Software Developers integrating AI into products
- Technical Leads overseeing AI initiatives

## Pre-Requisites
- Basic Python programming
- Familiarity with machine learning concepts
- Understanding of NLP fundamentals

## Learning Outcomes
- Design and implement RAG architectures
- Select and configure appropriate vector databases
- Optimize retrieval quality and response accuracy
- Deploy RAG systems in production environments
- Evaluate and monitor RAG system performance

## Overview
This comprehensive training covers the complete RAG ecosystem, from foundational concepts to advanced optimization techniques. Participants will work through hands-on exercises building real RAG pipelines.

## Course Outlines
### Module 1: Introduction to RAG
- What is Retrieval Augmented Generation?
- RAG vs Fine-tuning vs Prompt Engineering
- Architecture overview

### Module 2: Vector Databases
- Introduction to vector databases
- Embedding models and strategies
- Indexing and retrieval optimization

### Module 3: Building RAG Pipelines
- End-to-end pipeline design
- Document processing and chunking
- Query processing and response generation

### Module 4: Advanced RAG Techniques
- Multi-hop retrieval
- Hybrid search strategies
- Evaluation and monitoring

## Conclusion
RAG training empowers teams to build AI systems that deliver accurate, context-aware responses by combining the best of retrieval and generation approaches.

## Why Choose Edstellar
Edstellar brings 14+ years of corporate training expertise with 5,000+ certified trainers across 100+ locations worldwide. Our customized training programs are trusted by Fortune 500 companies.

## What Sets Us Apart
- Customized curriculum tailored to your team's tech stack
- Hands-on labs with real-world datasets
- Post-training support and certification
- Flexible delivery: virtual, onsite, or hybrid

## Drive Team Excellence Heading
Drive Team Excellence with RAG Training

## Testimonials Heading and Paragraph
What Our Clients Say About Edstellar's AI Training Programs

## Internal Links for Courses
- <a href="/course/prompt-engineering-training">Prompt Engineering Training</a>
- <a href="/course/langchain-training">LangChain Training</a>
- <a href="/course/vector-database-training">Vector Database Training</a>
"""

    manual_content = st.text_area(
        "Course Content (structured format)",
        value=sample_content,
        height=500,
    )

    if st.button("✅ Use This Content", use_container_width=True):
        st.session_state.parsed_content = manual_content
        st.session_state.content_source = "Manual Input"
        st.success("Content loaded! Go to **Preview & Push** tab.")


# ─── TAB 3: Preview & Push ───────────────────────────────────────────────────

with tab3:
    st.subheader("📋 Field Mapping Preview & Push")

    content = st.session_state.parsed_content
    source = st.session_state.content_source

    if not content:
        st.info("No content loaded yet. Use the **Google Doc Input** or **Manual Input** tab first.")
    else:
        st.markdown(f"**Content source:** {source}")
        sections = parse_structured_content(content)
        field_data = map_to_webflow_fields(sections)

        # Convert rich text fields to HTML
        for slug in list(field_data.keys()):
            field_data[slug] = convert_plain_to_html(field_data[slug], slug)

        # Show mapping in two columns
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**✅ Mapped Fields**")
            for slug, value in field_data.items():
                preview = value[:120] + "..." if len(value) > 120 else value
                is_html = slug in RICH_TEXT_FIELDS
                tag = " 🔤HTML" if is_html else ""
                st.markdown(f"**`{slug}`**{tag}: {preview}")

        with col2:
            st.markdown("**⚠️ Unmapped Sections**")
            mapped_sections = set()
            for section_name in sections:
                for key in FIELD_MAP:
                    if key.lower() == section_name.lower():
                        mapped_sections.add(section_name)
                        break

            unmapped = set(sections.keys()) - mapped_sections
            if unmapped:
                for s in unmapped:
                    st.warning(f"Section **{s}** not mapped to any Webflow field")
            else:
                st.success("All sections mapped successfully!")

            st.markdown("---")
            st.markdown("**📊 Summary**")
            st.metric("Total Sections", len(sections))
            st.metric("Mapped Fields", len(field_data))
            st.metric("Unmapped", len(unmapped) if unmapped else 0)

        # JSON preview
        with st.expander("📦 Raw API Payload (JSON)"):
            payload = {
                "isArchived": False,
                "isDraft": True,
                "fieldData": field_data,
            }
            st.json(payload)

        # Push controls
        st.divider()
        col_a, col_b, col_c = st.columns([1, 1, 1])

        with col_a:
            publish_option = st.radio(
                "After creation:",
                ["Create as Draft", "Create and Publish"],
            )

        with col_b:
            course_name = field_data.get("name", "Unknown Course")
            st.markdown(f"**Course:** {course_name}")
            st.markdown(f"**Slug:** `{field_data.get('slug', 'N/A')}`")

        with col_c:
            st.markdown("")
            push_clicked = st.button(
                "🚀 Push to Webflow CMS",
                type="primary",
                use_container_width=True,
            )

        if push_clicked:
            if not api_token:
                st.error("❌ Enter your Webflow API Token in the sidebar!")
            elif not collection_id:
                st.error("❌ Enter the Collection ID in the sidebar!")
            else:
                is_draft = publish_option == "Create as Draft"

                with st.spinner("Creating CMS item..."):
                    result = create_cms_item(api_token, collection_id, field_data, is_draft=is_draft)

                if result["status"] in [200, 201, 202]:
                    st.success("✅ Course item created successfully!")
                    item_id = result["response"].get("id", "")
                    st.info(f"Item ID: `{item_id}`")

                    if publish_option == "Create and Publish" and item_id:
                        with st.spinner("Publishing..."):
                            pub_result = publish_cms_item(api_token, collection_id, item_id)
                        if pub_result["status"] in [200, 201, 202]:
                            st.success("✅ Published to live site!")
                        else:
                            st.warning(f"⚠️ Created but publish failed: {pub_result['response']}")

                    with st.expander("API Response"):
                        st.json(result["response"])
                else:
                    st.error(f"❌ Failed (HTTP {result['status']})")
                    st.json(result["response"])


# ─── TAB 4: Template Guide ───────────────────────────────────────────────────

with tab4:
    st.subheader("📖 Google Doc Template for Writers")

    st.markdown("""
    ### How to Use
    
    1. **Create a new Google Doc** and copy the template below
    2. Use **Heading 2** style (or type `##`) for each section name
    3. Fill in the content under each heading
    4. Share the doc:
       - **For public access**: Share → Anyone with the link → Viewer
       - **For service account**: Share with the service account email shown in sidebar
    5. Paste the doc URL in the **Google Doc Input** tab and click **Fetch Document**
    
    ### Formatting Rules
    - **Heading 2** (`##`) = Section separator (maps to a Webflow field)
    - **Heading 3** (`###`) = Sub-heading within a section (becomes `<h3>` in rich text)
    - **Bullet points** (`-` or `•`) = Becomes `<ul><li>` in rich text fields
    - **Bold text** (`**text**`) = Becomes `<h4>` in rich text fields
    - Plain text = Becomes `<p>` in rich text fields
    
    ### Important Notes
    - Section names must match **exactly** (case-insensitive)
    - Leave sections empty or remove them if not applicable
    - The **Slug** is auto-generated from Course Name if omitted
    - **Images** must be added manually in Webflow (API limitation)
    - **Reference fields** (Category, Subcategory, Level, Type) must be set in Webflow
    """)

    template = """## Course Name
[Full course name, e.g., "Retrieval Augmented Generation (RAG) Training"]

## Meta Title
[SEO title, min 70 chars, e.g., "Course Name | Corporate Training | Edstellar"]

## Meta Description
[SEO description, min 155 chars]

## Canonical Link
[Full URL, e.g., https://www.edstellar.com/course/your-course-slug]

## Primary Keyword
[Main SEO keyword]

## Keyword Search Volume
[Monthly search volume number]

## Main Heading
[H1 heading for the page]

## Dynamic Course Name
[H2 and Para with Corporate Word — Course Name without "Training" and "Course" word]

## Delivery Type
[e.g., Instructor-Led, Self-Paced, Blended]

## Duration
[e.g., 16 Hours, 3 Days]

## Course Description
[2-3 paragraph overview of the course]

## Skill Data Header
[Section heading, e.g., "Skills Covered in [Course] Training"]

## Skill Data Paragraph
[Brief paragraph about skills covered]

## Skill Data Pointers
- Skill 1
- Skill 2
- Skill 3
- Skill 4
- Skill 5
- Skill 6

## Courses Card Pointers
- Key point for card display 1
- Key point for card display 2
- Key point for card display 3

## Key Highlights
- Highlight 1
- Highlight 2
- Highlight 3
- Highlight 4

## Target Audience
[Paragraph describing who should attend]

## Target Audience Points
- Audience segment 1
- Audience segment 2
- Audience segment 3
- Audience segment 4

## Pre-Requisites
- Prerequisite 1
- Prerequisite 2
- Prerequisite 3

## Learning Outcomes
- Outcome 1
- Outcome 2
- Outcome 3
- Outcome 4
- Outcome 5

## Overview
[Detailed course overview paragraph]

## Course Outlines
### Module 1: [Module Title]
- Topic 1
- Topic 2
- Topic 3

### Module 2: [Module Title]
- Topic 1
- Topic 2
- Topic 3

### Module 3: [Module Title]
- Topic 1
- Topic 2
- Topic 3

## Conclusion
[Closing paragraph about the course value]

## Why Choose Edstellar
[Standard Edstellar value proposition]

## What Sets Us Apart
- Differentiator 1
- Differentiator 2
- Differentiator 3
- Differentiator 4

## Drive Team Excellence Heading
[e.g., "Drive Team Excellence with [Course Name] Training"]

## Testimonials Heading and Paragraph
[e.g., "What Our Clients Say About Edstellar's [Category] Training Programs"]

## Internal Links for Courses
- <a href="/course/related-course-1-slug">Related Course 1 Name</a>
- <a href="/course/related-course-2-slug">Related Course 2 Name</a>
- <a href="/course/related-course-3-slug">Related Course 3 Name</a>
"""

    st.code(template, language="markdown")

    # Create downloadable template as a text file
    st.download_button(
        "📥 Download Template (.txt)",
        data=template,
        file_name="edstellar_course_template.txt",
        mime="text/plain",
    )
