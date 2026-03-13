"""
Edstellar Course Content → Webflow CMS Pusher
==============================================
A Streamlit app that reads course content from a structured Google Doc (or pasted text)
and pushes it to the Webflow CMS "Courses" collection via the Webflow API v2.

Setup:
  pip install streamlit requests python-slugify
  streamlit run app.py

Required:
  - Webflow Site API Token (generate from Project Settings → API access)
  - Collection ID for "Courses" (found in CMS → Collection Settings)
"""

import streamlit as st
import requests
import json
import re
from slugify import slugify

# ─── CONFIG ──────────────────────────────────────────────────────────────────

WEBFLOW_API_BASE = "https://api.webflow.com/v2"

# ─── FIELD MAPPING ───────────────────────────────────────────────────────────
# Maps Google Doc section headers → Webflow CMS field slugs
# Webflow converts field names to slug format (lowercase, hyphens)
# You can verify exact slugs by calling GET /collections/{id} with your API token

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


# ─── HELPER FUNCTIONS ────────────────────────────────────────────────────────

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
        header_match = re.match(r'^#{2,3}\s+(.+)$', stripped)
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
st.markdown("Push course content to the Webflow CMS **Courses** collection with one click.")

# Sidebar: Configuration
with st.sidebar:
    st.header("⚙️ Configuration")
    api_token = st.text_input("Webflow API Token", type="password", help="Generate from Project Settings → API access")
    collection_id = st.text_input(
        "Courses Collection ID",
        value="698afc4a706f88cce608a4ac",
        help="Found in CMS → Courses → Collection Settings"
    )

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

    st.divider()
    st.markdown("""
    **How it works:**
    1. Paste your structured content
    2. Preview the field mapping
    3. Click **Push to Webflow**
    4. Item is created as draft (or published)
    """)

# Main content area
tab1, tab2, tab3 = st.tabs(["📝 Content Input", "📋 Field Mapping Preview", "📖 Template Guide"])

with tab1:
    st.subheader("Paste your course content")
    st.markdown("Use the `## Section Name` format to separate fields. See the **Template Guide** tab for the full template.")

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

    content = st.text_area(
        "Course Content (structured format)",
        value=sample_content,
        height=500,
        help="Use ## Section Name to mark each field"
    )

with tab2:
    st.subheader("Field Mapping Preview")

    if content.strip():
        sections = parse_structured_content(content)
        field_data = map_to_webflow_fields(sections)

        # Convert rich text fields to HTML
        for slug in list(field_data.keys()):
            field_data[slug] = convert_plain_to_html(field_data[slug], slug)

        # Show mapping
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Mapped Fields** ✅")
            for slug, value in field_data.items():
                preview = value[:100] + "..." if len(value) > 100 else value
                st.markdown(f"**`{slug}`**: {preview}")

        with col2:
            st.markdown("**Unmapped Sections** ⚠️")
            mapped_sections = set()
            for section_name in sections:
                found = False
                for key in FIELD_MAP:
                    if key.lower() == section_name.lower():
                        found = True
                        break
                if found:
                    mapped_sections.add(section_name)

            unmapped = set(sections.keys()) - mapped_sections
            if unmapped:
                for s in unmapped:
                    st.warning(f"Section **{s}** not mapped to any Webflow field")
            else:
                st.success("All sections mapped successfully!")

        st.divider()

        # JSON preview
        with st.expander("📦 Raw API Payload (JSON)"):
            payload = {
                "isArchived": False,
                "isDraft": True,
                "fieldData": field_data,
            }
            st.json(payload)

        # Push button
        st.divider()
        col_a, col_b = st.columns(2)

        with col_a:
            publish_option = st.radio(
                "After creation:",
                ["Create as Draft", "Create and Publish"],
                help="Draft items need manual publishing in Webflow"
            )

        with col_b:
            st.markdown("")
            st.markdown("")
            if st.button("🚀 Push to Webflow CMS", type="primary", use_container_width=True):
                if not api_token:
                    st.error("❌ Enter your Webflow API Token in the sidebar first!")
                elif not collection_id:
                    st.error("❌ Enter the Collection ID in the sidebar first!")
                else:
                    is_draft = publish_option == "Create as Draft"

                    with st.spinner("Creating CMS item..."):
                        result = create_cms_item(api_token, collection_id, field_data, is_draft=is_draft)

                    if result["status"] in [200, 201, 202]:
                        st.success("✅ Course item created successfully!")
                        item_id = result["response"].get("id", "")
                        st.info(f"Item ID: `{item_id}`")

                        # Publish if requested
                        if publish_option == "Create and Publish" and item_id:
                            with st.spinner("Publishing item..."):
                                pub_result = publish_cms_item(api_token, collection_id, item_id)
                            if pub_result["status"] in [200, 201, 202]:
                                st.success("✅ Item published to live site!")
                            else:
                                st.warning(f"⚠️ Item created but publish failed: {pub_result['response']}")

                        with st.expander("API Response"):
                            st.json(result["response"])
                    else:
                        st.error(f"❌ Failed (HTTP {result['status']})")
                        st.json(result["response"])

    else:
        st.info("Paste content in the **Content Input** tab to see the field mapping.")

with tab3:
    st.subheader("📖 Google Doc Template for Writers")
    st.markdown("""
    Share this template with your content writers. They should fill in each section, 
    then paste the content into the **Content Input** tab (or you can automate reading from Google Docs).
    
    ### Template Instructions
    - Each section starts with `## Section Name` (exactly as shown)
    - Use `-` or `•` for bullet points within sections
    - Rich text fields (Course Description, Key Highlights, etc.) will be auto-converted to HTML
    - The **Slug** is auto-generated from the Course Name if not provided
    - Leave sections empty if not applicable — they'll be skipped
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

    if st.button("📋 Copy Template to Clipboard"):
        st.code(template, language="markdown")
        st.info("Select all the text above and copy it (Ctrl+A, Ctrl+C)")
