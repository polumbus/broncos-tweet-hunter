import streamlit as st
import tweepy
from anthropic import Anthropic
from datetime import datetime, timedelta
import os

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
    .tweet-card {
        background-color: #16181c;
        border: 1px solid #2f3336;
        border-radius: 16px;
        padding: 16px;
        margin: 12px 0;
    }
    .top-pick {
        background-color: #1a2332;
        border: 2px solid #1d9bf0;
        box-shadow: 0 0 20px rgba(29, 155, 240, 0.3);
    }
    .tweet-header {
        display: flex;
        align-items: center;
        margin-bottom: 12px;
    }
    .tweet-text {
        font-size: 15px;
        line-height: 20px;
        color: #e7e9ea;
        margin-bottom: 12px;
    }
    .tweet-metrics {
        display: flex;
        gap: 20px;
        color: #71767b;
        font-size: 13px;
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
</style>
""", unsafe_allow_html=True)

os.environ["TWITTER_BEARER_TOKEN"] = st.secrets["TWITTER_BEARER_TOKEN"]
os.environ["ANTHROPIC_API_KEY"] = st.secrets["ANTHROPIC_API_KEY"]

client = Anthropic()
client_twitter = tweepy.Client(bearer_token=os.environ["TWITTER_BEARER_TOKEN"], wait_on_rate_limit=True)

st.title("🏈 Broncos Tweet Hunter")
st.caption("Find the most controversial Denver Broncos debates from the last 48 hours")

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
    """Check if tweet is truly original (not a reply or retweet)"""
    # Filter out retweets (text starts with RT @)
    if tweet.text.startswith('RT @'):
        return False
    
    # Filter out replies (starts with @)
    if tweet.text.startswith('@'):
        return False
    
    # Filter out tweets with referenced tweets (replies, quotes, retweets)
    if hasattr(tweet, 'referenced_tweets') and tweet.referenced_tweets:
        return False
    
    return True

def search_viral_tweets(keywords, hours=48):
    """Search for viral tweets - DENVER BRONCOS ONLY"""
    # Build query with DENVER BRONCOS specific keywords only
    query = " OR ".join([f'"{k}"' for k in keywords])
    
    # Exclude college/high school teams
    query += " -\"Western Michigan\" -\"Boise State\" -\"high school\" -\"HS\" -\"prep\" -\"college\" -\"university\""
    
    # Exclude retweets and replies
    query += " -is:retweet -is:reply lang:en"
    
    start_time = datetime.utcnow() - timedelta(hours=hours)
    
    try:
        tweets = client_twitter.search_recent_tweets(
            query=query,
            max_results=100,
            start_time=start_time,
            tweet_fields=['public_metrics', 'created_at', 'referenced_tweets'],
            expansions=['author_id'],
            user_fields=['username', 'name']
        )
        
        if not tweets.data:
            return []
        
        users = {user.id: user for user in tweets.includes['users']}
        scored_tweets = []
        
        for tweet in tweets.data:
            # EXTRA FILTER: Only keep truly original tweets
            if not is_original_tweet(tweet):
                continue
            
            metrics = tweet.public_metrics
            priority_info = determine_priority(tweet.text)
            
            # CONTROVERSY RANKING: Replies MASSIVELY weighted (x100000) → Retweets (x100) → Likes (x1)
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
        
        scored_tweets.sort(key=lambda x: x['engagement_score'], reverse=True)
        return scored_tweets
    except Exception as e:
        st.error(f"Error: {str(e)}")
        return []

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

def display_tweet_media(media_list):
    """Display media inline like Twitter"""
    if not media_list:
        return
    
    for media in media_list:
        try:
            if media.type == 'photo' and hasattr(media, 'url'):
                st.image(media.url, use_container_width=True)
            elif media.type in ['video', 'animated_gif'] and hasattr(media, 'preview_image_url'):
                st.image(media.preview_image_url, use_container_width=True, caption="▶️ Video")
        except:
            pass

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
        # Search DENVER Broncos - specific keywords only
        broncos_keywords = [
            "Denver Broncos",
            "Sean Payton", 
            "Bo Nix",
            "Patrick Surtain",
            "Courtland Sutton",
            "Javonte Williams",
            "Empower Field",
            "Mile High"
        ]
        broncos_tweets = search_viral_tweets(broncos_keywords)
        
        # Search Nuggets
        nuggets_keywords = ["Denver Nuggets", "Nikola Jokic", "Jokic", "Jamal Murray", "Ball Arena"]
        nuggets_tweets = search_viral_tweets(nuggets_keywords)
        
        # Get top 10 Broncos and top 5 Nuggets
        top_broncos = broncos_tweets[:10]
        top_nuggets = nuggets_tweets[:5]
        
        if top_broncos or top_nuggets:
            st.success(f"✅ Found {len(top_broncos)} Broncos + {len(top_nuggets)} Nuggets debates!")
            
            # Show TOP 3 Broncos picks
            if len(top_broncos) >= 3:
                st.markdown("### ⭐ TOP 3 BRONCOS PICKS")
                for i, tweet in enumerate(top_broncos[:3]):
                    tweet_url = f"https://twitter.com/{tweet['author']}/status/{tweet['id']}"
                    
                    st.markdown(f"""
                    <div class="tweet-card top-pick">
                        <span class="top-pick-badge">⭐ TOP PICK #{i+1}</span>
                        <div class="tweet-header">
                            <span class="priority-badge {tweet['priority']['color']}">{tweet['priority']['label']}</span>
                            <strong>{tweet['author_name']}</strong> @{tweet['author']}
                        </div>
                        <div class="tweet-text">{tweet['text']}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Fetch and display media
                    media = fetch_tweet_media(tweet['id'])
                    display_tweet_media(media)
                    
                    st.markdown(f"""
                    <div class="tweet-metrics">
                        <span class="metric-high">💬 {tweet['replies']} replies</span>
                        <span class="metric-high">❤️ {tweet['likes']}</span>
                        <span class="metric-high">🔄 {tweet['retweets']}</span>
                    </div>
                    <a href="{tweet_url}" target="_blank" style="color: #1d9bf0; text-decoration: none;">🔗 View on Twitter →</a>
                    """, unsafe_allow_html=True)
                    
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
            
            # Show remaining Broncos tweets
            if len(top_broncos) > 3:
                st.markdown("### 🏈 OTHER BRONCOS TWEETS")
                for idx, tweet in enumerate(top_broncos[3:], start=3):
                    tweet_url = f"https://twitter.com/{tweet['author']}/status/{tweet['id']}"
                    
                    st.markdown(f"""
                    <div class="tweet-card">
                        <div class="tweet-header">
                            <span class="priority-badge {tweet['priority']['color']}">{tweet['priority']['label']}</span>
                            <strong>{tweet['author_name']}</strong> @{tweet['author']}
                        </div>
                        <div class="tweet-text">{tweet['text']}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Fetch and display media
                    media = fetch_tweet_media(tweet['id'])
                    display_tweet_media(media)
                    
                    st.markdown(f"""
                    <div class="tweet-metrics">
                        <span class="metric-high">💬 {tweet['replies']} replies</span>
                        <span>❤️ {tweet['likes']}</span>
                        <span>🔄 {tweet['retweets']}</span>
                    </div>
                    <a href="{tweet_url}" target="_blank" style="color: #1d9bf0; text-decoration: none;">🔗 View on Twitter →</a>
                    """, unsafe_allow_html=True)
                    
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
            
            # Show Nuggets tweets
            if top_nuggets:
                st.markdown("### 🏀 NUGGETS TWEETS")
                for idx, tweet in enumerate(top_nuggets):
                    tweet_url = f"https://twitter.com/{tweet['author']}/status/{tweet['id']}"
                    
                    st.markdown(f"""
                    <div class="tweet-card">
                        <div class="tweet-header">
                            <span class="priority-badge" style="background-color: #fdb927; color: #00285e;">🏀 NUGGETS</span>
                            <strong>{tweet['author_name']}</strong> @{tweet['author']}
                        </div>
                        <div class="tweet-text">{tweet['text']}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Fetch and display media
                    media = fetch_tweet_media(tweet['id'])
                    display_tweet_media(media)
                    
                    st.markdown(f"""
                    <div class="tweet-metrics">
                        <span class="metric-high">💬 {tweet['replies']} replies</span>
                        <span>❤️ {tweet['likes']}</span>
                        <span>🔄 {tweet['retweets']}</span>
                    </div>
                    <a href="{tweet_url}" target="_blank" style="color: #1d9bf0; text-decoration: none;">🔗 View on Twitter →</a>
                    """, unsafe_allow_html=True)
                    
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
