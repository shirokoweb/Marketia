import streamlit as st
import os
import time
import datetime
from google import genai
from dotenv import load_dotenv

# Set page config for a clean, professional look
st.set_page_config(
    page_title="Marketia Research",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Load environment variables
load_dotenv()

# --- CSS for Professional UI ---
st.markdown("""
<style>
    .main {
        background-color: #f9f9f9;
        font-family: "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    .stButton>button {
        width: 100%;
        border-radius: 4px;
        font-weight: 600;
    }
    .stTextArea>div>div>textarea {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
    }
    h1, h2, h3 {
        color: #333333;
    }
</style>
""", unsafe_allow_html=True)

# --- Sidebar: Configuration ---
with st.sidebar:
    st.header("Settings")
    
    # API Key Handling
    env_api_key = os.getenv("GOOGLE_API_KEY")
    api_key_input = st.text_input(
        "Google API Key", 
        value=env_api_key if env_api_key else "", 
        type="password",
        help="Your Google AI Studio API Key"
    )
    
    if not api_key_input:
        st.warning("Please enter your API Key to proceed.")
        st.stop()
        
    client = genai.Client(api_key=api_key_input)
    
    st.divider()
    model_name = st.selectbox(
        "Research Agent",
        ["deep-research-pro-preview-12-2025"],
        index=0
    )
    
    st.divider()
    # Obsidian Vault Path
    env_vault_path = os.getenv("OBSIDIAN_VAULT_PATH", "")
    output_dir = st.text_input(
        "Output Directory",
        value=env_vault_path,
        placeholder="/Users/you/Obsidian/Research/",
        help="Path to save reports. Leave empty to save in current directory."
    )
    
    # Validate and normalize path
    if output_dir:
        output_dir = os.path.expanduser(output_dir.strip())
        if not os.path.isdir(output_dir):
            st.warning(f"Directory not found: {output_dir}")
            output_dir = ""
        else:
            st.caption(f"📁 Saving to: `{output_dir}`")
    
    st.info("Status: Ready")

# --- Helper Functions ---
import re
import yaml

def slugify(text):
    """Convert text to URL-friendly slug."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)  # Remove special chars
    text = re.sub(r'[\s_]+', '-', text)   # Replace spaces/underscores with hyphens
    text = re.sub(r'-+', '-', text)       # Remove duplicate hyphens
    return text[:60]  # Limit length

def generate_frontmatter(title, report_type="research", tags=None, prompt_summary="", 
                         tokens_used=0, estimated_cost=0.0, follow_up_count=0):
    """Generate YAML frontmatter for Obsidian compatibility."""
    now = datetime.datetime.now()
    frontmatter = {
        "title": title,
        "type": report_type,
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "tags": tags or [],
        "prompt_summary": prompt_summary[:200] if prompt_summary else "",
        "tokens_used": tokens_used,
        "estimated_cost": f"${estimated_cost:.4f}",
        "follow_up_count": follow_up_count,
        "last_updated": now.strftime("%Y-%m-%d %H:%M:%S"),
    }
    yaml_str = yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True, sort_keys=False)
    return f"---\n{yaml_str}---\n\n"

def parse_frontmatter(content):
    """Extract frontmatter dict and body from markdown content."""
    if not content.startswith("---"):
        return {}, content
    
    try:
        # Find the closing ---
        end_idx = content.find("---", 3)
        if end_idx == -1:
            return {}, content
        
        yaml_str = content[3:end_idx].strip()
        body = content[end_idx + 3:].strip()
        frontmatter = yaml.safe_load(yaml_str) or {}
        return frontmatter, body
    except yaml.YAMLError:
        return {}, content

def update_frontmatter(content, updates):
    """Update specific fields in existing frontmatter."""
    frontmatter, body = parse_frontmatter(content)
    frontmatter.update(updates)
    frontmatter["last_updated"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    yaml_str = yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True, sort_keys=False)
    return f"---\n{yaml_str}---\n\n{body}"

def save_research_report(content, title, tags=None, prompt_summary="", tokens_used=0, estimated_cost=0.0, output_dir=""):
    """Save a new research report with frontmatter and slug-based filename."""
    slug = slugify(title) if title else "research"
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    base_name = f"{slug}_{date_str}.md"
    
    # Use output_dir if provided, otherwise current directory
    if output_dir:
        filename = os.path.join(output_dir, base_name)
    else:
        filename = base_name
    
    # Handle filename collisions
    counter = 2
    original_filename = filename
    while os.path.exists(filename):
        collision_name = base_name.replace(".md", f"-{counter}.md")
        filename = os.path.join(output_dir, collision_name) if output_dir else collision_name
        counter += 1
    
    frontmatter = generate_frontmatter(
        title=title,
        report_type="research",
        tags=tags,
        prompt_summary=prompt_summary,
        tokens_used=tokens_used,
        estimated_cost=estimated_cost,
    )
    
    full_content = frontmatter + f"# {title}\n\n## Research Report\n\n{content}"
    
    with open(filename, "w") as f:
        f.write(full_content)
    
    return filename

def generate_title_and_tags(prompt, report_content, api_client):
    """
    Use Gemini Flash to generate a descriptive title and tags from the research.
    Returns: (title, tags_list) or falls back to (prompt_excerpt, []) on failure.
    """
    try:
        extraction_prompt = f"""Based on this research prompt and report, generate:
1. A concise, descriptive title (5-8 words max, no quotes)
2. 3-5 relevant tags (lowercase, single words or hyphenated)

PROMPT: {prompt[:500]}

REPORT EXCERPT: {report_content[:1500]}

Respond in this exact format:
TITLE: <your title here>
TAGS: tag1, tag2, tag3, tag4"""

        response = api_client.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents=extraction_prompt
        )
        
        result_text = response.text.strip()
        
        # Parse response
        title = prompt[:60]  # fallback
        tags = []
        
        for line in result_text.split("\n"):
            if line.upper().startswith("TITLE:"):
                title = line.split(":", 1)[1].strip()[:80]
            elif line.upper().startswith("TAGS:"):
                tags_raw = line.split(":", 1)[1].strip()
                tags = [t.strip().lower().replace(" ", "-") for t in tags_raw.split(",")][:5]
        
        return title, tags
        
    except Exception as e:
        # Fallback: use first 60 chars of prompt as title
        return prompt[:60].strip(), []

def append_followup_to_report(filepath, followup_content, question, tokens_used=0, estimated_cost=0.0):
    """Append a follow-up section to an existing report file."""
    with open(filepath, "r") as f:
        existing_content = f.read()
    
    # Parse existing frontmatter
    frontmatter, body = parse_frontmatter(existing_content)
    
    # Update follow-up count
    follow_up_count = frontmatter.get("follow_up_count", 0) + 1
    frontmatter["follow_up_count"] = follow_up_count
    frontmatter["last_updated"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Create new follow-up section
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    followup_section = f"\n\n---\n\n## Follow-up {follow_up_count}: {question[:50]}{'...' if len(question) > 50 else ''}\n"
    followup_section += f"*Asked: {timestamp} | Tokens: {tokens_used:,} | Cost: ${estimated_cost:.4f}*\n\n"
    followup_section += followup_content
    
    # Rebuild file
    yaml_str = yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True, sort_keys=False)
    new_content = f"---\n{yaml_str}---\n\n{body}{followup_section}"
    
    with open(filepath, "w") as f:
        f.write(new_content)
    
    return follow_up_count

def calculate_cost(prompt_tokens, output_tokens):
    """Calculate estimated cost based on token usage."""
    # Pricing for Gemini Deep Research Agent
    # Input: $1.00 / 1M (<= 200k), $2.00 / 1M (> 200k)
    # Output: $6.00 / 1M (<= 200k), $9.00 / 1M (> 200k)
    
    if prompt_tokens <= 200_000:
        input_rate = 1.00
        output_rate = 6.00
    else:
        input_rate = 2.00
        output_rate = 9.00
        
    input_cost = (prompt_tokens / 1_000_000) * input_rate
    output_cost = (output_tokens / 1_000_000) * output_rate
    
    return input_cost + output_cost

def get_research_reports(search_dir=""):
    """Get only research reports (not follow-up-only files), sorted by modification time."""
    reports = []
    target_dir = search_dir if search_dir else "."
    
    try:
        files = os.listdir(target_dir)
    except OSError:
        return reports
    
    for f in files:
        if f.endswith(".md") and not f.startswith("README"):
            filepath = os.path.join(target_dir, f) if search_dir else f
            try:
                with open(filepath, "r") as file:
                    content = file.read()
                frontmatter, _ = parse_frontmatter(content)
                # Include files that are research type or have no frontmatter (legacy)
                if frontmatter.get("type") == "research" or not frontmatter:
                    title = frontmatter.get("title", f)
                    follow_ups = frontmatter.get("follow_up_count", 0)
                    reports.append({
                        "filename": filepath,  # Full path for saving follow-ups
                        "basename": f,
                        "title": title,
                        "follow_up_count": follow_ups,
                        "display": f"{title} ({follow_ups} follow-ups)" if follow_ups else title
                    })
            except Exception:
                # If we can't read the file, include it anyway
                reports.append({
                    "filename": filepath,
                    "basename": f,
                    "title": f,
                    "follow_up_count": 0,
                    "display": f
                })
    
    # Sort by modification time, newest first
    reports.sort(key=lambda x: os.path.getmtime(x["filename"]), reverse=True)
    return reports

# --- Main Interface ---
st.title("📊 Marketia Research Hub")

tab1, tab2 = st.tabs(["🚀 New Research", "🔍 Follow-up Analysis"])

# --- TAB 1: NEW RESEARCH ---
with tab1:
    st.subheader("Launch New Deep Research Task")
    
    # Optional title input
    report_title = st.text_input(
        "Report Title (optional)",
        placeholder="Leave empty for AI-generated title, or enter your own...",
        help="A descriptive title for your research. If left empty, one will be generated from the prompt."
    )
    
    col1, col2 = st.columns([3, 1])
    with col1:
        research_prompt = st.text_area(
            "Research Objectives & Prompt",
            height=250,
            placeholder="Describe your market research goal, key questions, and desired output format..."
        )
    with col2:
        uploaded_file = st.file_uploader("Or upload prompt file (.txt)", type=["txt"])
        if uploaded_file is not None:
            research_prompt = uploaded_file.read().decode("utf-8")
            st.success(f"Loaded: {uploaded_file.name}")

    if st.button("Start Deep Research", type="primary"):
        if not research_prompt:
            st.error("Please enter a prompt.")
        else:
            with st.status("Initializing Research Agent...", expanded=True) as status:
                try:
                    # Start Interaction
                    status.write("Submitting task to Google GenAI...")
                    interaction = client.interactions.create(
                        agent=model_name,
                        input=research_prompt,
                        background=True
                    )
                    status.write(f"Task ID: `{interaction.id}`")
                    status.write("Agent is researching... (Cost & Usage will appear upon completion)")
                    
                    # Polling Loop
                    progress_bar = st.progress(0)
                    start_time = time.time()
                    
                    while True:
                        interaction = client.interactions.get(interaction.id)
                        batch_status = interaction.status
                        
                        if batch_status == 'completed':
                            progress_bar.progress(100)
                            status.update(label="Research Completed!", state="complete", expanded=False)
                            break
                        elif batch_status == 'failed':
                            status.update(label="Research Failed", state="error")
                            st.error(f"Error: {interaction.error}")
                            st.stop()
                        
                        # Fake progress update for UX since we don't get % from API
                        elapsed = time.time() - start_time
                        pseudo_progress = min(90, int(elapsed / 6)) # slowly fill up
                        progress_bar.progress(pseudo_progress)
                        
                        time.sleep(5)
                    
                    # Display Results
                    full_report = ""
                    if interaction.outputs:
                        st.divider()
                        
                        # DEBUG: Inspect interaction object
                        debug_info = []
                        debug_info.append(f"Has 'usage' attr: {hasattr(interaction, 'usage')}")
                        if hasattr(interaction, 'usage') and interaction.usage:
                            debug_info.append(f"usage type: {type(interaction.usage)}")
                            debug_info.append(f"usage value: {interaction.usage}")
                            # Try to get dict representation
                            if hasattr(interaction.usage, 'to_dict'):
                                debug_info.append(f"usage.to_dict(): {interaction.usage.to_dict()}")
                            elif hasattr(interaction.usage, '__dict__'):
                                debug_info.append(f"usage.__dict__: {interaction.usage.__dict__}")
                            # Check for common token fields
                            for attr in ['prompt_token_count', 'candidates_token_count', 'total_token_count', 
                                         'input_tokens', 'output_tokens', 'total_tokens']:
                                if hasattr(interaction.usage, attr):
                                    debug_info.append(f"usage.{attr}: {getattr(interaction.usage, attr)}")
                        else:
                            debug_info.append("usage is None or missing")
                        
                        # Save to file
                        with open("debug_interaction.txt", "w") as df:
                            df.write("\n".join(debug_info))
                        
                        with st.expander("🔍 Debug: Interaction Object (click to expand)"):
                            for line in debug_info:
                                st.text(line)
                        
                        # Calculate and display metrics
                        if hasattr(interaction, 'usage') and interaction.usage:
                            usage = interaction.usage
                            p_tokens = usage.total_input_tokens or 0
                            o_tokens = usage.total_output_tokens or 0
                            r_tokens = usage.total_reasoning_tokens or 0
                            total_cost = calculate_cost(p_tokens, o_tokens + r_tokens)
                            
                            col_m1, col_m2, col_m3, col_m4 = st.columns(4)
                            col_m1.metric("Input Tokens", f"{p_tokens:,}")
                            col_m2.metric("Output Tokens", f"{o_tokens:,}")
                            col_m3.metric("Reasoning Tokens", f"{r_tokens:,}")
                            col_m4.metric("Estimated Cost", f"${total_cost:.4f}")
                        
                        st.success("Research Report Generated")
                        
                        for output in interaction.outputs:
                            full_report += output.text
                        
                        st.markdown(full_report)
                        
                        # Generate title and tags
                        if report_title.strip():
                            # User provided title
                            final_title = report_title.strip()
                            final_tags = []
                        else:
                            # AI-generated title and tags
                            with st.spinner("Generating title and tags..."):
                                final_title, final_tags = generate_title_and_tags(
                                    prompt=research_prompt,
                                    report_content=full_report,
                                    api_client=client
                                )
                        
                        # Calculate metrics for saving
                        p_tokens = 0
                        total_cost = 0.0
                        if hasattr(interaction, 'usage') and interaction.usage:
                            usage = interaction.usage
                            p_tokens = (usage.total_input_tokens or 0) + (usage.total_output_tokens or 0) + (usage.total_reasoning_tokens or 0)
                            total_cost = calculate_cost(usage.total_input_tokens or 0, (usage.total_output_tokens or 0) + (usage.total_reasoning_tokens or 0))
                        
                        # Save with frontmatter
                        saved_filename = save_research_report(
                            content=full_report,
                            title=final_title,
                            tags=final_tags,
                            prompt_summary=research_prompt[:200],
                            tokens_used=p_tokens,
                            estimated_cost=total_cost,
                            output_dir=output_dir
                        )
                        
                        st.success(f"📁 Saved to `{saved_filename}`")
                            
                        # Read back the full file for download
                        with open(saved_filename, "r") as f:
                            download_content = f.read()
                            
                        st.download_button(
                            label="Download Report as MD",
                            data=download_content,
                            file_name=saved_filename,
                            mime="text/markdown"
                        )
                        
                    else:
                        st.warning("Task completed but returned no text output.")

                except Exception as e:
                    st.error(f"An error occurred: {str(e)}")

# --- TAB 2: FOLLOW-UP ---
with tab2:
    st.subheader("Continue Research (Follow-up)")
    
    available_reports = get_research_reports(search_dir=output_dir)
    
    if not available_reports:
        st.info("No existing reports found. Run a new research task first.")
    else:
        # Create display options for selectbox
        report_options = {r["display"]: r for r in available_reports}
        selected_display = st.selectbox(
            "Select Parent Report",
            options=list(report_options.keys()),
            help="Follow-up will be appended to this report"
        )
        selected_report = report_options[selected_display]
        
        # Show report info
        with st.expander("📄 View Parent Report"):
            with open(selected_report["filename"], "r") as f:
                context_content = f.read()
            frontmatter, body = parse_frontmatter(context_content)
            if frontmatter:
                st.caption(f"**Title:** {frontmatter.get('title', 'N/A')} | **Follow-ups:** {frontmatter.get('follow_up_count', 0)} | **Last updated:** {frontmatter.get('last_updated', 'N/A')}")
            st.text(body[:800] + "..." if len(body) > 800 else body)

        followup_query = st.text_input(
            "Follow-up Question", 
            placeholder="e.g., 'Compare the pricing models' or 'Deep dive on competitor X'"
        )
        
        if st.button("Run Follow-up", type="primary"):
            if not followup_query:
                st.error("Please enter a question.")
            else:
                with st.status("Running follow-up research...", expanded=True) as status:
                    try:
                        # Load full context
                        with open(selected_report["filename"], "r") as f:
                            context_content = f.read()
                        
                        # Construct Prompt
                        final_prompt = (
                            f"CONTEXT:\n"
                            f"The following is a market research report generated previously:\n"
                            f"===\n{context_content}\n===\n\n"
                            f"TASK:\n"
                            f"Based on the report above (and performing additional research if necessary), "
                            f"please answer this follow-up request:\n"
                            f"{followup_query}"
                        )
                        
                        status.write("Submitting follow-up to research agent...")
                        interaction = client.interactions.create(
                            agent=model_name,
                            input=final_prompt,
                            background=True
                        )
                        status.write(f"Task ID: `{interaction.id}`")
                        
                        # Polling logic
                        while True:
                            interaction = client.interactions.get(interaction.id)
                            if interaction.status in ['completed', 'failed']:
                                break
                            time.sleep(3)
                        
                        if interaction.status == 'completed':
                            if interaction.outputs:
                                followup_out = "".join([o.text for o in interaction.outputs])
                                
                                # Metrics for follow-up
                                p_tokens = 0
                                total_cost = 0.0
                                if hasattr(interaction, 'usage') and interaction.usage:
                                    usage = interaction.usage
                                    p_in = usage.total_input_tokens or 0
                                    p_out = usage.total_output_tokens or 0
                                    p_reason = usage.total_reasoning_tokens or 0
                                    p_tokens = p_in + p_out + p_reason
                                    total_cost = calculate_cost(p_in, p_out + p_reason)
                                    
                                    m_c1, m_c2, m_c3, m_c4 = st.columns(4)
                                    m_c1.metric("Input", f"{p_in:,}")
                                    m_c2.metric("Output", f"{p_out:,}")
                                    m_c3.metric("Reasoning", f"{p_reason:,}")
                                    m_c4.metric("Cost", f"${total_cost:.4f}")
                                
                                status.update(label="Follow-up Complete!", state="complete", expanded=False)
                                
                                st.divider()
                                st.markdown(followup_out)
                                
                                # Append to parent report
                                follow_up_num = append_followup_to_report(
                                    filepath=selected_report["filename"],
                                    followup_content=followup_out,
                                    question=followup_query,
                                    tokens_used=p_tokens,
                                    estimated_cost=total_cost
                                )
                                
                                st.success(f"✅ Appended as Follow-up #{follow_up_num} to `{selected_report['filename']}`")
                                
                                # Download the updated full report
                                with open(selected_report["filename"], "r") as f:
                                    updated_content = f.read()
                                st.download_button(
                                    "Download Updated Report", 
                                    updated_content, 
                                    file_name=selected_report["filename"]
                                )
                            else:
                                st.warning("No output.")
                        else:
                            st.error(f"Failed: {interaction.error}")
                            
                    except Exception as e:
                        st.error(f"Error: {e}")
