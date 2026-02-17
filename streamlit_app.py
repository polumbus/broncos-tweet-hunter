import streamlit as st
import tweepy
from anthropic import Anthropic
from datetime import datetime, timedelta
import os

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

# Keywords
BRONCOS_KEYWORDS = [
    "#Broncos", "#BroncosCountry", "Broncos", "Denver Broncos",
    "Bo Nix", "Surtain", "Sean Payton"
]

NUGGETS_KEYWORDS = [
    "#Nuggets", "Nuggets", "Denver Nuggets", "Jokic"
]

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

def get_top_debate_tweets():
    """Main processing: Combine all searches, dedupe, score, and split by team"""
    
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
            
            metrics = tweet.public_metrics
            
            # Apply filters
            if is_spam_tweet(tweet, metrics):
                continue
            
            if not is_original_tweet(tweet):
                continue
            
            # Calculate debate score
            score = calculate_debate_score(metrics, tweet.text)
            priority_info = determine_priority(tweet.text)
            
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
                'priority': priority_info
            })
            
            seen_ids.add(tweet.id)
    
    # Sort all tweets by debate score
    all_tweets.sort(key=lambda x: x['debate_score'], reverse=True)
    
    # Split back into Broncos vs Nuggets based on keyword matching
    broncos_keywords_lower = [k.lower() for k in BRONCOS_KEYWORDS]
    nuggets_keywords_lower = [k.lower() for k in NUGGETS_KEYWORDS]
    
    broncos_top = []
    nuggets_top = []
    
    for tweet in all_tweets:
        text_lower = tweet['text'].lower()
        
        # Check if it matches Broncos keywords
        is_broncos = any(kw in text_lower for kw in broncos_keywords_lower)
        is_nuggets = any(kw in text_lower for kw in nuggets_keywords_lower)
        
        # Prioritize Broncos if both match
        if is_broncos and len(broncos_top) < 10:
            broncos_top.append(tweet)
        elif is_nuggets and len(nuggets_top) < 5:
            nuggets_top.append(tweet)
        
        # Stop when we have enough
        if len(broncos_top) >= 10 and len(nuggets_top) >= 5:
            break
    
    return broncos_top, nuggets_top

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
    
    with st.container():
        if is_top_pick:
            st.markdown(f'<span class="top-pick-badge">⭐ TOP PICK #{pick_number}</span>', unsafe_allow_html=True)
        
        header_html = f'''
            <div style="margin-bottom: 12px;">
                <span class="priority-badge {tweet['priority']['color']}">{tweet['priority']['label']}</span>
        '''
        
        if is_debate:
            header_html += f'<span class="debate-badge">🔥 {tweet["replies"]} replies</span>'
        
        header_html += f'''
                <br>
                <strong style="color: #e7e9ea;">{tweet['author_name']}</strong> 
                <span style="color: #71767b;">@{tweet['author']}</span>
            </div>
        '''
        
        st.markdown(header_html, unsafe_allow_html=True)
        
        st.markdown(f'<div style="font-size: 15px; line-height: 20px; color: #e7e9ea; margin-bottom: 12px;">{tweet["text"]}</div>', unsafe_allow_html=True)
        
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

if st.button("🔍 Scan for Viral Broncos & Nuggets Debates", use_container_width=True):
    with st.spinner("Scanning Twitter for controversial Broncos & Nuggets content..."):
        
        # Get top tweets from all searches combined
        top_broncos, top_nuggets = get_top_debate_tweets()
        
        if top_broncos or top_nuggets:
            st.success(f"✅ Found {len(top_broncos)} Broncos + {len(top_nuggets)} Nuggets debates!")
            
            if top_broncos:
                top_3_count = min(3, len(top_broncos))
                if top_3_count > 0:
                    st.markdown("### ⭐ TOP 3 BRONCOS PICKS")
                    for i in range(top_3_count):
                        tweet = top_broncos[i]
                        display_tweet_card(tweet, is_top_pick=True, pick_number=i+1)
                        
                        with st.spinner("Generating rewrites in your voice..."):
                            rewrites = generate_rewrites(tweet['text'])
                        
                        st.markdown("**✍️ Your Rewrites:**")
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.markdown(f"<div class='rewrite-preview'><strong>Default:</strong><br>{rewrites['Default']}</div>", unsafe_allow_html=True)
                            if st.button("📋 Copy", key=f"copy_default_top{i}"):
                                st.code(rewrites['Default'], language=None)
                            
                            st.markdown(f"<div class='rewrite-preview'><strong>Analytical:</strong><br>{rewrites['Analytical']}</div>", unsafe_allow_html=True)
                            if st.button("📋 Copy", key=f"copy_analytical_top{i}"):
                                st.code(rewrites['Analytical'], language=None)
                        
                        with col2:
                            st.markdown(f"<div class='rewrite-preview'><strong>Controversial:</strong><br>{rewrites['Controversial']}</div>", unsafe_allow_html=True)
                            if st.button("📋 Copy", key=f"copy_controversial_top{i}"):
                                st.code(rewrites['Controversial'], language=None)
                            
                            st.markdown(f"<div class='rewrite-preview'><strong>Personal:</strong><br>{rewrites['Personal']}</div>", unsafe_allow_html=True)
                            if st.button("📋 Copy", key=f"copy_personal_top{i}"):
                                st.code(rewrites['Personal'], language=None)
                        
                        st.markdown("---")
                
                if len(top_broncos) > 3:
                    st.markdown("### 🏈 OTHER BRONCOS TWEETS")
                    for idx, tweet in enumerate(top_broncos[3:], start=3):
                        display_tweet_card(tweet, is_top_pick=False)
                        
                        with st.spinner("Generating rewrites in your voice..."):
                            rewrites = generate_rewrites(tweet['text'])
                        
                        st.markdown("**✍️ Your Rewrites:**")
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.markdown(f"<div class='rewrite-preview'><strong>Default:</strong><br>{rewrites['Default']}</div>", unsafe_allow_html=True)
                            if st.button("📋 Copy", key=f"copy_default_b{idx}"):
                                st.code(rewrites['Default'], language=None)
                            
                            st.markdown(f"<div class='rewrite-preview'><strong>Analytical:</strong><br>{rewrites['Analytical']}</div>", unsafe_allow_html=True)
                            if st.button("📋 Copy", key=f"copy_analytical_b{idx}"):
                                st.code(rewrites['Analytical'], language=None)
                        
                        with col2:
                            st.markdown(f"<div class='rewrite-preview'><strong>Controversial:</strong><br>{rewrites['Controversial']}</div>", unsafe_allow_html=True)
                            if st.button("📋 Copy", key=f"copy_controversial_b{idx}"):
                                st.code(rewrites['Controversial'], language=None)
                            
                            st.markdown(f"<div class='rewrite-preview'><strong>Personal:</strong><br>{rewrites['Personal']}</div>", unsafe_allow_html=True)
                            if st.button("📋 Copy", key=f"copy_personal_b{idx}"):
                                st.code(rewrites['Personal'], language=None)
                        
                        st.markdown("---")
            
            if top_nuggets:
                st.markdown("### 🏀 NUGGETS TWEETS")
                for idx, tweet in enumerate(top_nuggets):
                    display_tweet_card(tweet, is_top_pick=False)
                    
                    with st.spinner("Generating rewrites in your voice..."):
                        rewrites = generate_rewrites(tweet['text'])
                    
                    st.markdown("**✍️ Your Rewrites:**")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown(f"<div class='rewrite-preview'><strong>Default:</strong><br>{rewrites['Default']}</div>", unsafe_allow_html=True)
                        if st.button("📋 Copy", key=f"copy_default_n{idx}"):
                            st.code(rewrites['Default'], language=None)
                        
                        st.markdown(f"<div class='rewrite-preview'><strong>Analytical:</strong><br>{rewrites['Analytical']}</div>", unsafe_allow_html=True)
                        if st.button("📋 Copy", key=f"copy_analytical_n{idx}"):
                            st.code(rewrites['Analytical'], language=None)
                    
                    with col2:
                        st.markdown(f"<div class='rewrite-preview'><strong>Controversial:</strong><br>{rewrites['Controversial']}</div>", unsafe_allow_html=True)
                        if st.button("📋 Copy", key=f"copy_controversial_n{idx}"):
                            st.code(rewrites['Controversial'], language=None)
                        
                        st.markdown(f"<div class='rewrite-preview'><strong>Personal:</strong><br>{rewrites['Personal']}</div>", unsafe_allow_html=True)
                        if st.button("📋 Copy", key=f"copy_personal_n{idx}"):
                            st.code(rewrites['Personal'], language=None)
                    
                    st.markdown("---")
        else:
            st.warning("⚠️ No viral debates found in the last 36 hours. Try again later!")
