import streamlit as st
import tweepy
from anthropic import Anthropic
from datetime import datetime, timedelta
import os
from collections import defaultdict

# ========================================
# PRODUCTION MODE
# ========================================
TESTING_MODE = False
MAX_TWEETS = 100
HOURS_BACK = 36
# ========================================

st.set_page_config(page_title="Broncos Tweet Hunter", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    .main { background-color: #000000; color: #e7e9ea; }
    .stButton>button { 
        background-color: #1d9bf0; 
        color: white; 
        border-radius: 20px;
        border: none;
        font-weight: bold;
        padding: 12px 24px;
        font-size: 16px;
    }
    .stButton>button[kind="secondary"] {
        background-color: #2f3336;
        border: 1px solid #536471;
    }
    .stTextArea>div>div>textarea {
        background-color: #16181c;
        color: #e7e9ea;
        border: 1px solid #2f3336;
        border-radius: 8px;
    }
    div[data-testid="stVerticalBlock"] > div.tweet-card {
        background-color: #16181c;
        border: 1px solid #2f3336;
        border-radius: 16px;
        padding: 16px;
        margin: 12px 0;
    }
    div[data-testid="stVerticalBlock"] > div.top-pick {
        background-color: #1a2332;
        border: 2px solid #1d9bf0;
        box-shadow: 0 0 20px rgba(29, 155, 240, 0.3);
        border-radius: 16px;
        padding: 16px;
        margin: 12px 0;
    }
    .metric-high { color: #f91880; font-weight: bold; }
    .debate-badge {
        background-color: #ff4500;
        color: white;
        padding: 4px 10px;
        border-radius: 12px;
        font-size: 11px;
        font-weight: bold;
        margin-left: 8px;
    }
    .subject-badge {
        background-color: #2f3336;
        color: #8899a6;
        padding: 3px 8px;
        border-radius: 10px;
        font-size: 10px;
        font-weight: bold;
        margin-left: 6px;
    }
    .rewrite-preview {
        background-color: #1c1f23;
        border-left: 3px solid #1d9bf0;
        padding: 12px;
        margin: 8px 0;
        border-radius: 8px;
        font-size: 14px;
    }
    .priority-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: bold;
        margin-right: 8px;
    }
    .top-pick-badge {
        background-color: #1d9bf0;
        color: white;
        padding: 6px 14px;
        border-radius: 20px;
        font-size: 13px;
        font-weight: bold;
        margin-bottom: 8px;
        display: inline-block;
    }
    .bo-nix { background-color: #ff4500; color: white; }
    .sean-payton { background-color: #ff8c00; color: white; }
    .nuggets { background-color: #ffd700; color: black; }
    .broncos { background-color: #fb4f14; color: white; }
</style>
""", unsafe_allow_html=True)

os.environ["TWITTER_BEARER_TOKEN"] = st.secrets["TWITTER_BEARER_TOKEN"]
os.environ["ANTHROPIC_API_KEY"] = st.secrets["ANTHROPIC_API_KEY"]

client = Anthropic()
client_twitter = tweepy.Client(bearer_token=os.environ["TWITTER_BEARER_TOKEN"], wait_on_rate_limit=True)

st.title("🏈 Broncos Tweet Hunter")
st.caption(f"Find the most controversial Denver Broncos & Nuggets debates from the last {HOURS_BACK} hours")

# Initialize session state for tracking shown tweets
if 'shown_tweet_ids' not in st.session_state:
    st.session_state.shown_tweet_ids = set()

if 'edited_tweets' not in st.session_state:
    st.session_state.edited_tweets = {}

if 'generated_rewrites' not in st.session_state:
    st.session_state.generated_rewrites = {}

# Keywords
BRONCOS_KEYWORDS = [
    "Denver Broncos",        # Most specific - prioritize this
    "#Broncos",
    "#BroncosCountry",
    "Broncos NFL",           # Add NFL context
    "Bo Nix",
    "Surtain",
    "Sean Payton"
]

NUGGETS_KEYWORDS = [
    "#Nuggets", "Nuggets", "Denver Nuggets", "Jokic"
]

def extract_subjects(tweet_text):
    """Extract key subjects/topics from tweet - returns set of subject strings"""
    text_lower = tweet_text.lower()
    subjects = set()
    
    # BRONCOS PLAYERS
    if any(kw in text_lower for kw in ["bo nix", "nix", "bo-nix", "bonix"]):
        subjects.add("Bo Nix")
    if any(kw in text_lower for kw in ["patrick surtain", "surtain", "ps2"]):
        subjects.add("Patrick Surtain")
    if any(kw in text_lower for kw in ["courtland sutton", "sutton"]):
        subjects.add("Courtland Sutton")
    if any(kw in text_lower for kw in ["javonte williams", "javonte"]):
        subjects.add("Javonte Williams")
    if any(kw in text_lower for kw in ["russell wilson", "russ wilson", "russ"]):
        subjects.add("Russell Wilson")
    if any(kw in text_lower for kw in ["riley moss"]):
        subjects.add("Riley Moss")
    if any(kw in text_lower for kw in ["troy franklin", "franklin"]):
        subjects.add("Troy Franklin")
    
    # BRONCOS COACHES/STAFF
    if any(kw in text_lower for kw in ["sean payton", "payton", "coach payton"]):
        subjects.add("Sean Payton")
    if any(kw in text_lower for kw in ["vance joseph", "vance"]):
        subjects.add("Vance Joseph")
    
    # BRONCOS TOPICS
    if any(kw in text_lower for kw in ["fire payton", "payton out", "fire sean"]):
        subjects.add("Fire Payton")
    if any(kw in text_lower for kw in ["qb", "quarterback"]):
        subjects.add("QB Discussion")
    if any(kw in text_lower for kw in ["defense", "defensive", "no fly zone"]):
        subjects.add("Defense")
    if any(kw in text_lower for kw in ["offense", "offensive"]):
        subjects.add("Offense")
    if "draft" in text_lower:
        subjects.add("Draft")
    if any(kw in text_lower for kw in ["playoffs", "playoff"]):
        subjects.add("Playoffs")
    
    # NUGGETS PLAYERS
    if any(kw in text_lower for kw in ["nikola jokic", "jokic", "joker"]):
        subjects.add("Nikola Jokic")
    if any(kw in text_lower for kw in ["jamal murray", "murray"]):
        subjects.add("Jamal Murray")
    if any(kw in text_lower for kw in ["aaron gordon", "ag", "gordon"]):
        subjects.add("Aaron Gordon")
    if any(kw in text_lower for kw in ["michael porter", "mpj", "porter jr"]):
        subjects.add("Michael Porter Jr")
    
    # NUGGETS TOPICS
    if "mvp" in text_lower:
        subjects.add("MVP")
    if any(kw in text_lower for kw in ["rest", "resting", "load management"]):
        subjects.add("Player Rest")
    if any(kw in text_lower for kw in ["championship", "title", "ring"]):
        subjects.add("Championship")
    
    # GENERAL TOPICS (cross-team)
    if any(kw in text_lower for kw in ["trade", "traded", "trading"]):
        subjects.add("Trade Talk")
    if any(kw in text_lower for kw in ["aj brown", "a.j. brown"]):
        subjects.add("AJ Brown")
    if any(kw in text_lower for kw in ["contract", "extension", "deal"]):
        subjects.add("Contract")
    if any(kw in text_lower for kw in ["injury", "injured", "hurt"]):
        subjects.add("Injury")
    
    # Fallback: if no specific subject identified
    if not subjects:
        if "broncos" in text_lower:
            subjects.add("General Broncos")
        elif "nuggets" in text_lower or "jokic" in text_lower:
            subjects.add("General Nuggets")
        else:
            subjects.add("Other")
    
    return subjects

def determine_priority(tweet_text):
    """Determine ranking priority based on content"""
    text_lower = tweet_text.lower()
    if any(word in text_lower for word in ["bo nix", "nix", "bo mix"]):
        return {"priority": 100, "label": "🔥 BO NIX", "color": "bo-nix"}
    elif any(word in text_lower for word in ["sean payton", "payton"]):
        return {"priority": 75, "label": "⚡ SEAN PAYTON", "color": "sean-payton"}
    elif any(word in text_lower for word in ["jokic", "nuggets"]):
        return {"priority": 50, "label": "🏀 NUGGETS", "color": "nuggets"}
    return {"priority": 10, "label": "🏈 BRONCOS", "color": "broncos"}

def calculate_debate_score(metrics, tweet_text):
    """HEAVILY prioritizes replies (debate) + retweets (virality)"""
    text_lower = tweet_text.lower()
    
    # Base score — replies dominate
    score = (
        metrics['reply_count'] * 75000 +      # Debate king
        metrics['retweet_count'] * 1200 +     # Viral spread
        metrics['like_count'] * 8 +           # Minor factor
        determine_priority(tweet_text)['priority']
    )
    
    # Bonus for controversial language
    controversy_keywords = [
        "fire", "trade", "overrated", "bust", "sucks", "trash", "worst",
        "choke", "flop", "out", "hot take", "debate", "controversial",
        "payton out", "nix sucks", "jokic flop", "worst trade", "mistake",
        "regret", "washed", "benched", "russ cooked", "payton system",
        "draft mistake", "playoff miss", "murray inconsistent", "title window",
        "mpj contract", "no fly zone"
    ]
    if any(kw in text_lower for kw in controversy_keywords):
        score += 250000  # Huge boost
    
    return score

def is_spam_tweet(tweet, metrics):
    """Filter out spam tweets - RELAXED for debate tweets"""
    total = metrics['reply_count'] + metrics['like_count'] + metrics['retweet_count']
    
    # Allow high-engagement @-replies (debate threads)
    if tweet.text.startswith('@') and total < 15:
        return True
    
    # Block excessive mass mentions
    if tweet.text.count('@') >= 15:
        return True
    
    # Minimum engagement threshold
    if total < 8:
        return True
    
    return False

def is_wrong_broncos_team(tweet):
    """Filter out non-Denver Broncos teams (Brisbane Broncos rugby, etc.)"""
    text_lower = tweet.text.lower()
    
    # Exclude rugby/NRL keywords
    rugby_keywords = [
        "rugby", "nrl", "brisbane", "queensland", "super league",
        "world club challenge", "red hill", "suncorp stadium",
        "reece walsh", "adam reynolds", "broncos rugby", "league"
    ]
    
    if any(kw in text_lower for kw in rugby_keywords):
        return True
    
    # If tweet mentions "Broncos" but no NFL/Denver context, be suspicious
    if "broncos" in text_lower:
        nfl_context = [
            "denver", "nfl", "super bowl", "afc", "bo nix", 
            "sean payton", "surtain", "mile high", "empower field",
            "football", "quarterback", "qb", "touchdown"
        ]
        has_nfl_context = any(kw in text_lower for kw in nfl_context)
        
        # If it mentions "Broncos" but has NO NFL context, likely wrong team
        if not has_nfl_context:
            return True
    
    return False

def is_original_tweet(tweet):
    """Check if tweet is original - ONLY block actual retweets"""
    if tweet.text.startswith('RT @'):
        return False
    
    if hasattr(tweet, 'referenced_tweets') and tweet.referenced_tweets:
        for ref in tweet.referenced_tweets:
            if ref.type == 'retweeted':
                return False
    
    return True

def search_viral_tweets(keywords, hours=36, debate_mode=False):
    """Search for viral tweets - WITH RELEVANCY SORTING + OPTIONAL DEBATE MODE"""
    base_query = " OR ".join(keywords)
    query = f"({base_query}) -is:retweet lang:en"
    
    if debate_mode:
        # Controversy terms - tweets must match keywords AND have controversy
        controversy = [
            "fire", "trade", "overrated", "bust", "sucks", "trash", "worst",
            "choke", "flop", "out", "hot take", "debate", "controversial",
            "payton out", "nix sucks", "jokic flop", "worst trade", "mistake",
            "regret", "washed", "benched", "russ cooked"
        ]
        debate_part = " OR ".join(controversy)
        query = f"({query}) ({debate_part})"  # AND-like via parentheses
    
    start_time = datetime.utcnow() - timedelta(hours=hours)
    
    try:
        tweets = client_twitter.search_recent_tweets(
            query=query,
            max_results=MAX_TWEETS,
            start_time=start_time,
            sort_order='relevancy',  # CRITICAL: Get best tweets
            tweet_fields=['public_metrics', 'created_at', 'referenced_tweets'],
            expansions=['author_id'],
            user_fields=['username', 'name']
        )
        return tweets
    except Exception as e:
        st.error(f"Search error: {str(e)}")
        return None

def get_top_debate_tweets(exclude_ids=None):
    """Main processing: Combine searches, dedupe, score, and enforce subject diversity"""
    
    if exclude_ids is None:
        exclude_ids = set()
    
    # Run 4 searches
    broncos_normal = search_viral_tweets(BRONCOS_KEYWORDS, debate_mode=False)
    broncos_debate = search_viral_tweets(BRONCOS_KEYWORDS, debate_mode=True)
    nuggets_normal = search_viral_tweets(NUGGETS_KEYWORDS, debate_mode=False)
    nuggets_debate = search_viral_tweets(NUGGETS_KEYWORDS, debate_mode=True)
    
    all_tweets = []
    seen_ids = set()
    all_users = {}
    
    # Process all 4 search results
    for tweets_obj in [broncos_normal, broncos_debate, nuggets_normal, nuggets_debate]:
        if not tweets_obj or not tweets_obj.data:
            continue
        
        # Collect users
        if hasattr(tweets_obj, 'includes') and tweets_obj.includes and 'users' in tweets_obj.includes:
            for user in tweets_obj.includes['users']:
                all_users[user.id] = user
        
        # Process tweets
        for tweet in tweets_obj.data:
            # Skip duplicates
            if tweet.id in seen_ids:
                continue
            
            # Skip already shown tweets
            if tweet.id in exclude_ids:
                continue
            
            metrics = tweet.public_metrics
            
            # Apply filters
            if is_spam_tweet(tweet, metrics):
                continue
            
            if not is_original_tweet(tweet):
                continue
            
            # Filter out wrong Broncos team (rugby/Brisbane)
            if is_wrong_broncos_team(tweet):
                continue
            
            # Calculate debate score
            score = calculate_debate_score(metrics, tweet.text)
            priority_info = determine_priority(tweet.text)
            
            # Extract subjects for diversity tracking
            subjects = extract_subjects(tweet.text)
            
            user = all_users.get(tweet.author_id)
            
            all_tweets.append({
                'id': tweet.id,
                'text': tweet.text,
                'author': user.username if user else 'Unknown',
                'author_name': user.name if user else 'Unknown',
                'created_at': tweet.created_at,
                'likes': metrics['like_count'],
                'retweets': metrics['retweet_count'],
                'replies': metrics['reply_count'],
                'debate_score': score,
                'priority': priority_info,
                'subjects': subjects  # Store subjects for diversity
            })
            
            seen_ids.add(tweet.id)
    
    # Sort all tweets by debate score
    all_tweets.sort(key=lambda x: x['debate_score'], reverse=True)
    
    # DIVERSITY ENFORCEMENT: Max 2 tweets per subject
    broncos_keywords_lower = [k.lower() for k in BRONCOS_KEYWORDS]
    nuggets_keywords_lower = [k.lower() for k in NUGGETS_KEYWORDS]
    
    final_broncos = []
    final_nuggets = []
    subject_count_broncos = defaultdict(int)
    subject_count_nuggets = defaultdict(int)
    
    broncos_backup = []
    nuggets_backup = []
    
    for tweet in all_tweets:
        text_lower = tweet['text'].lower()
        
        # Determine if Broncos or Nuggets
        is_broncos = any(kw in text_lower for kw in broncos_keywords_lower)
        is_nuggets = any(kw in text_lower for kw in nuggets_keywords_lower)
        
        # Process Broncos tweets
        if is_broncos and len(final_broncos) < 10:
            # Check if any subject would exceed limit of 2
            can_add = True
            for subj in tweet['subjects']:
                if subject_count_broncos[subj] >= 2:
                    can_add = False
                    break
            
            if can_add:
                final_broncos.append(tweet)
                for subj in tweet['subjects']:
                    subject_count_broncos[subj] += 1
            else:
                broncos_backup.append(tweet)
        
        # Process Nuggets tweets
        elif is_nuggets and len(final_nuggets) < 5:
            # Check if any subject would exceed limit of 2
            can_add = True
            for subj in tweet['subjects']:
                if subject_count_nuggets[subj] >= 2:
                    can_add = False
                    break
            
            if can_add:
                final_nuggets.append(tweet)
                for subj in tweet['subjects']:
                    subject_count_nuggets[subj] += 1
            else:
                nuggets_backup.append(tweet)
    
    # FALLBACK: If short, relax to 3 max per subject
    if len(final_broncos) < 8 and broncos_backup:
        for tweet in broncos_backup:
            if len(final_broncos) >= 10:
                break
            
            can_add = True
            for subj in tweet['subjects']:
                if subject_count_broncos[subj] >= 3:  # Relaxed to 3
                    can_add = False
                    break
            
            if can_add:
                final_broncos.append(tweet)
                for subj in tweet['subjects']:
                    subject_count_broncos[subj] += 1
    
    if len(final_nuggets) < 4 and nuggets_backup:
        for tweet in nuggets_backup:
            if len(final_nuggets) >= 5:
                break
            
            can_add = True
            for subj in tweet['subjects']:
                if subject_count_nuggets[subj] >= 3:  # Relaxed to 3
                    can_add = False
                    break
            
            if can_add:
                final_nuggets.append(tweet)
                for subj in tweet['subjects']:
                    subject_count_nuggets[subj] += 1
    
    return final_broncos, final_nuggets

def fetch_tweet_media(tweet_id):
    """Fetch media for a specific tweet"""
    try:
        tweet_data = client_twitter.get_tweet(
            tweet_id,
            expansions=['attachments.media_keys'],
            media_fields=['url', 'preview_image_url', 'type', 'variants']
        )
        
        if hasattr(tweet_data, 'includes') and tweet_data.includes and 'media' in tweet_data.includes:
            return tweet_data.includes['media']
        return []
    except:
        return []

def display_tweet_card(tweet, is_top_pick=False, pick_number=None):
    """Display a tweet card using Streamlit container"""
    tweet_url = f"https://twitter.com/{tweet['author']}/status/{tweet['id']}"
    
    # Check if it's a hot debate (high replies)
    is_debate = tweet['replies'] >= 10
    
    # Get primary subject for badge
    primary_subject = list(tweet['subjects'])[0] if tweet['subjects'] else "General"
    
    with st.container():
        if is_top_pick:
            st.markdown(f'<span class="top-pick-badge">⭐ TOP PICK #{pick_number}</span>', unsafe_allow_html=True)
        
        header_html = f'''
            <div style="margin-bottom: 12px;">
                <span class="priority-badge {tweet['priority']['color']}">{tweet['priority']['label']}</span>
        '''
        
        if is_debate:
            header_html += f'<span class="debate-badge">🔥 {tweet["replies"]} replies</span>'
        
        # Show primary subject
        header_html += f'<span class="subject-badge">📌 {primary_subject}</span>'
        
        header_html += f'''
                <br>
                <strong style="color: #e7e9ea;">{tweet['author_name']}</strong> 
                <span style="color: #71767b;">@{tweet['author']}</span>
            </div>
        '''
        
        st.markdown(header_html, unsafe_allow_html=True)
        
        # Original tweet text
        st.markdown(f'<div style="font-size: 15px; line-height: 20px; color: #e7e9ea; margin-bottom: 8px;"><strong>Original:</strong></div>', unsafe_allow_html=True)
        st.markdown(f'<div style="font-size: 15px; line-height: 20px; color: #e7e9ea; margin-bottom: 12px;">{tweet["text"]}</div>', unsafe_allow_html=True)
        
        # Editable version
        tweet_id = tweet['id']
        if tweet_id not in st.session_state.edited_tweets:
            st.session_state.edited_tweets[tweet_id] = tweet['text']
        
        edited_text = st.text_area(
            "✏️ Edit tweet before generating rewrites:",
            value=st.session_state.edited_tweets[tweet_id],
            height=100,
            key=f"edit_{tweet_id}",
            help="Modify the tweet text, then click 'Generate Rewrites' below"
        )
        
        # Update session state when text changes
        st.session_state.edited_tweets[tweet_id] = edited_text
        
        col_reset, col_space = st.columns([1, 3])
        with col_reset:
            if st.button("↺ Reset", key=f"reset_{tweet_id}"):
                st.session_state.edited_tweets[tweet_id] = tweet['text']
                st.rerun()
        
        # Return the edited text for use in rewrites
        tweet['edited_text'] = edited_text
        
        media = fetch_tweet_media(tweet['id'])
        if media:
            for m in media:
                try:
                    if m.type == 'photo' and hasattr(m, 'url') and m.url:
                        st.image(m.url, width=300)
                    elif m.type in ['video', 'animated_gif'] and hasattr(m, 'preview_image_url') and m.preview_image_url:
                        st.image(m.preview_image_url, caption="▶️ Video", width=300)
                except:
                    pass
        
        metric_style = "metric-high" if is_top_pick else ""
        st.markdown(f'''
            <div style="display: flex; gap: 20px; color: #71767b; font-size: 13px; margin: 12px 0;">
                <span class="{metric_style}">💬 {tweet['replies']} replies</span>
                <span class="{metric_style}">🔄 {tweet['retweets']} RTs</span>
                <span class="{metric_style}">❤️ {tweet['likes']}</span>
            </div>
        ''', unsafe_allow_html=True)
        
        st.markdown(f'<a href="{tweet_url}" target="_blank" style="color: #1d9bf0; text-decoration: none;">🔗 View on Twitter →</a>', unsafe_allow_html=True)

def generate_rewrites(original_tweet):
    """Generate all 4 rewrite styles at once"""
    styles = {
        "Default": "Rewrite this tweet in Tyler's voice as a Broncos analyst. Keep it punchy and real.",
        "Analytical": "Rewrite with deep analysis. What would a former player see that others don't?",
        "Controversial": "Rewrite as a spicy take. Call out bad decisions. Make it debatable.",
        "Personal": "Rewrite with personal playing experience. Reference the locker room."
    }
    
    rewrites = {}
    
    for style_name, prompt in styles.items():
        try:
            message = client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=280,
                messages=[{
                    "role": "user",
                    "content": f"""You are Tyler, a Denver Broncos analyst and former player.

Original tweet: "{original_tweet}"

{prompt}

Keep it under 280 characters. Sound like Tyler - insider perspective, conversational, punchy."""
                }]
            )
            rewrites[style_name] = message.content[0].text
        except Exception as e:
            rewrites[style_name] = f"ERROR: {str(e)}"
    
    return rewrites

# Button section
col1, col2, col3 = st.columns([2, 2, 1])

with col1:
    scan_button = st.button("🔍 Scan for Viral Debates", use_container_width=True, type="primary")

with col2:
    scan_new_button = st.button("🆕 Scan Again (New Tweets Only)", use_container_width=True)

with col3:
    if st.button("🗑️ Clear History"):
        st.session_state.shown_tweet_ids = set()
        st.session_state.edited_tweets = {}
        st.session_state.generated_rewrites = {}
        st.success("History cleared!")
        st.rerun()

# Show count of previously seen tweets
if len(st.session_state.shown_tweet_ids) > 0:
    st.caption(f"📊 Already shown {len(st.session_state.shown_tweet_ids)} tweets (will be excluded from 'New Tweets Only' scans)")

if scan_button or scan_new_button:
    # Determine which tweets to exclude
    exclude_ids = st.session_state.shown_tweet_ids if scan_new_button else set()
    
    scan_type = "new tweets only" if scan_new_button else "all viral debates"
    
    with st.spinner(f"Scanning Twitter for {scan_type}..."):
        
        # Get top tweets with diversity enforcement
        top_broncos, top_nuggets = get_top_debate_tweets(exclude_ids=exclude_ids)
        
        # Track newly shown tweets
        for tweet in top_broncos + top_nuggets:
            st.session_state.shown_tweet_ids.add(tweet['id'])
        
        if top_broncos or top_nuggets:
            st.success(f"✅ Found {len(top_broncos)} Broncos + {len(top_nuggets)} Nuggets debates with max variety!")
            
            if top_broncos:
                top_3_count = min(3, len(top_broncos))
                if top_3_count > 0:
                    st.markdown("### ⭐ TOP 3 BRONCOS PICKS")
                    for i in range(top_3_count):
                        tweet = top_broncos[i]
                        display_tweet_card(tweet, is_top_pick=True, pick_number=i+1)
                        
                        # Use edited text if available, otherwise original
                        text_to_rewrite = tweet.get('edited_text', tweet['text'])
                        tweet_key = f"top{i}"
                        
                        if st.button(f"✨ Generate Rewrites", key=f"gen_{tweet_key}", use_container_width=True):
                            with st.spinner("Generating rewrites in your voice..."):
                                rewrites = generate_rewrites(text_to_rewrite)
                                st.session_state.generated_rewrites[tweet_key] = rewrites
                        
                        # Display rewrites if they exist
                        if tweet_key in st.session_state.generated_rewrites:
                            rewrites = st.session_state.generated_rewrites[tweet_key]
                            st.markdown("**✍️ Your Rewrites:**")
                            
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                st.markdown(f"<div class='rewrite-preview'><strong>Default:</strong><br>{rewrites['Default']}</div>", unsafe_allow_html=True)
                                if st.button("📋 Copy", key=f"copy_default_{tweet_key}"):
                                    st.code(rewrites['Default'], language=None)
                                
                                st.markdown(f"<div class='rewrite-preview'><strong>Analytical:</strong><br>{rewrites['Analytical']}</div>", unsafe_allow_html=True)
                                if st.button("📋 Copy", key=f"copy_analytical_{tweet_key}"):
                                    st.code(rewrites['Analytical'], language=None)
                            
                            with col2:
                                st.markdown(f"<div class='rewrite-preview'><strong>Controversial:</strong><br>{rewrites['Controversial']}</div>", unsafe_allow_html=True)
                                if st.button("📋 Copy", key=f"copy_controversial_{tweet_key}"):
                                    st.code(rewrites['Controversial'], language=None)
                                
                                st.markdown(f"<div class='rewrite-preview'><strong>Personal:</strong><br>{rewrites['Personal']}</div>", unsafe_allow_html=True)
                                if st.button("📋 Copy", key=f"copy_personal_{tweet_key}"):
                                    st.code(rewrites['Personal'], language=None)
                        
                        st.markdown("---")
                
                if len(top_broncos) > 3:
                    st.markdown("### 🏈 OTHER BRONCOS TWEETS")
                    for idx, tweet in enumerate(top_broncos[3:], start=3):
                        display_tweet_card(tweet, is_top_pick=False)
                        
                        # Use edited text if available, otherwise original
                        text_to_rewrite = tweet.get('edited_text', tweet['text'])
                        tweet_key = f"b{idx}"
                        
                        if st.button(f"✨ Generate Rewrites", key=f"gen_{tweet_key}", use_container_width=True):
                            with st.spinner("Generating rewrites in your voice..."):
                                rewrites = generate_rewrites(text_to_rewrite)
                                st.session_state.generated_rewrites[tweet_key] = rewrites
                        
                        # Display rewrites if they exist
                        if tweet_key in st.session_state.generated_rewrites:
                            rewrites = st.session_state.generated_rewrites[tweet_key]
                            st.markdown("**✍️ Your Rewrites:**")
                            
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                st.markdown(f"<div class='rewrite-preview'><strong>Default:</strong><br>{rewrites['Default']}</div>", unsafe_allow_html=True)
                                if st.button("📋 Copy", key=f"copy_default_{tweet_key}"):
                                    st.code(rewrites['Default'], language=None)
                                
                                st.markdown(f"<div class='rewrite-preview'><strong>Analytical:</strong><br>{rewrites['Analytical']}</div>", unsafe_allow_html=True)
                                if st.button("📋 Copy", key=f"copy_analytical_{tweet_key}"):
                                    st.code(rewrites['Analytical'], language=None)
                            
                            with col2:
                                st.markdown(f"<div class='rewrite-preview'><strong>Controversial:</strong><br>{rewrites['Controversial']}</div>", unsafe_allow_html=True)
                                if st.button("📋 Copy", key=f"copy_controversial_{tweet_key}"):
                                    st.code(rewrites['Controversial'], language=None)
                                
                                st.markdown(f"<div class='rewrite-preview'><strong>Personal:</strong><br>{rewrites['Personal']}</div>", unsafe_allow_html=True)
                                if st.button("📋 Copy", key=f"copy_personal_{tweet_key}"):
                                    st.code(rewrites['Personal'], language=None)
                        
                        st.markdown("---")
            
            if top_nuggets:
                st.markdown("### 🏀 NUGGETS TWEETS")
                for idx, tweet in enumerate(top_nuggets):
                    display_tweet_card(tweet, is_top_pick=False)
                    
                    # Use edited text if available, otherwise original
                    text_to_rewrite = tweet.get('edited_text', tweet['text'])
                    tweet_key = f"n{idx}"
                    
                    if st.button(f"✨ Generate Rewrites", key=f"gen_{tweet_key}", use_container_width=True):
                        with st.spinner("Generating rewrites in your voice..."):
                            rewrites = generate_rewrites(text_to_rewrite)
                            st.session_state.generated_rewrites[tweet_key] = rewrites
                    
                    # Display rewrites if they exist
                    if tweet_key in st.session_state.generated_rewrites:
                        rewrites = st.session_state.generated_rewrites[tweet_key]
                        st.markdown("**✍️ Your Rewrites:**")
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.markdown(f"<div class='rewrite-preview'><strong>Default:</strong><br>{rewrites['Default']}</div>", unsafe_allow_html=True)
                            if st.button("📋 Copy", key=f"copy_default_{tweet_key}"):
                                st.code(rewrites['Default'], language=None)
                            
                            st.markdown(f"<div class='rewrite-preview'><strong>Analytical:</strong><br>{rewrites['Analytical']}</div>", unsafe_allow_html=True)
                            if st.button("📋 Copy", key=f"copy_analytical_{tweet_key}"):
                                st.code(rewrites['Analytical'], language=None)
                        
                        with col2:
                            st.markdown(f"<div class='rewrite-preview'><strong>Controversial:</strong><br>{rewrites['Controversial']}</div>", unsafe_allow_html=True)
                            if st.button("📋 Copy", key=f"copy_controversial_{tweet_key}"):
                                st.code(rewrites['Controversial'], language=None)
                            
                            st.markdown(f"<div class='rewrite-preview'><strong>Personal:</strong><br>{rewrites['Personal']}</div>", unsafe_allow_html=True)
                            if st.button("📋 Copy", key=f"copy_personal_{tweet_key}"):
                                st.code(rewrites['Personal'], language=None)
                    
                    st.markdown("---")
        else:
            if scan_new_button and len(exclude_ids) > 0:
                st.warning(f"⚠️ No NEW viral debates found (already showed {len(exclude_ids)} tweets). Try regular scan or clear history!")
            else:
                st.warning("⚠️ No viral debates found in the last 36 hours. Try again later!")
