import streamlit as st
import tweepy
from anthropic import Anthropic
from datetime import datetime, timedelta
import os

# ========================================
# TESTING MODE - CHANGE THIS
# ========================================
TESTING_MODE = True  # Set to False when ready for full scanning
MAX_TWEETS = 20 if TESTING_MODE else 100  # 20 tweets in testing, 100 in production
DEBUG_MEDIA = True  # Shows detailed media debugging info
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
    .debug-box { background-color: #2d2d2d; padding: 10px; border-radius: 8px; margin: 10px 0; }
</style>
""", unsafe_allow_html=True)

os.environ["TWITTER_BEARER_TOKEN"] = st.secrets["TWITTER_BEARER_TOKEN"]
os.environ["ANTHROPIC_API_KEY"] = st.secrets["ANTHROPIC_API_KEY"]

client = Anthropic()
client_twitter = tweepy.Client(bearer_token=os.environ["TWITTER_BEARER_TOKEN"], wait_on_rate_limit=True)

st.title("🏈 Broncos Tweet Hunter - MEDIA DEBUG MODE")
if TESTING_MODE:
    st.caption(f"⚠️ TESTING MODE: Fetching only {MAX_TWEETS} tweets to save credits")
else:
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
    if tweet.text.startswith('RT @'):
        return False
    if tweet.text.startswith('@'):
        return False
    if hasattr(tweet, 'referenced_tweets') and tweet.referenced_tweets:
        return False
    return True

def search_viral_tweets(keywords, hours=48):
    """Search for viral tweets - DENVER BRONCOS ONLY"""
    query = " OR ".join([f'"{k}"' for k in keywords])
    query += " -\"Western Michigan\" -\"Boise State\" -\"high school\" -\"HS\" -\"prep\" -\"college\" -\"university\""
    query += " -is:retweet -is:reply lang:en"
    
    start_time = datetime.utcnow() - timedelta(hours=hours)
    
    try:
        tweets = client_twitter.search_recent_tweets(
            query=query,
            max_results=MAX_TWEETS,
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
            if not is_original_tweet(tweet):
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
        
        scored_tweets.sort(key=lambda x: x['engagement_score'], reverse=True)
        return scored_tweets
    except Exception as e:
        st.error(f"Error: {str(e)}")
        return []

def fetch_tweet_media_debug(tweet_id):
    """Fetch media with DETAILED debugging"""
    debug_info = {
        'tweet_id': tweet_id,
        'success': False,
        'has_includes': False,
        'has_media': False,
        'media_count': 0,
        'media_types': [],
        'error': None
    }
    
    try:
        tweet_data = client_twitter.get_tweet(
            tweet_id,
            expansions=['attachments.media_keys'],
            media_fields=['url', 'preview_image_url', 'type', 'variants']
        )
        
        debug_info['success'] = True
        
        if hasattr(tweet_data, 'includes'):
            debug_info['has_includes'] = True
            
            if tweet_data.includes and 'media' in tweet_data.includes:
                debug_info['has_media'] = True
                debug_info['media_count'] = len(tweet_data.includes['media'])
                debug_info['media_types'] = [m.type for m in tweet_data.includes['media']]
                
                if DEBUG_MEDIA:
                    st.markdown(f"""
                    <div class="debug-box">
                    ✅ <strong>MEDIA FOUND for tweet {tweet_id}:</strong><br>
                    - Count: {debug_info['media_count']}<br>
                    - Types: {', '.join(debug_info['media_types'])}
                    </div>
                    """, unsafe_allow_html=True)
                
                return tweet_data.includes['media'], debug_info
        
        if DEBUG_MEDIA:
            st.markdown(f"""
            <div class="debug-box">
            ⚠️ <strong>NO MEDIA for tweet {tweet_id}:</strong><br>
            - Has includes: {debug_info['has_includes']}<br>
            - Has media: {debug_info['has_media']}
            </div>
            """, unsafe_allow_html=True)
        
        return [], debug_info
        
    except Exception as e:
        debug_info['error'] = str(e)
        if DEBUG_MEDIA:
            st.error(f"❌ ERROR fetching media for tweet {tweet_id}: {str(e)}")
        return [], debug_info

def display_tweet_media(media_list):
    """Display media inline like Twitter"""
    if not media_list:
        return
    
    for idx, media in enumerate(media_list):
        try:
            if media.type == 'photo':
                if hasattr(media, 'url') and media.url:
                    st.success(f"📸 Displaying photo #{idx+1}")
                    st.image(media.url, use_container_width=True)
                else:
                    st.warning(f"Photo #{idx+1} has no URL attribute")
            elif media.type in ['video', 'animated_gif']:
                if hasattr(media, 'preview_image_url') and media.preview_image_url:
                    st.success(f"🎥 Displaying video preview #{idx+1}")
                    st.image(media.preview_image_url, use_container_width=True, caption="▶️ Video")
                else:
                    st.warning(f"Video #{idx+1} has no preview_image_url attribute")
        except Exception as e:
            st.error(f"Error displaying media #{idx+1}: {str(e)}")

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
            "Sean Payton", 
            "Bo Nix",
            "Patrick Surtain",
            "Courtland Sutton",
            "Javonte Williams",
            "Empower Field",
            "Mile High"
        ]
        broncos_tweets = search_viral_tweets(broncos_keywords)
        
        nuggets_keywords = ["Denver Nuggets", "Nikola Jokic", "Jokic", "Jamal Murray", "Ball Arena"]
        nuggets_tweets = search_viral_tweets(nuggets_keywords)
        
        top_broncos = broncos_tweets[:10]
        top_nuggets = nuggets_tweets[:5]
        
        if top_broncos or top_nuggets:
            st.success(f"✅ Found {len(top_broncos)} Broncos + {len(top_nuggets)} Nuggets debates!")
            
            # Show ALL Broncos tweets with media debug
            st.markdown("### 🏈 ALL BRONCOS TWEETS (WITH MEDIA DEBUG)")
            for idx, tweet in enumerate(top_broncos):
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
                    <a href="{tweet_url}" target="_blank" style="color: #1d9bf0; text-decoration: none;">🔗 View on Twitter →</a>
                </div>
                """, unsafe_allow_html=True)
                
                # Fetch and display media WITH DEBUG
                st.markdown(f"**🔍 Checking for media in tweet {idx+1}...**")
                media, debug_info = fetch_tweet_media_debug(tweet['id'])
                display_tweet_media(media)
                
                st.markdown("---")
        else:
            st.warning("No tweets found. Try again in a few moments!")
