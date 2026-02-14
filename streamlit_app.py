import streamlit as st
import tweepy
from anthropic import Anthropic
from datetime import datetime, timedelta
import os

st.set_page_config(page_title="Broncos Tweet Hunter", layout="wide", initial_sidebar_state="collapsed")

# Custom CSS to make it look like Twitter
st.markdown("""
<style>
    .main { background-color: #000000; color: #e7e9ea; }
    .stButton>button { 
        background-color: #1d9bf0; 
        color: white; 
        border-radius: 20px;
        border: none;
        font-weight: bold;
    }
    .tweet-card {
        background-color: #16181c;
        border: 1px solid #2f3336;
        border-radius: 16px;
        padding: 16px;
        margin: 12px 0;
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
    .tweet-link {
        color: #1d9bf0;
        text-decoration: none;
        font-size: 13px;
    }
    .tweet-link:hover {
        text-decoration: underline;
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
    .bo-nix { background-color: #ff4500; color: white; }
    .sean-payton { background-color: #ff8c00; color: white; }
    .broncos { background-color: #fb4f14; color: white; }
</style>
""", unsafe_allow_html=True)

# Set environment variables from secrets
os.environ["TWITTER_BEARER_TOKEN"] = st.secrets["TWITTER_BEARER_TOKEN"]
os.environ["ANTHROPIC_API_KEY"] = st.secrets["ANTHROPIC_API_KEY"]

client = Anthropic()
client_twitter = tweepy.Client(bearer_token=os.environ["TWITTER_BEARER_TOKEN"], wait_on_rate_limit=True)

st.title("🏈 Broncos Tweet Hunter")
st.caption("Find viral Broncos debates from the last 48 hours")

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
    """Search for viral tweets with media"""
    query = " OR ".join([f'"{k}"' for k in keywords]) + " -is:retweet lang:en"
    start_time = datetime.utcnow() - timedelta(hours=hours)
    
    try:
        tweets = client_twitter.search_recent_tweets(
            query=query,
            max_results=100,
            start_time=start_time,
            tweet_fields=['public_metrics', 'created_at'],
            expansions=['author_id', 'attachments.media_keys'],
            user_fields=['username', 'name'],
            media_fields=['url', 'preview_image_url', 'type']
        )
        
        if not tweets.data:
            return []
        
        users = {user.id: user for user in tweets.includes['users']}
        
        # Get media if it exists
        media_dict = {}
        if tweets.includes and 'media' in tweets.includes:
            media_dict = {media.media_key: media for media in tweets.includes['media']}
        
        scored_tweets = []
        
        for tweet in tweets.data:
            metrics = tweet.public_metrics
            priority_info = determine_priority(tweet.text)
            
            # Prioritize by replies first (controversy)
            engagement_score = (metrics['reply_count'] * 1000) + priority_info['priority']
            
            user = users.get(tweet.author_id)
            
            # Get media for this tweet
            tweet_media = []
            if hasattr(tweet, 'attachments') and tweet.attachments and 'media_keys' in tweet.attachments:
                for media_key in tweet.attachments['media_keys']:
                    if media_key in media_dict:
                        tweet_media.append(media_dict[media_key])
            
            scored_tweets.append({
                'id': tweet.id,
                'text': tweet.text,
                'author': user.username if user else 'Unknown',
                'author_name': user.name if user else 'Unknown',
                'created_at': tweet.created_at,
                'likes': metrics['like_count'],
                'retweets': metrics['retweet_count'],
                'replies': metrics['reply_count'],
                'impressions': metrics.get('impression_count', 0),
                'engagement_score': engagement_score,
                'priority': priority_info,
                'media': tweet_media
            })
        
        scored_tweets.sort(key=lambda x: x['engagement_score'], reverse=True)
        return scored_tweets[:10]
    
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

if st.button("🔍 Scan for Viral Broncos Debates", use_container_width=True):
    with st.spinner("Scanning Twitter for controversial Broncos content..."):
        keywords = ["Denver Broncos", "Sean Payton", "Bo Nix", "Broncos"]
        tweets = search_viral_tweets(keywords)
        
        if tweets:
            st.success(f"✅ Found {len(tweets)} viral debates! Sorted by controversy (reply count).")
            
            for tweet in tweets:
                # Tweet card with clickable link
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
                        <span>❤️ {tweet['likes']}</span>
                        <span>🔄 {tweet['retweets']}</span>
                    </div>
                    <a href="{tweet_url}" target="_blank" class="tweet-link">🔗 View on Twitter</a>
                </div>
                """, unsafe_allow_html=True)
                
                # Show images/videos if attached
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
except Exception as e:
    pass  # Silently skip if media can't be loaded
                
                # Generate all 4 rewrites
                with st.spinner("Generating rewrites in your voice..."):
                    rewrites = generate_rewrites(tweet['text'])
                
                # Show all rewrites as previews
                st.markdown("**✍️ Your Rewrites (Pick One to Edit & Post):**")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown(f"<div class='rewrite-preview'><strong>Default:</strong><br>{rewrites['Default']}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='rewrite-preview'><strong>Analytical:</strong><br>{rewrites['Analytical']}</div>", unsafe_allow_html=True)
                
                with col2:
                    st.markdown(f"<div class='rewrite-preview'><strong>Controversial:</strong><br>{rewrites['Controversial']}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='rewrite-preview'><strong>Personal:</strong><br>{rewrites['Personal']}</div>", unsafe_allow_html=True)
                
                st.markdown("---")
        else:
            st.warning("No tweets found. Try again in a few moments!")

