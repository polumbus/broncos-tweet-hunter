import streamlit as st
import os
import tweepy
from anthropic import Anthropic
from datetime import datetime, timedelta

st.set_page_config(page_title="Broncos Tweet Hunter", layout="wide")

# Read from Streamlit secrets and set as environment variables
os.environ["TWITTER_BEARER_TOKEN"] = st.secrets["TWITTER_BEARER_TOKEN"]
os.environ["ANTHROPIC_API_KEY"] = st.secrets["ANTHROPIC_API_KEY"]

# Initialize clients
client = Anthropic()
client_twitter = tweepy.Client(bearer_token=os.environ["TWITTER_BEARER_TOKEN"], wait_on_rate_limit=True)

st.title("🏈 BRONCOS TWEET HUNTER")
st.write("Find viral Broncos & Nuggets content from the last 48 hours")

# Sidebar
st.sidebar.header("⚙️ Settings")
search_mode = st.sidebar.radio("Search for:", ["Broncos Only (85%)", "Broncos + Nuggets (85/15)"])

def search_viral_tweets(keywords, max_results=50):
    """Search Twitter for viral tweets"""
    query = " OR ".join([f'"{k}"' for k in keywords]) + " -is:retweet lang:en"
    start_time = datetime.utcnow() - timedelta(hours=48)
    
    try:
        tweets = client_twitter.search_recent_tweets(
            query=query,
            max_results=max_results,
            start_time=start_time,
            tweet_fields=['public_metrics', 'created_at', 'author_id'],
            expansions=['author_id'],
            user_fields=['username', 'name']
        )
        
        if not tweets.data:
            return []
        
        # Get user info
        users = {user.id: user for user in tweets.includes['users']}
        
        # Score tweets (replies weighted 3x for controversy)
        scored_tweets = []
        for tweet in tweets.data:
            metrics = tweet.public_metrics
            engagement_score = (metrics['reply_count'] * 3) + (metrics['retweet_count'] * 2) + metrics['like_count']
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
                'url': f"https://twitter.com/{user.username if user else 'twitter'}/status/{tweet.id}"
            })
        
        # Sort by engagement score
        scored_tweets.sort(key=lambda x: x['engagement_score'], reverse=True)
        return scored_tweets[:10]
    
    except Exception as e:
        st.error(f"Twitter API Error: {str(e)}")
        return []

def rewrite_tweet(original_text, style="default"):
    """Rewrite tweet in Tyler's voice"""
    
    voice_profile = """You are Tyler, a Denver Broncos analyst and former player. Your voice:
- Insider perspective (you know team dynamics from playing)
- Conversational and smart (not generic hot takes)
- Mix analysis with personality
- Ask rhetorical questions to engage
- Short, punchy paragraphs
- Willing to have spicy takes
- Examples: 'Bo's presser was a DIRECT RESPONSE to Sean', 'It's Walmart money!'"""
    
    style_prompts = {
        "default": "Rewrite this tweet in Tyler's voice. Keep it under 280 characters.",
        "analytical": "Rewrite as deep analysis from Tyler (former player). Break down strategy/implications. Under 280 chars.",
        "controversial": "Rewrite as a spicy hot take from Tyler. Make it debate-worthy. Under 280 chars.",
        "personal": "Rewrite from Tyler's experience as a former player. Reference locker room insights. Under 280 chars."
    }
    
    prompt = f"""{voice_profile}

Original tweet: "{original_text}"

{style_prompts.get(style, style_prompts['default'])}"""
    
    try:
        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text
    except Exception as e:
        return f"Error: {str(e)}"

# Main interface
if st.button("🔍 SCAN FOR VIRAL TWEETS (LAST 48 HOURS)", use_container_width=True):
    with st.spinner("🏈 Searching Twitter for viral Broncos content..."):
        
        if search_mode == "Broncos Only (85%)":
            keywords = ["Denver Broncos", "Sean Payton", "Bo Nix", "#Broncos"]
        else:
            # 85% Broncos, 15% Nuggets
            broncos_tweets = search_viral_tweets(["Denver Broncos", "Sean Payton", "Bo Nix"], max_results=40)
            nuggets_tweets = search_viral_tweets(["Denver Nuggets", "Nikola Jokic"], max_results=7)
            tweets = broncos_tweets + nuggets_tweets
            tweets.sort(key=lambda x: x['engagement_score'], reverse=True)
            tweets = tweets[:10]
        
        if search_mode == "Broncos Only (85%)":
            tweets = search_viral_tweets(keywords)
        
        if tweets:
            st.success(f"✅ Found {len(tweets)} viral tweets!")
            
            for i, tweet in enumerate(tweets, 1):
                st.markdown("---")
                
                # Tweet header
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.markdown(f"### #{i} - @{tweet['author']} ({tweet['author_name']})")
                with col2:
                    team_badge = "🏈 BRONCOS" if i <= 9 or search_mode == "Broncos Only (85%)" else "🏀 NUGGETS"
                    st.markdown(f"**{team_badge}**")
                
                # Engagement metrics
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("❤️ Likes", f"{tweet['likes']:,}")
                col2.metric("🔄 Retweets", f"{tweet['retweets']:,}")
                col3.metric("💬 Replies", f"{tweet['replies']:,}")
                col4.metric("🔥 Score", f"{tweet['engagement_score']:,}")
                
                # Original tweet
                st.markdown("#### 📱 Original Tweet")
                st.info(tweet['text'])
                st.markdown(f"[View on Twitter]({tweet['url']}) • Posted {tweet['created_at'].strftime('%b %d, %Y at %I:%M %p UTC')}")
                
                # AI Rewrites
                st.markdown("#### 🤖 AI Rewrites in Your Voice")
                
                tab1, tab2, tab3, tab4 = st.tabs(["✍️ Default", "📊 Analytical", "🔥 Controversial", "👤 Personal"])
                
                with tab1:
                    if st.button(f"Generate Default Rewrite", key=f"default_{tweet['id']}"):
                        with st.spinner("Rewriting..."):
                            rewrite = rewrite_tweet(tweet['text'], "default")
                            st.success(rewrite)
                            st.code(rewrite, language=None)
                
                with tab2:
                    if st.button(f"Generate Analytical Rewrite", key=f"analytical_{tweet['id']}"):
                        with st.spinner("Rewriting..."):
                            rewrite = rewrite_tweet(tweet['text'], "analytical")
                            st.success(rewrite)
                            st.code(rewrite, language=None)
                
                with tab3:
                    if st.button(f"Generate Controversial Rewrite", key=f"controversial_{tweet['id']}"):
                        with st.spinner("Rewriting..."):
                            rewrite = rewrite_tweet(tweet['text'], "controversial")
                            st.success(rewrite)
                            st.code(rewrite, language=None)
                
                with tab4:
                    if st.button(f"Generate Personal Rewrite", key=f"personal_{tweet['id']}"):
                        with st.spinner("Rewriting..."):
                            rewrite = rewrite_tweet(tweet['text'], "personal")
                            st.success(rewrite)
                            st.code(rewrite, language=None)
        else:
            st.warning("No tweets found. Try again in a few moments!")

# Footer
st.markdown("---")
st.caption("💰 **Cost Tracking:** Twitter API (Free tier) | Claude API (~$0.50 per scan)")
