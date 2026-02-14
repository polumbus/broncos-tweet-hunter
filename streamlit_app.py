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
</style>
""", unsafe_allow_html=True)

os.environ["TWITTER_BEARER_TOKEN"] = st.secrets["TWITTER_BEARER_TOKEN"]
os.environ["ANTHROPIC_API_KEY"] = st.secrets["ANTHROPIC_API_KEY"]

client = Anthropic()
client_twitter = tweepy.Client(bearer_token=os.environ["TWITTER_BEARER_TOKEN"], wait_on_rate_limit=True)

st.title("🏈 Broncos Tweet Hunter - DEBUG MODE")
st.caption("Showing ALL tweets found (no filters)")

def search_all_tweets(keywords, hours=48):
    """Search for ALL tweets with NO filtering"""
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
        all_tweets = []
        
        for tweet in tweets.data:
            metrics = tweet.public_metrics
            user = users.get(tweet.author_id)
            
            # NO FILTERING - show everything
            engagement_score = (metrics['reply_count'] * 10000) + (metrics['retweet_count'] * 100) + metrics['like_count']
            
            all_tweets.append({
                'id': tweet.id,
                'text': tweet.text,
                'author': user.username if user else 'Unknown',
                'author_name': user.name if user else 'Unknown',
                'likes': metrics['like_count'],
                'retweets': metrics['retweet_count'],
                'replies': metrics['reply_count'],
                'engagement_score': engagement_score
            })
        
        all_tweets.sort(key=lambda x: x['engagement_score'], reverse=True)
        return all_tweets
    
    except Exception as e:
        st.error(f"Error: {str(e)}")
        return []

if st.button("🔍 Scan (Show Everything - No Filters)", use_container_width=True):
    with st.spinner("Searching..."):
        broncos_keywords = ["Denver Broncos", "Sean Payton", "Bo Nix", "Broncos"]
        tweets = search_all_tweets(broncos_keywords)
        
        if tweets:
            st.success(f"✅ Found {len(tweets)} total Broncos tweets in last 48 hours")
            
            for i, tweet in enumerate(tweets[:20]):
                tweet_url = f"https://twitter.com/{tweet['author']}/status/{tweet['id']}"
                
                st.markdown(f"""
                <div class="tweet-card">
                    <strong>{tweet['author_name']}</strong> @{tweet['author']}
                    <div class="tweet-text">{tweet['text']}</div>
                    <div class="tweet-metrics">
                        <span>💬 {tweet['replies']} replies</span>
                        <span>🔄 {tweet['retweets']} RTs</span>
                        <span>❤️ {tweet['likes']} likes</span>
                    </div>
                    <a href="{tweet_url}" target="_blank" style="color: #1d9bf0; text-decoration: none;">🔗 View on Twitter</a>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.warning("❌ No tweets found at all. This means the Twitter API search isn't working or your bearer token has issues.")
