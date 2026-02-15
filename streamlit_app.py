import streamlit as st
import tweepy
from anthropic import Anthropic
from datetime import datetime, timedelta
import os

# ========================================
# DEBUG MODE - Find out why we're missing tweets
# ========================================
TESTING_MODE = True
MAX_TWEETS = 100
HOURS_BACK = 168  # 7 days
# ========================================

st.set_page_config(page_title="Broncos Tweet Hunter - DEBUG", layout="wide", initial_sidebar_state="collapsed")

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
    .tweet-sample {
        background-color: #1a1a1a;
        border-left: 3px solid #1d9bf0;
        padding: 10px;
        margin: 8px 0;
        font-size: 13px;
    }
</style>
""", unsafe_allow_html=True)

os.environ["TWITTER_BEARER_TOKEN"] = st.secrets["TWITTER_BEARER_TOKEN"]
os.environ["ANTHROPIC_API_KEY"] = st.secrets["ANTHROPIC_API_KEY"]

client_twitter = tweepy.Client(bearer_token=os.environ["TWITTER_BEARER_TOKEN"], wait_on_rate_limit=True)

st.title("🏈 Broncos Tweet Hunter - DEBUG MODE")
st.caption("Let's find out why we're missing high-engagement tweets")

if st.button("🔍 DEBUG: Scan for Broncos Tweets", use_container_width=True):
    with st.spinner("Scanning Twitter..."):
        broncos_keywords = [
            "Denver Broncos",
            "Bo Nix",
            "Surtain",
            "Courtland Sutton",
            "Sean Payton",
            "Vance Joseph"
        ]
        
        # SIMPLEST POSSIBLE QUERY - NO FILTERS
        query = " OR ".join([f'"{k}"' for k in broncos_keywords])
        query += " lang:en"  # ONLY language filter
        
        start_time = datetime.utcnow() - timedelta(hours=HOURS_BACK)
        
        st.markdown("### 🔍 QUERY BEING SENT TO TWITTER:")
        st.code(query)
        
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
                st.error("❌ Twitter returned ZERO tweets!")
                st.stop()
            
            users = {user.id: user for user in tweets.includes['users']}
            
            st.success(f"✅ Twitter returned {len(tweets.data)} tweets")
            
            # ANALYZE ALL TWEETS
            all_tweets_data = []
            for tweet in tweets.data:
                metrics = tweet.public_metrics
                user = users.get(tweet.author_id)
                
                # Check what would filter it out
                is_rt = tweet.text.startswith('RT @')
                starts_with_at = tweet.text.startswith('@')
                has_ref_tweets = hasattr(tweet, 'referenced_tweets') and tweet.referenced_tweets
                ref_types = []
                if has_ref_tweets:
                    ref_types = [ref.type for ref in tweet.referenced_tweets]
                
                all_tweets_data.append({
                    'text': tweet.text[:100],
                    'author': user.username if user else 'Unknown',
                    'replies': metrics['reply_count'],
                    'likes': metrics['like_count'],
                    'retweets': metrics['retweet_count'],
                    'is_rt': is_rt,
                    'starts_at': starts_with_at,
                    'ref_types': ref_types
                })
            
            # Sort by engagement
            all_tweets_data.sort(key=lambda x: (x['replies'] * 100000) + (x['retweets'] * 100) + x['likes'], reverse=True)
            
            # SHOW TOP 20 TWEETS WITH THEIR FILTER STATUS
            st.markdown("### 📊 TOP 20 TWEETS BY ENGAGEMENT:")
            st.markdown("*This shows what Twitter gave us and why each tweet might be filtered out*")
            
            for i, t in enumerate(all_tweets_data[:20], 1):
                filter_reasons = []
                if t['is_rt']:
                    filter_reasons.append("❌ Starts with 'RT @'")
                if t['starts_at']:
                    filter_reasons.append("❌ Starts with '@'")
                if 'replied_to' in t['ref_types']:
                    filter_reasons.append("❌ Is a reply")
                if 'retweeted' in t['ref_types']:
                    filter_reasons.append("❌ Is a retweet")
                if 'quoted' in t['ref_types']:
                    filter_reasons.append("✅ Is a quote tweet (OK)")
                
                if not filter_reasons:
                    filter_reasons.append("✅ WOULD PASS ALL FILTERS")
                
                engagement_emoji = "🔥" if t['replies'] >= 10 or t['likes'] >= 50 or t['retweets'] >= 10 else "❄️"
                
                st.markdown(f"""
                <div class="tweet-sample">
                <strong>#{i} {engagement_emoji} @{t['author']}</strong><br>
                💬 {t['replies']} replies | ❤️ {t['likes']} likes | 🔄 {t['retweets']} retweets<br>
                <em>"{t['text']}..."</em><br>
                <strong>Filter Status:</strong> {', '.join(filter_reasons)}
                </div>
                """, unsafe_allow_html=True)
            
            # SUMMARY STATISTICS
            total_tweets = len(all_tweets_data)
            high_engagement = len([t for t in all_tweets_data if t['replies'] >= 10 or t['likes'] >= 50 or t['retweets'] >= 10])
            would_be_filtered_rt = len([t for t in all_tweets_data if t['is_rt']])
            would_be_filtered_at = len([t for t in all_tweets_data if t['starts_at'] and not t['is_rt']])
            would_be_filtered_reply = len([t for t in all_tweets_data if 'replied_to' in t['ref_types']])
            
            st.markdown("### 📈 SUMMARY:")
            st.markdown(f"""
            <div class="debug-box">
            <strong>TOTAL TWEETS FROM TWITTER:</strong> {total_tweets}<br>
            <strong>High engagement (10+ replies OR 50+ likes OR 10+ retweets):</strong> {high_engagement}<br>
            <br>
            <strong>WOULD BE FILTERED OUT BY:</strong><br>
            - Starts with "RT @": {would_be_filtered_rt}<br>
            - Starts with "@" (not RT): {would_be_filtered_at}<br>
            - Has 'replied_to' reference: {would_be_filtered_reply}<br>
            <br>
            <strong>CONCLUSION:</strong> Look at the top 20 tweets above. Are high-engagement tweets being filtered incorrectly?
            </div>
            """, unsafe_allow_html=True)
            
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
