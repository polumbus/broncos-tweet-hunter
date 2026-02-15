import streamlit as st
import tweepy
from anthropic import Anthropic
from datetime import datetime, timedelta
import os

# ========================================
# TESTING MODE - CHANGE THIS
# ========================================
TESTING_MODE = True  # Set to False when ready for full scanning
MAX_TWEETS = 20  # Always 20 tweets to save Twitter API credits
HOURS_BACK = 720 if TESTING_MODE else 36  # 30 days for testing, 36 hours for production
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
    .broncos { background-color: #fb4f14; color: white; }
    .debug-box {
        background-color: #2d2d2d;
        border: 1px solid #444;
        border-radius: 8px;
        padding: 12px;
        margin: 12px 0;
        font-family: monospace;
        font-size: 12px;
        color: #00ff00;
    }
</style>
""", unsafe_allow_html=True)

os.environ["TWITTER_BEARER_TOKEN"] = st.secrets["TWITTER_BEARER_TOKEN"]
os.environ["ANTHROPIC_API_KEY"] = st.secrets["ANTHROPIC_API_KEY"]

client = Anthropic()
client_twitter = tweepy.Client(bearer_token=os.environ["TWITTER_BEARER_TOKEN"], wait_on_rate_limit=True)

st.title("🏈 Broncos Tweet Hunter")
if TESTING_MODE:
    st.caption(f"⚠️ TESTING MODE: Fetching {MAX_TWEETS} tweets from last {HOURS_BACK//24} days")
else:
    st.caption(f"Find the most controversial Denver Broncos debates from the last {HOURS_BACK} hours")

def determine_priority(tweet_text):
    """Determine ranking priority based on content - SMALL tiebreaker only"""
    text_lower = tweet_text.lower()
    if "bo nix" in text_lower or "bo mix" in text_lower:
        return {"rank": 1, "label": "🔥 BO NIX", "color": "bo-nix", "priority": 100}
    elif "sean payton" in text_lower or "payton" in text_lower:
        return {"rank": 2, "label": "⚡ SEAN PAYTON", "color": "sean-payton", "priority": 50}
    else:
        return {"rank": 3, "label": "🏈 BRONCOS", "color": "broncos", "priority": 10}

def is_original_tweet(tweet):
    """Check if tweet is original - LESS AGGRESSIVE FILTERING"""
    if tweet.text.startswith('RT @'):
        return False
    
    if hasattr(tweet, 'referenced_tweets') and tweet.referenced_tweets:
        for ref in tweet.referenced_tweets:
            if ref.type == 'retweeted':
                return False
    
    return True

def search_viral_tweets(keywords, hours=None):
    """Search for viral tweets with DEBUG LOGGING"""
    if hours is None:
        hours = HOURS_BACK
    
    query = " OR ".join([f'"{k}"' for k in keywords])
    query += " -is:retweet -is:reply lang:en"
    
    start_time = datetime.utcnow() - timedelta(hours=hours)
    
    # DEBUG: Show query info
    debug_info = {
        'query_length': len(query),
        'query': query,
        'start_time': start_time.isoformat(),
        'max_tweets_requested': MAX_TWEETS
    }
    
    try:
        tweets = client_twitter.search_recent_tweets(
            query=query,
            max_results=MAX_TWEETS,
            start_time=start_time,
            tweet_fields=['public_metrics', 'created_at', 'referenced_tweets'],
            expansions=['author_id'],
            user_fields=['username', 'name']
        )
        
        # DEBUG: Count tweets at each stage
        debug_info['tweets_returned_by_twitter'] = len(tweets.data) if tweets.data else 0
        
        if not tweets.data:
            return [], debug_info
        
        users = {user.id: user for user in tweets.includes['users']}
        scored_tweets = []
        filtered_count = 0
        
        for tweet in tweets.data:
            if not is_original_tweet(tweet):
                filtered_count += 1
                continue
            
            metrics = tweet.public_metrics
            priority_info = determine_priority(tweet.text)
            
            engagement_score = (
                (metrics['reply_count'] * 100000) + 
                (metrics['retweet_count'] * 100) + 
                metrics['like_count'] + 
                priority_info['priority']
            )
            
            user = users.get(tweet.author_id)
            
            scored_tweets.append({
                'id': tweet.id,
                'text': tweet.text,
                'author': user.username if user else 'Unknown',
                'author_name': user.name if user else 'Unknown',
                'created_at': tweet.created_at,
                'likes': metrics['like_count'],
                'retweets': metrics['retweet_count'],
                'replies': metrics['reply_count'],
                'engagement_score': engagement_score,
                'priority': priority_info
            })
        
        # DEBUG: Final counts
        debug_info['filtered_out_by_is_original'] = filtered_count
        debug_info['final_tweet_count'] = len(scored_tweets)
        
        scored_tweets.sort(key=lambda x: x['engagement_score'], reverse=True)
        return scored_tweets, debug_info
    except Exception as e:
        debug_info['error'] = str(e)
        st.error(f"Error: {str(e)}")
        return [], debug_info

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
    
    with st.container():
        if is_top_pick:
            st.markdown(f'<span class="top-pick-badge">⭐ TOP PICK #{pick_number}</span>', unsafe_allow_html=True)
        
        st.markdown(f'''
            <div style="margin-bottom: 12px;">
                <span class="priority-badge {tweet['priority']['color']}">{tweet['priority']['label']}</span>
                <strong style="color: #e7e9ea;">{tweet['author_name']}</strong> 
                <span style="color: #71767b;">@{tweet['author']}</span>
            </div>
        ''', unsafe_allow_html=True)
        
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
                <span class="{metric_style}">❤️ {tweet['likes']}</span>
                <span class="{metric_style}">🔄 {tweet['retweets']}</span>
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
        broncos_keywords = [
            "Denver Broncos",
            "Bo Nix",
            "Surtain",
            "Courtland Sutton",
            "Meinerz",
            "Bolles",
            "Zach Allen",
            "Nik Bonitto",
            "Evan Engram",
            "McGlinchey",
            "Marvin Mims",
            "Hufanga",
            "Dre Greenlaw",
            "Troy Franklin",
            "Dobbins",
            "RJ Harvey",
            "Singleton",
            "McLaughlin",
            "Sean Payton",
            "Vance Joseph",
            "Davis Webb",
            "Broncos free agency",
            "Broncos draft",
            "Broncos mock draft",
            "Broncos trade"
        ]
        broncos_tweets, broncos_debug = search_viral_tweets(broncos_keywords)
        
        nuggets_keywords = [
            "Denver Nuggets",
            "Nikola Jokic",
            "Jamal Murray"
        ]
        nuggets_tweets, nuggets_debug = search_viral_tweets(nuggets_keywords)
        
        # SHOW DEBUG INFO
        st.markdown("### 🐛 DEBUG INFO")
        st.markdown(f'''
        <div class="debug-box">
        <strong>BRONCOS SEARCH:</strong><br>
        - Query length: {broncos_debug.get('query_length', 'N/A')} chars<br>
        - Tweets returned by Twitter: {broncos_debug.get('tweets_returned_by_twitter', 0)}<br>
        - Filtered out by is_original_tweet(): {broncos_debug.get('filtered_out_by_is_original', 0)}<br>
        - Final tweet count: {broncos_debug.get('final_tweet_count', 0)}<br>
        <br>
        <strong>NUGGETS SEARCH:</strong><br>
        - Query length: {nuggets_debug.get('query_length', 'N/A')} chars<br>
        - Tweets returned by Twitter: {nuggets_debug.get('tweets_returned_by_twitter', 0)}<br>
        - Filtered out by is_original_tweet(): {nuggets_debug.get('filtered_out_by_is_original', 0)}<br>
        - Final tweet count: {nuggets_debug.get('final_tweet_count', 0)}
        </div>
        ''', unsafe_allow_html=True)
        
        top_broncos = broncos_tweets[:10]
        top_nuggets = nuggets_tweets[:5]
        
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
            st.warning("No tweets found. Try again in a few moments!")
