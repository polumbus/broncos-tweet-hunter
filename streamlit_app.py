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
st.caption("Find viral bangers from the last 48 hours")

def determine_priority(tweet_text):
    """Determine ranking priority based on content"""
    text_lower = tweet_text.lower()
    if "bo nix" in text_lower or "bo mix" in text_lower:
        return {"rank": 1, "label": "🔥 BO NIX", "color": "bo-nix", "priority": 1000000}
    elif "sean payton" in text_lower or "payton" in text_lower:
        return {"rank": 2, "label": "⚡ SEAN PAYTON", "color": "sean-payton", "priority": 500000}
    else:
        return {"rank": 3, "label": "🏈 BRONCOS", "color": "broncos", "priority": 100000}

def search_viral_tweets(keywords, hours=48):
    """Search for viral tweets"""
    query = " OR ".join([f'"{k}"' for k in keywords]) + " -is:retweet lang:en"
    start_time = datetime.utcnow() - timedelta(hours=hours)
    
    try:
        tweets = client_twitter.search_recent_tweets(
            query=query,
            max_results=100,
            start_time=start_time,
            tweet_fields=['public_metrics', 'created_at'],
            expansions=['author_id'],
            user_fields=['username', 'name']
        )
        
        if not tweets.data:
            return []
        
        users = {user.id: user for user in tweets.includes['users']}
        viral_tweets = []
        
        for tweet in tweets.data:
            metrics = tweet.public_metrics
            
            # Filter: 10+ replies, 50+ likes, 5+ RTs
            if (metrics['reply_count'] >= 10 and 
                metrics['like_count'] >= 50 and 
                metrics['retweet_count'] >= 5):
                
                priority_info = determine_priority(tweet.text)
                
                # Rank: Replies (x10000), Retweets (x100), Likes (x1)
                engagement_score = (
                    (metrics['reply_count'] * 10000) + 
                    (metrics['retweet_count'] * 100) + 
                    metrics['like_count'] + 
                    priority_info['priority']
                )
                
                user = users.get(tweet.author_id)
                
                viral_tweets.append({
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
        
        viral_tweets.sort(key=lambda x: x['engagement_score'], reverse=True)
        return viral_tweets
    
    except Exception as e:
        st.error(f"Error: {str(e)}")
        return []

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

if st.button("🔍 Scan for Viral Broncos & Nuggets", use_container_width=True):
    with st.spinner("Scanning for viral bangers (10+ replies, 50+ likes, 5+ RTs)..."):
        # Search Broncos
        broncos_keywords = ["Denver Broncos", "Sean Payton", "Bo Nix", "Broncos"]
        broncos_tweets = search_viral_tweets(broncos_keywords)
        
        # Search Nuggets
        nuggets_keywords = ["Denver Nuggets", "Nikola Jokic", "Nuggets"]
        nuggets_tweets = search_viral_tweets(nuggets_keywords)
        
        # Get top 10 Broncos and top 5 Nuggets
        top_broncos = broncos_tweets[:10]
        top_nuggets = nuggets_tweets[:5]
        
        if top_broncos or top_nuggets:
            st.success(f"✅ Found {len(top_broncos)} Broncos + {len(top_nuggets)} Nuggets viral bangers!")
            
            # TOP 3 BRONCOS PICKS
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
                        <div class="tweet-metrics">
                            <span class="metric-high">💬 {tweet['replies']} replies</span>
                            <span class="metric-high">🔄 {tweet['retweets']} RTs</span>
                            <span class="metric-high">❤️ {tweet['likes']} likes</span>
                        </div>
                        <a href="{tweet_url}" target="_blank" style="color: #1d9bf0; text-decoration: none;">🔗 View on Twitter →</a>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Show media
                    try:
                        tweet_details = client_twitter.get_tweet(
                            tweet['id'], 
                            expansions='attachments.media_keys', 
                            media_fields='url,preview_image_url,type,variants'
                        )
                        
                        if tweet_details.includes and 'media' in tweet_details.includes:
                            st.markdown("**📸 Media:**")
                            for media in tweet_details.includes['media']:
                                if media.type == 'photo':
                                    if hasattr(media, 'url') and media.url:
                                        st.image(media.url, use_container_width=True)
                                elif media.type == 'video' or media.type == 'animated_gif':
                                    if hasattr(media, 'preview_image_url') and media.preview_image_url:
                                        st.image(media.preview_image_url, caption="Video preview", use_container_width=True)
                    except:
                        pass
                    
                    with st.spinner("Generating rewrites..."):
                        rewrites = generate_rewrites(tweet['text'])
                    
                    st.markdown("**✍️ Your Rewrites:**")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown(f"<div class='rewrite-preview'><strong>Default:</strong><br>{rewrites['Default']}</div>", unsafe_allow_html=True)
                        if st.button(f"📋 Copy", key=f"copy_default_{i}"):
                            st.code(rewrites['Default'], language=None)
                        
                        st.markdown(f"<div class='rewrite-preview'><strong>Analytical:</strong><br>{rewrites['Analytical']}</div>", unsafe_allow_html=True)
                        if st.button(f"📋 Copy", key=f"copy_analytical_{i}"):
                            st.code(rewrites['Analytical'], language=None)
                    
                    with col2:
                        st.markdown(f"<div class='rewrite-preview'><strong>Controversial:</strong><br>{rewrites['Controversial']}</div>", unsafe_allow_html=True)
                        if st.button(f"📋 Copy", key=f"copy_controversial_{i}"):
                            st.code(rewrites['Controversial'], language=None)
                        
                        st.markdown(f"<div class='rewrite-preview'><strong>Personal:</strong><br>{rewrites['Personal']}</div>", unsafe_allow_html=True)
                        if st.button(f"📋 Copy", key=f"copy_personal_{i}"):
                            st.code(rewrites['Personal'], language=None)
                    
                    st.markdown("---")
            
            # OTHER BRONCOS TWEETS
            if len(top_broncos) > 3:
                st.markdown("### 🏈 Other Broncos Tweets")
                for i, tweet in enumerate(top_broncos[3:], start=3):
                    tweet_url = f"https://twitter.com/{tweet['author']}/status/{tweet['id']}"
                    
                    st.markdown(f"""
                    <div class="tweet-card">
                        <div class="tweet-header">
                            <span class="priority-badge {tweet['priority']['color']}">{tweet['priority']['label']}</span>
                            <strong>{tweet['author_name']}</strong> @{tweet['author']}
                        </div>
                        <div class="tweet-text">{tweet['text']}</div>
                        <div class="tweet-metrics">
                            <span class="metric-high">💬 {tweet['replies']} replies</span>
                            <span>🔄 {tweet['retweets']} RTs</span>
                            <span>❤️ {tweet['likes']} likes</span>
                        </div>
                        <a href="{tweet_url}" target="_blank" style="color: #1d9bf0; text-decoration: none;">🔗 View on Twitter →</a>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Show media
                    try:
                        tweet_details = client_twitter.get_tweet(
                            tweet['id'], 
                            expansions='attachments.media_keys', 
                            media_fields='url,preview_image_url,type,variants'
                        )
                        
                        if tweet_details.includes and 'media' in tweet_details.includes:
                            st.markdown("**📸 Media:**")
                            for media in tweet_details.includes['media']:
                                if media.type == 'photo':
                                    if hasattr(media, 'url') and media.url:
                                        st.image(media.url, use_container_width=True)
                                elif media.type == 'video' or media.type == 'animated_gif':
                                    if hasattr(media, 'preview_image_url') and media.preview_image_url:
                                        st.image(media.preview_image_url, caption="Video preview", use_container_width=True)
                    except:
                        pass
                    
                    with st.spinner("Generating rewrites..."):
                        rewrites = generate_rewrites(tweet['text'])
                    
                    st.markdown("**✍️ Your Rewrites:**")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown(f"<div class='rewrite-preview'><strong>Default:</strong><br>{rewrites['Default']}</div>", unsafe_allow_html=True)
                        if st.button(f"📋 Copy", key=f"copy_default_b{i}"):
                            st.code(rewrites['Default'], language=None)
                        
                        st.markdown(f"<div class='rewrite-preview'><strong>Analytical:</strong><br>{rewrites['Analytical']}</div>", unsafe_allow_html=True)
                        if st.button(f"📋 Copy", key=f"copy_analytical_b{i}"):
                            st.code(rewrites['Analytical'], language=None)
                    
                    with col2:
                        st.markdown(f"<div class='rewrite-preview'><strong>Controversial:</strong><br>{rewrites['Controversial']}</div>", unsafe_allow_html=True)
                        if st.button(f"📋 Copy", key=f"copy_controversial_b{i}"):
                            st.code(rewrites['Controversial'], language=None)
                        
                        st.markdown(f"<div class='rewrite-preview'><strong>Personal:</strong><br>{rewrites['Personal']}</div>", unsafe_allow_html=True)
                        if st.button(f"📋 Copy", key=f"copy_personal_b{i}"):
                            st.code(rewrites['Personal'], language=None)
                    
                    st.markdown("---")
            
            # NUGGETS TWEETS
            if top_nuggets:
                st.markdown("### 🏀 Denver Nuggets Tweets")
                for i, tweet in enumerate(top_nuggets):
                    tweet_url = f"https://twitter.com/{tweet['author']}/status/{tweet['id']}"
                    
                    st.markdown(f"""
                    <div class="tweet-card">
                        <div class="tweet-header">
                            <span class="priority-badge" style="background-color: #fdb927; color: #00285e;">🏀 NUGGETS</span>
                            <strong>{tweet['author_name']}</strong> @{tweet['author']}
                        </div>
                        <div class="tweet-text">{tweet['text']}</div>
                        <div class="tweet-metrics">
                            <span class="metric-high">💬 {tweet['replies']} replies</span>
                            <span>🔄 {tweet['retweets']} RTs</span>
                            <span>❤️ {tweet['likes']} likes</span>
                        </div>
                        <a href="{tweet_url}" target="_blank" style="color: #1d9bf0; text-decoration: none;">🔗 View on Twitter →</a>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Show media
                    try:
                        tweet_details = client_twitter.get_tweet(
                            tweet['id'], 
                            expansions='attachments.media_keys', 
                            media_fields='url,preview_image_url,type,variants'
                        )
                        
                        if tweet_details.includes and 'media' in tweet_details.includes:
                            st.markdown("**📸 Media:**")
                            for media in tweet_details.includes['media']:
                                if media.type == 'photo':
                                    if hasattr(media, 'url') and media.url:
                                        st.image(media.url, use_container_width=True)
                                elif media.type == 'video' or media.type == 'animated_gif':
                                    if hasattr(media, 'preview_image_url') and media.preview_image_url:
                                        st.image(media.preview_image_url, caption="Video preview", use_container_width=True)
                    except:
                        pass
                    
                    with st.spinner("Generating rewrites..."):
                        rewrites = generate_rewrites(tweet['text'])
                    
                    st.markdown("**✍️ Your Rewrites:**")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown(f"<div class='rewrite-preview'><strong>Default:</strong><br>{rewrites['Default']}</div>", unsafe_allow_html=True)
                        if st.button(f"📋 Copy", key=f"copy_default_n{i}"):
                            st.code(rewrites['Default'], language=None)
                        
                        st.markdown(f"<div class='rewrite-preview'><strong>Analytical:</strong><br>{rewrites['Analytical']}</div>", unsafe_allow_html=True)
                        if st.button(f"📋 Copy", key=f"copy_analytical_n{i}"):
                            st.code(rewrites['Analytical'], language=None)
                    
                    with col2:
                        st.markdown(f"<div class='rewrite-preview'><strong>Controversial:</strong><br>{rewrites['Controversial']}</div>", unsafe_allow_html=True)
                        if st.button(f"📋 Copy", key=f"copy_controversial_n{i}"):
                            st.code(rewrites['Controversial'], language=None)
                        
                        st.markdown(f"<div class='rewrite-preview'><strong>Personal:</strong><br>{rewrites['Personal']}</div>", unsafe_allow_html=True)
                        if st.button(f"📋 Copy", key=f"copy_personal_n{i}"):
                            st.code(rewrites['Personal'], language=None)
                    
                    st.markdown("---")
        else:
            st.warning("No viral bangers found matching your criteria. Try again later!")
