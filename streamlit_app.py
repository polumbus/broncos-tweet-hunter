import streamlit as st
import tweepy
from anthropic import Anthropic
from datetime import datetime, timedelta
import os
import json
from pathlib import Path
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote_plus
import html as html_lib
import random

# ========================================
# PRODUCTION MODE
# ========================================
TESTING_MODE = False
MAX_TWEETS = 100
HOURS_BACK = 36
SCAN_HISTORY_FILE = Path("scan_history.json")
TYLER_USERNAME = "tyler_polumbus"  # For tweet performance tracker

# High-signal accounts — beat writers, official, fan accounts with real engagement
INSIDER_ACCOUNTS = [
    # Official team
    "Broncos", "nuggets",
    # Broncos beat writers / media
    "MaseDenver", "NickKosmider", "ZacStevensDNVR", "AricDiLalla",
    "RyanKoenigsberg", "BenjaminAllbright", "CecilLammey", "TroyRenck",
    "MikeKlis", "DMac_Denver",
    # Broncos fan / analysis
    "ThatsGoodSports", "MileHighReport", "BSNBroncos", "InTheNixOfTime",
    # Nuggets beat writers / media
    "msaborern", "Harrison_Wind", "AdamMaresSBN", "BSNNuggets",
    # Denver sports general
    "AltitudeSR",
]
# ========================================

st.set_page_config(page_title="Tweet Hunter", layout="wide", initial_sidebar_state="collapsed")

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

st.title("🏈 Tweet Hunter")
st.caption(f"Find the most controversial Denver Broncos & Nuggets debates from the last {HOURS_BACK} hours")

# Initialize session state for tracking shown tweets
if 'shown_tweet_ids' not in st.session_state:
    st.session_state.shown_tweet_ids = set()

if 'current_broncos_tweets' not in st.session_state:
    st.session_state.current_broncos_tweets = []

if 'current_nuggets_tweets' not in st.session_state:
    st.session_state.current_nuggets_tweets = []

if 'trending_topics' not in st.session_state:
    st.session_state.trending_topics = []

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

def is_spam_tweet(tweet, metrics, is_recency=False):
    """Filter out spam tweets - relaxed thresholds for recency searches"""
    total = metrics['reply_count'] + metrics['like_count'] + metrics['retweet_count']
    
    # Allow high-engagement @-replies (debate threads)
    if tweet.text.startswith('@') and total < (10 if is_recency else 15):
        return True
    
    # Block excessive mass mentions
    if tweet.text.count('@') >= 15:
        return True
    
    # Minimum engagement threshold - lower for fresh tweets still building momentum
    if total < (4 if is_recency else 8):
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

def is_wrong_nuggets(tweet):
    """Filter out non-Denver Nuggets tweets (chicken nuggets, trading nuggets, etc.)"""
    text_lower = tweet.text.lower()
    
    # Only check tweets that mention nuggets-related keywords
    if not any(kw in text_lower for kw in ["nuggets", "#nuggets"]):
        return False  # Not a nuggets tweet, let other filters handle it
    
    # If it has clear NBA/Denver context, it's fine
    nba_context = [
        "denver", "nba", "jokic", "joker", "murray", "aaron gordon",
        "michael porter", "mpj", "malone", "coach", "playoff", "playoffs",
        "championship", "western conference", "ball arena", "altitude",
        "basketball", "game", "season", "roster", "draft", "trade",
        "free agent", "mvp", "all-star", "starting lineup", "bench",
        "points", "assists", "rebounds", "triple double", "load management"
    ]
    has_nba_context = any(kw in text_lower for kw in nba_context)
    
    if has_nba_context:
        return False  # Legit Nuggets tweet
    
    # Block food, trading, general non-basketball "nuggets"
    spam_context = [
        "chicken", "eating", "food", "recipe", "cook", "fry", "fried",
        "mcdonalds", "burger", "sauce", "meal", "nugget meal",
        "trading", "traders", "forex", "crypto", "stock", "candle",
        "chart", "profit", "motivation", "daily motivation",
        "ford", "ev ", "electric vehicle", "pickup", "truck", "platform",
        "gold nugget", "nuggets of wisdom", "information nuggets",
        "dog", "cat", "pet", "puppy", "pidgey", "bird"
    ]
    has_spam_context = any(kw in text_lower for kw in spam_context)
    
    if has_spam_context:
        return True  # Definitely not Denver Nuggets
    
    # If tweet ONLY says "nuggets" with no NBA context, likely not Denver
    # But if it has #Nuggets (hashtag), give benefit of the doubt
    if "#nuggets" in text_lower:
        return False
    
    # Generic "nuggets" with no context either way — block it
    return True

def search_viral_tweets(keywords, hours=36, debate_mode=False, sort_order='relevancy', start_time_override=None):
    """Search for viral tweets — supports sort mode and time window overrides"""
    base_query = " OR ".join(keywords)
    query = f"({base_query}) -is:retweet lang:en"
    
    if debate_mode:
        controversy = [
            "fire", "trade", "overrated", "bust", "sucks", "trash", "worst",
            "choke", "flop", "out", "hot take", "debate", "controversial",
            "payton out", "nix sucks", "jokic flop", "worst trade", "mistake",
            "regret", "washed", "benched", "russ cooked"
        ]
        debate_part = " OR ".join(controversy)
        query = f"({query}) ({debate_part})"
    
    start_time = start_time_override or (datetime.utcnow() - timedelta(hours=hours))
    
    try:
        tweets = client_twitter.search_recent_tweets(
            query=query,
            max_results=MAX_TWEETS,
            start_time=start_time,
            sort_order=sort_order,
            tweet_fields=['public_metrics', 'created_at', 'referenced_tweets', 'attachments'],
            expansions=['author_id', 'attachments.media_keys'],
            user_fields=['username', 'name'],
            media_fields=['url', 'preview_image_url', 'type']
        )
        return tweets
    except Exception as e:
        print(f"Search error: {str(e)}")
        return None

def search_insider_tweets(accounts, hours=24):
    """Search for tweets FROM high-signal insider accounts"""
    # Twitter query length limit — use first 10 accounts
    sample = random.sample(accounts, min(10, len(accounts)))
    from_clause = " OR ".join([f"from:{acct}" for acct in sample])
    query = f"({from_clause}) -is:retweet lang:en"
    
    start_time = datetime.utcnow() - timedelta(hours=hours)
    
    try:
        tweets = client_twitter.search_recent_tweets(
            query=query,
            max_results=50,
            start_time=start_time,
            sort_order='relevancy',
            tweet_fields=['public_metrics', 'created_at', 'referenced_tweets', 'attachments'],
            expansions=['author_id', 'attachments.media_keys'],
            user_fields=['username', 'name'],
            media_fields=['url', 'preview_image_url', 'type']
        )
        return tweets
    except Exception as e:
        print(f"Insider search error: {str(e)}")
        return None

def get_subject_penalty_from_history():
    """Penalize subjects that dominated previous scans (cross-scan balancing)"""
    try:
        history = []
        if SCAN_HISTORY_FILE.exists():
            all_history = json.loads(SCAN_HISTORY_FILE.read_text())
            # Look at last 3 scans only
            history = all_history[-3:] if len(all_history) >= 3 else all_history
        
        subject_appearances = defaultdict(int)
        for entry in history:
            topics = entry.get("topics", {})
            for subject in topics:
                subject_appearances[subject] += 1
        
        # Subjects that appeared in all recent scans get penalized
        penalty = {}
        for subject, count in subject_appearances.items():
            if count >= 3:
                penalty[subject] = 3  # Heavy penalty — appeared in all 3 recent scans
            elif count >= 2:
                penalty[subject] = 1  # Light penalty
        
        return penalty
    except Exception:
        return {}

def get_top_debate_tweets(exclude_ids=None):
    """Main processing: 4 core + 2 fresh + 1 insider + scoring + diversity"""
    
    if exclude_ids is None:
        exclude_ids = set()
    
    # Fresh window: random 12-18h for variety between scans
    fresh_hours = random.randint(12, 18)
    fresh_start = datetime.utcnow() - timedelta(hours=fresh_hours)
    
    # Run 7 searches IN PARALLEL
    # Core 4: UNCHANGED from baseline (relevancy, full 36h window)
    # Fresh 2: ADDED (recency, recent 12-18h slice)
    # Insider 1: ADDED (beat writers + team accounts)
    with ThreadPoolExecutor(max_workers=7) as executor:
        futures = {
            # --- CORE 4: identical to baseline ---
            'broncos_normal': executor.submit(search_viral_tweets, BRONCOS_KEYWORDS, HOURS_BACK, False),
            'broncos_debate': executor.submit(search_viral_tweets, BRONCOS_KEYWORDS, HOURS_BACK, True),
            'nuggets_normal': executor.submit(search_viral_tweets, NUGGETS_KEYWORDS, HOURS_BACK, False),
            'nuggets_debate': executor.submit(search_viral_tweets, NUGGETS_KEYWORDS, HOURS_BACK, True),
            # --- FRESH 2: recency injection ---
            'broncos_fresh': executor.submit(search_viral_tweets, BRONCOS_KEYWORDS, fresh_hours, False, 'recency', fresh_start),
            'nuggets_fresh': executor.submit(search_viral_tweets, NUGGETS_KEYWORDS, fresh_hours, False, 'recency', fresh_start),
            # --- INSIDER 1: beat writers + team accounts ---
            'insiders': executor.submit(search_insider_tweets, INSIDER_ACCOUNTS, 24),
        }
        results = {name: f.result() for name, f in futures.items()}
    
    # Track which results get relaxed filters (fresh + insider tweets)
    recency_sources = {'broncos_fresh', 'nuggets_fresh', 'insiders'}
    
    # Get subject penalty from scan history (cross-scan balancing)
    subject_penalty = get_subject_penalty_from_history()
    
    all_tweets = []
    seen_ids = set()
    all_users = {}
    all_media = {}
    
    # Debug counters
    stats = {
        'total_raw': 0,
        'total_raw_core': 0,
        'total_raw_fresh': 0,
        'total_raw_insider': 0,
        'filtered_spam': 0,
        'filtered_not_original': 0,
        'filtered_rugby': 0,
        'filtered_duplicate': 0,
        'kept': 0,
        'kept_fresh': 0,
        'fresh_window': f"{fresh_hours}h",
        'subjects_penalized': list(subject_penalty.keys()) if subject_penalty else []
    }
    
    # Process all 6 search results
    for source_name, tweets_obj in results.items():
        if not tweets_obj or not tweets_obj.data:
            continue
        
        is_recency = source_name in recency_sources
        
        stats['total_raw'] += len(tweets_obj.data)
        if source_name == 'insiders':
            stats['total_raw_insider'] += len(tweets_obj.data)
        elif is_recency:
            stats['total_raw_fresh'] += len(tweets_obj.data)
        else:
            stats['total_raw_core'] += len(tweets_obj.data)
        
        # Collect users
        if hasattr(tweets_obj, 'includes') and tweets_obj.includes and 'users' in tweets_obj.includes:
            for user in tweets_obj.includes['users']:
                all_users[user.id] = user
        
        # Collect media
        if hasattr(tweets_obj, 'includes') and tweets_obj.includes and 'media' in tweets_obj.includes:
            for media in tweets_obj.includes['media']:
                all_media[media.media_key] = media
        
        # Process tweets
        for tweet in tweets_obj.data:
            if tweet.id in seen_ids:
                stats['filtered_duplicate'] += 1
                continue
            
            if tweet.id in exclude_ids:
                stats['filtered_duplicate'] += 1
                continue
            
            metrics = tweet.public_metrics
            
            # Use relaxed spam thresholds for recency tweets (still building engagement)
            if is_spam_tweet(tweet, metrics, is_recency=is_recency):
                stats['filtered_spam'] += 1
                continue
            
            if not is_original_tweet(tweet):
                stats['filtered_not_original'] += 1
                continue
            
            if is_wrong_broncos_team(tweet):
                stats['filtered_rugby'] += 1
                continue
            
            if is_wrong_nuggets(tweet):
                stats['filtered_spam'] += 1
                continue
            
            stats['kept'] += 1
            
            # Calculate debate score
            score = calculate_debate_score(metrics, tweet.text)
            priority_info = determine_priority(tweet.text)
            subjects = extract_subjects(tweet.text)
            
            user = all_users.get(tweet.author_id)
            
            # Freshness bonus — tweets < 6h old get a score bump to compete with older viral tweets
            is_fresh = False
            age_hours = 999
            if tweet.created_at:
                try:
                    age = datetime.utcnow() - tweet.created_at.replace(tzinfo=None)
                    age_hours = age.total_seconds() / 3600
                    if age_hours < 6:
                        score += 100000  # Fresh tweet bonus
                        is_fresh = True
                    elif age_hours < 12:
                        score += 50000   # Moderately fresh bonus
                        is_fresh = True
                except:
                    pass
            
            if is_fresh:
                stats['kept_fresh'] += 1
            
            # Velocity boost — fresh tweets with rising replies are the #1 target
            if age_hours < 8 and metrics['reply_count'] > 3:
                score += metrics['reply_count'] * 20000  # Rising debate signal
            
            # Cross-scan subject penalty — demote subjects that dominated recent scans
            for subj in subjects:
                if subj in subject_penalty:
                    score -= subject_penalty[subj] * 50000  # Gentle demotion
            
            # Attach media
            tweet_media = []
            if hasattr(tweet, 'attachments') and tweet.attachments and 'media_keys' in tweet.attachments:
                for mk in tweet.attachments['media_keys']:
                    if mk in all_media:
                        tweet_media.append(all_media[mk])
            
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
                'subjects': subjects,
                'media': tweet_media,
                'is_fresh': is_fresh,
                'age_hours': round(age_hours, 1)
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
        
        is_broncos = any(kw in text_lower for kw in broncos_keywords_lower)
        is_nuggets = any(kw in text_lower for kw in nuggets_keywords_lower)
        
        if is_broncos and len(final_broncos) < 10:
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
        
        elif is_nuggets and len(final_nuggets) < 5:
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
                if subject_count_broncos[subj] >= 3:
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
                if subject_count_nuggets[subj] >= 3:
                    can_add = False
                    break
            if can_add:
                final_nuggets.append(tweet)
                for subj in tweet['subjects']:
                    subject_count_nuggets[subj] += 1
    
    # VOLUME FALLBACK: If still short after diversity relaxation,
    # relax even further (max 5 per subject) from backup pool
    if len(final_broncos) < 6 and broncos_backup:
        for tweet in broncos_backup:
            if len(final_broncos) >= 10:
                break
            if tweet not in final_broncos:
                can_add = True
                for subj in tweet['subjects']:
                    if subject_count_broncos[subj] >= 5:
                        can_add = False
                        break
                if can_add:
                    final_broncos.append(tweet)
                    for subj in tweet['subjects']:
                        subject_count_broncos[subj] += 1
    
    if len(final_nuggets) < 3 and nuggets_backup:
        for tweet in nuggets_backup:
            if len(final_nuggets) >= 5:
                break
            if tweet not in final_nuggets:
                can_add = True
                for subj in tweet['subjects']:
                    if subject_count_nuggets[subj] >= 5:
                        can_add = False
                        break
                if can_add:
                    final_nuggets.append(tweet)
                    for subj in tweet['subjects']:
                        subject_count_nuggets[subj] += 1
    
    # LAST RESORT: If still under 6 Broncos, do one extra relevancy search
    if len(final_broncos) < 6:
        try:
            extra = search_viral_tweets(BRONCOS_KEYWORDS, HOURS_BACK, True)
            if extra and extra.data:
                extra_users = {}
                if hasattr(extra, 'includes') and extra.includes and 'users' in extra.includes:
                    for u in extra.includes['users']:
                        extra_users[u.id] = u
                for tweet in extra.data:
                    if len(final_broncos) >= 10:
                        break
                    if tweet.id in seen_ids or tweet.id in exclude_ids:
                        continue
                    m = tweet.public_metrics
                    if is_spam_tweet(tweet, m):
                        continue
                    if not is_original_tweet(tweet):
                        continue
                    if is_wrong_broncos_team(tweet):
                        continue
                    eu = extra_users.get(tweet.author_id)
                    final_broncos.append({
                        'id': tweet.id,
                        'text': tweet.text,
                        'author': eu.username if eu else 'Unknown',
                        'author_name': eu.name if eu else 'Unknown',
                        'created_at': tweet.created_at,
                        'likes': m['like_count'],
                        'retweets': m['retweet_count'],
                        'replies': m['reply_count'],
                        'debate_score': calculate_debate_score(m, tweet.text),
                        'priority': determine_priority(tweet.text),
                        'subjects': extract_subjects(tweet.text),
                        'media': [],
                        'is_fresh': False,
                        'age_hours': 999
                    })
        except Exception as e:
            print(f"Volume fallback error: {e}")
    
    return final_broncos, final_nuggets, stats

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
        
        # Freshness badge for tweets < 12h old
        if tweet.get('is_fresh'):
            age = tweet.get('age_hours', 0)
            if age < 1:
                fresh_label = "🆕 <1h old"
            else:
                fresh_label = f"🆕 {age:.0f}h old"
            header_html += f'<span style="background-color: #00ba7c; color: white; padding: 3px 8px; border-radius: 10px; font-size: 10px; font-weight: bold; margin-left: 6px;">{fresh_label}</span>'
        
        header_html += f'''
                <br>
                <strong style="color: #e7e9ea;">{tweet['author_name']}</strong> 
                <span style="color: #71767b;">@{tweet['author']}</span>
            </div>
        '''
        
        st.markdown(header_html, unsafe_allow_html=True)
        
        st.markdown(f'<div style="font-size: 15px; line-height: 20px; color: #e7e9ea; margin-bottom: 12px;">{tweet["text"]}</div>', unsafe_allow_html=True)
        
        # Use pre-fetched media (no extra API calls!)
        media = tweet.get('media', [])
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
        metrics_html = f'<div style="display: flex; gap: 20px; color: #71767b; font-size: 13px; margin: 12px 0;"><span class="{metric_style}">💬 {tweet["replies"]} replies</span><span class="{metric_style}">🔄 {tweet["retweets"]} RTs</span><span class="{metric_style}">❤️ {tweet["likes"]}</span></div>'
        st.markdown(metrics_html, unsafe_allow_html=True)
        
        st.markdown(f'<a href="{tweet_url}" target="_blank" style="color: #1d9bf0; text-decoration: none;">🔗 View on Twitter →</a>', unsafe_allow_html=True)

def generate_rewrites(original_tweet):
    """Generate all 4 rewrite styles at once using Sonnet"""
    
    prompt = f'''You are writing tweets for Tyler Polumbus — former Denver Broncos offensive lineman (Super Bowl 50 champion), current radio host on Altitude 92.5, and host of the "Mount Polumbus Speaks" podcast. He played 8 NFL seasons as an undrafted free agent and started over 60 games.

Original tweet:
{original_tweet}

Generate 4 tweet versions:

1. DEFAULT: Clean, informative take in Tyler's sports radio voice. Confident but balanced.

2. CONTROVERSIAL: Spicy hot take designed to drive maximum engagement and debate. Bold, unapologetic.

3. RETWEET: This will be used as a quote tweet. Add genuine value on top of the original — provide insider context, a layer of analysis, a connection most fans wouldn't make, or a strong opinion that elevates the conversation. Do NOT just rephrase the original. Think "what does Tyler uniquely bring to this that nobody else can?"

4. REPLY: This will be posted as a direct reply to the original tweet. Either add meaningful context/layers that deepen the discussion, or give Tyler's clear opinion in response. Should feel like a natural reply in a conversation thread — direct, punchy, and engaging. Can agree, disagree, or build on the original.

All versions should be tweet-length (under 280 characters). Sound like a real person, not a bot.

Return ONLY valid JSON:
{{"Default": "...", "Controversial": "...", "Retweet": "...", "Reply": "..."}}'''
    
    try:
        message = client.messages.create(
            model="claude-sonnet-4-5-20250929",  # Back to reliable Sonnet
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        response_text = message.content[0].text
        clean_response = response_text.replace('```json', '').replace('```', '').strip()
        
        import json
        rewrites = json.loads(clean_response)
        return rewrites
    except Exception as e:
        return {
            "Default": f"ERROR: {str(e)}",
            "Controversial": f"ERROR: {str(e)}",
            "Retweet": f"ERROR: {str(e)}",
            "Reply": f"ERROR: {str(e)}"
        }

# ========================================
# 🧵 THREAD BUILDER
# ========================================

def generate_thread(original_tweet, subject=""):
    """Generate a 4-5 tweet thread building on the original tweet"""
    
    prompt = f'''You are Tyler Polumbus — former Denver Broncos offensive lineman (Super Bowl 50 champion, 8 NFL seasons, undrafted free agent who started 60+ games), current radio host on Altitude 92.5 (12-3 PM MST), and host of the "Mount Polumbus Speaks" podcast.

You just saw this viral tweet and want to build a full thread giving your take:

Original tweet:
{original_tweet}

Generate a 4-5 tweet thread (each tweet under 280 characters). The thread should:

- Tweet 1: Strong hook that grabs attention — a bold statement or question that makes people stop scrolling
- Tweet 2: Your unique insider take — something only a guy who played in the NFL and was in that locker room would know
- Tweet 3: Evidence or context — back up your take with a specific observation, comparison, or reference
- Tweet 4: The counter-argument acknowledged — show you've thought about the other side, then explain why you still hold your position
- Tweet 5 (optional): The closer — a punchy one-liner that's clip-worthy and shareable

Rules:
- Sound like a real person, not an AI. Use natural language.
- Be opinionated. Don't hedge everything.
- Each tweet should stand on its own but flow as a thread
- No hashtags in the thread (they look forced)
- Number the tweets 1/ 2/ 3/ etc.

Return valid JSON array of strings:
["1/ tweet one text...", "2/ tweet two text...", "3/ tweet three text...", "4/ tweet four text...", "5/ tweet five text..."]'''
    
    try:
        message = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}]
        )
        
        response_text = message.content[0].text
        clean_response = response_text.replace('```json', '').replace('```', '').strip()
        return json.loads(clean_response)
    except Exception as e:
        return [f"ERROR: {str(e)}"]

def display_thread(thread_tweets, key_prefix):
    """Display a generated thread with editable text areas and copy buttons"""
    thread_header = f'<div style="background-color: #16181c; border: 1px solid #1d9bf0; border-radius: 12px; padding: 16px; margin: 8px 0;"><div style="font-size: 13px; color: #1d9bf0; font-weight: bold; margin-bottom: 10px;">🧵 THREAD ({len(thread_tweets)} tweets)</div></div>'
    st.markdown(thread_header, unsafe_allow_html=True)
    
    for j, tweet_text in enumerate(thread_tweets):
        edited = st.text_area(
            f"Tweet {j+1}",
            value=tweet_text,
            height=80,
            key=f"{key_prefix}_thread_{j}",
            label_visibility="collapsed"
        )
        if st.button(f"📋 Copy Tweet {j+1}", key=f"{key_prefix}_copy_thread_{j}", use_container_width=True):
            st.code(edited, language=None)
    
    # Copy full thread
    full_thread_key = f"{key_prefix}_full_thread"
    if st.button("📋 Copy Full Thread", key=full_thread_key, use_container_width=True, type="primary"):
        all_tweets = []
        for j in range(len(thread_tweets)):
            widget_key = f"{key_prefix}_thread_{j}"
            all_tweets.append(st.session_state.get(widget_key, thread_tweets[j]))
        st.code("\n\n".join(all_tweets), language=None)

# ========================================
# 📋 SHOW PREP NOTES
# ========================================

def generate_show_prep(trending_topics):
    """Generate radio-ready show prep talking points from trending topics"""
    
    # Build topic summary
    topic_summary = ""
    for i, topic in enumerate(trending_topics[:6], 1):
        topic_summary += f"\n{i}. {topic['subject']} — {topic['total_replies']} replies, {topic['total_retweets']} RTs, {topic['total_likes']} likes ({topic['tweet_count']} tweets)"
        if topic.get('top_tweet'):
            topic_summary += f"\n   Hottest take: \"{topic['top_tweet']}\""
    
    prompt = f'''You are a show prep producer for Tyler Polumbus's radio show on Altitude 92.5 (12-3 PM MST). Tyler is a former Denver Broncos offensive lineman (Super Bowl 50 champion, 8 NFL seasons as an undrafted free agent, started 60+ games) who now hosts a daily sports radio show.

Here are today's trending topics from Denver sports Twitter:
{topic_summary}

Generate show prep notes Tyler can use on air TODAY. For each of the top 3-4 topics:

1. **TOPIC**: The subject
2. **OPEN WITH** (1 sentence): How Tyler should introduce this topic to listeners. Conversational, like you're talking to a friend at a bar.
3. **KEY FACTS** (2-3 bullets): The specific things Tyler needs to know — stats, quotes, context
4. **TYLER'S TAKE** (1-2 sentences): What Tyler's opinion should be, drawing on his playing experience
5. **CALLER QUESTION**: A question to throw to callers that will light up the phone lines
6. **TRANSITION**: One sentence to smoothly move to the next topic

Keep it punchy. Tyler reads this during commercial breaks. No fluff.

Return valid JSON array:
[
  {{
    "topic": "...",
    "open_with": "...",
    "key_facts": ["...", "...", "..."],
    "tylers_take": "...",
    "caller_question": "...",
    "transition": "..."
  }}
]'''
    
    try:
        message = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        response_text = message.content[0].text
        clean_response = response_text.replace('```json', '').replace('```', '').strip()
        return json.loads(clean_response)
    except Exception as e:
        return [{"topic": f"ERROR: {str(e)}", "open_with": "", "key_facts": [], "tylers_take": "", "caller_question": "", "transition": ""}]

# ========================================
# 📊 MY TWEET PERFORMANCE TRACKER
# ========================================

def get_my_tweet_performance(username=TYLER_USERNAME, count=20):
    """Fetch Tyler's recent tweets and their engagement metrics"""
    try:
        # Get user ID
        user = client_twitter.get_user(username=username, user_fields=['public_metrics'])
        if not user or not user.data:
            return None, None
        
        user_data = user.data
        user_metrics = user_data.public_metrics
        
        # Get recent tweets
        tweets = client_twitter.get_users_tweets(
            user_data.id,
            max_results=count,
            tweet_fields=['public_metrics', 'created_at', 'text'],
            exclude=['retweets']
        )
        
        if not tweets or not tweets.data:
            return user_metrics, []
        
        tweet_list = []
        for tweet in tweets.data:
            m = tweet.public_metrics
            total_engagement = m['reply_count'] + m['retweet_count'] + m['like_count']
            
            # Detect subjects
            subjects = extract_subjects(tweet.text)
            
            tweet_list.append({
                'id': tweet.id,
                'text': tweet.text,
                'created_at': tweet.created_at,
                'replies': m['reply_count'],
                'retweets': m['retweet_count'],
                'likes': m['like_count'],
                'impressions': m.get('impression_count', 0),
                'total_engagement': total_engagement,
                'subjects': subjects
            })
        
        # Sort by total engagement
        tweet_list.sort(key=lambda x: x['total_engagement'], reverse=True)
        
        return user_metrics, tweet_list
    except Exception as e:
        print(f"Tweet performance error: {e}")
        return None, None

# ========================================
# 🎯 REPLY TARGET FINDER
# ========================================

def find_reply_targets(min_followers=25000):
    """Find high-follower accounts tweeting about Broncos/Nuggets — prime reply opportunities"""
    
    # Search for Broncos and Nuggets tweets from larger accounts
    query_broncos = "(Denver Broncos OR Bo Nix OR Sean Payton OR #BroncosCountry) -is:retweet lang:en"
    query_nuggets = "(Denver Nuggets OR Jokic OR Nuggets NBA) -is:retweet lang:en"
    
    start_time = datetime.utcnow() - timedelta(hours=24)
    
    all_targets = []
    seen_ids = set()
    
    def search_targets(query):
        try:
            result = client_twitter.search_recent_tweets(
                query=query,
                max_results=100,
                start_time=start_time,
                sort_order='relevancy',
                tweet_fields=['public_metrics', 'created_at'],
                expansions=['author_id'],
                user_fields=['username', 'name', 'public_metrics', 'verified']
            )
            return result
        except Exception as e:
            print(f"Reply target search error: {e}")
            return None
    
    # Search both in parallel
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(search_targets, query_broncos),
            executor.submit(search_targets, query_nuggets)
        ]
        results = [f.result() for f in futures]
    
    for result in results:
        if not result or not result.data:
            continue
        
        # Build user map
        users = {}
        if hasattr(result, 'includes') and result.includes and 'users' in result.includes:
            for u in result.includes['users']:
                users[u.id] = u
        
        for tweet in result.data:
            if tweet.id in seen_ids:
                continue
            seen_ids.add(tweet.id)
            
            user = users.get(tweet.author_id)
            if not user or not hasattr(user, 'public_metrics'):
                continue
            
            followers = user.public_metrics.get('followers_count', 0)
            if followers < min_followers:
                continue
            
            # Skip Tyler's own tweets
            if user.username.lower() == TYLER_USERNAME.lower():
                continue
            
            m = tweet.public_metrics
            tweet_engagement = m['reply_count'] + m['retweet_count'] + m['like_count']
            
            # Opportunity score: high follower + high engagement = best reply target
            opportunity_score = (followers * 0.3) + (tweet_engagement * 100)
            
            all_targets.append({
                'id': tweet.id,
                'text': tweet.text,
                'author': user.username,
                'author_name': user.name,
                'followers': followers,
                'verified': getattr(user, 'verified', False),
                'replies': m['reply_count'],
                'retweets': m['retweet_count'],
                'likes': m['like_count'],
                'tweet_engagement': tweet_engagement,
                'opportunity_score': opportunity_score,
                'created_at': tweet.created_at
            })
    
    # Sort by opportunity score
    all_targets.sort(key=lambda x: x['opportunity_score'], reverse=True)
    
    return all_targets[:15]  # Top 15 targets

# ========================================
# SCAN HISTORY PERSISTENCE
# ========================================

def save_scan_to_history(broncos_tweets, nuggets_tweets):
    """Save scan results to persistent JSON for weekly rollup tracking"""
    history = load_scan_history(days=30)  # Keep 30 days
    
    # Build topic snapshot from this scan
    topic_data = defaultdict(lambda: {"tweet_count": 0, "total_replies": 0, "total_retweets": 0, "total_likes": 0, "sample_tweets": []})
    
    for tweet in broncos_tweets + nuggets_tweets:
        for subject in tweet['subjects']:
            td = topic_data[subject]
            td["tweet_count"] += 1
            td["total_replies"] += tweet['replies']
            td["total_retweets"] += tweet['retweets']
            td["total_likes"] += tweet['likes']
            if len(td["sample_tweets"]) < 2:  # Keep top 2 sample tweets per subject
                td["sample_tweets"].append(tweet['text'][:200])
    
    scan_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "broncos_count": len(broncos_tweets),
        "nuggets_count": len(nuggets_tweets),
        "topics": {k: dict(v) for k, v in topic_data.items()}
    }
    
    history.append(scan_entry)
    
    try:
        SCAN_HISTORY_FILE.write_text(json.dumps(history, indent=2, default=str))
    except Exception as e:
        print(f"Failed to save scan history: {e}")

def load_scan_history(days=7):
    """Load scan history, filtering to the last N days"""
    if not SCAN_HISTORY_FILE.exists():
        return []
    
    try:
        all_history = json.loads(SCAN_HISTORY_FILE.read_text())
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        return [entry for entry in all_history if entry.get("timestamp", "") >= cutoff]
    except Exception:
        return []

# ========================================
# TRENDING TOPICS (Current Scan)
# ========================================

# Map subject names to smart Twitter search queries
SUBJECT_SEARCH_QUERIES = {
    # Broncos Players
    "Bo Nix": "Bo Nix Broncos",
    "Patrick Surtain": "Patrick Surtain OR PS2 Broncos",
    "Courtland Sutton": "Courtland Sutton Broncos",
    "Javonte Williams": "Javonte Williams Broncos",
    "Russell Wilson": "Russell Wilson Broncos",
    "Riley Moss": "Riley Moss Broncos",
    "Troy Franklin": "Troy Franklin Broncos",
    # Broncos Coaches
    "Sean Payton": "Sean Payton Broncos",
    "Vance Joseph": "Vance Joseph Broncos",
    "Fire Payton": "fire Payton OR Payton out Broncos",
    # Broncos Topics
    "QB Discussion": "Broncos quarterback OR Broncos QB",
    "Defense": "Broncos defense OR Broncos defensive",
    "Offense": "Broncos offense OR Broncos offensive",
    "Draft": "Broncos draft OR Nuggets draft",
    "Playoffs": "Broncos playoffs OR Nuggets playoffs",
    "General Broncos": "Denver Broncos",
    # Nuggets Players
    "Nikola Jokic": "Jokic Nuggets",
    "Jamal Murray": "Jamal Murray Nuggets",
    "Aaron Gordon": "Aaron Gordon Nuggets",
    "Michael Porter Jr": "Michael Porter Jr OR MPJ Nuggets",
    # Nuggets Topics
    "MVP": "Jokic MVP OR Nuggets MVP",
    "Player Rest": "Nuggets rest OR load management Nuggets",
    "Championship": "Nuggets championship OR Nuggets title",
    "General Nuggets": "Denver Nuggets",
    # Cross-team
    "Trade Talk": "Broncos trade OR Nuggets trade",
    "AJ Brown": "AJ Brown Broncos",
    "Contract": "Broncos contract OR Nuggets contract",
    "Injury": "Broncos injury OR Nuggets injury",
}

def get_twitter_search_url(subject):
    """Build a Twitter search URL for a topic"""
    query = SUBJECT_SEARCH_QUERIES.get(subject, f"{subject} Broncos OR Nuggets")
    return f"https://twitter.com/search?q={quote_plus(query)}&src=typed_query&f=top"

def get_trending_topics(broncos_tweets, nuggets_tweets):
    """Aggregate current scan by subject — returns sorted list of topic dicts"""
    topic_agg = defaultdict(lambda: {
        "tweet_count": 0,
        "total_replies": 0,
        "total_retweets": 0,
        "total_likes": 0,
        "total_engagement": 0,
        "top_tweet": None,
        "top_tweet_score": 0
    })
    
    for tweet in broncos_tweets + nuggets_tweets:
        for subject in tweet['subjects']:
            ta = topic_agg[subject]
            ta["tweet_count"] += 1
            ta["total_replies"] += tweet['replies']
            ta["total_retweets"] += tweet['retweets']
            ta["total_likes"] += tweet['likes']
            engagement = tweet['replies'] + tweet['retweets'] + tweet['likes']
            ta["total_engagement"] += engagement
            if engagement > ta["top_tweet_score"]:
                ta["top_tweet_score"] = engagement
                ta["top_tweet"] = tweet['text'][:150]
    
    # Sort by total engagement
    sorted_topics = sorted(
        [{"subject": k, **v} for k, v in topic_agg.items()],
        key=lambda x: x["total_engagement"],
        reverse=True
    )
    
    return sorted_topics

# ========================================
# WEEKLY ROLLUP / PODCAST IDEAS
# ========================================

def get_weekly_topic_summary():
    """Aggregate 7 days of scan history into topic rankings"""
    history = load_scan_history(days=7)
    
    if not history:
        return [], 0
    
    weekly_agg = defaultdict(lambda: {
        "appearances": 0,  # How many scans this topic showed up in
        "total_tweets": 0,
        "total_replies": 0,
        "total_retweets": 0,
        "total_likes": 0,
        "total_engagement": 0,
        "sample_tweets": []
    })
    
    for scan in history:
        for subject, data in scan.get("topics", {}).items():
            wa = weekly_agg[subject]
            wa["appearances"] += 1
            wa["total_tweets"] += data.get("tweet_count", 0)
            wa["total_replies"] += data.get("total_replies", 0)
            wa["total_retweets"] += data.get("total_retweets", 0)
            wa["total_likes"] += data.get("total_likes", 0)
            wa["total_engagement"] += (
                data.get("total_replies", 0) + 
                data.get("total_retweets", 0) + 
                data.get("total_likes", 0)
            )
            for st_text in data.get("sample_tweets", []):
                if len(wa["sample_tweets"]) < 4:
                    wa["sample_tweets"].append(st_text)
    
    sorted_weekly = sorted(
        [{"subject": k, **v} for k, v in weekly_agg.items()],
        key=lambda x: x["total_engagement"],
        reverse=True
    )
    
    return sorted_weekly, len(history)

def generate_podcast_ideas(weekly_topics):
    """Use Claude to generate 3 podcast episode ideas from the week's hottest topics"""
    
    # Build context from top topics
    top_topics = weekly_topics[:8]  # Send top 8 topics for context
    topic_context = ""
    for i, topic in enumerate(top_topics, 1):
        topic_context += f"\n{i}. **{topic['subject']}** — {topic['total_tweets']} tweets, {topic['total_replies']} replies, {topic['total_retweets']} RTs, appeared in {topic['appearances']} scans"
        if topic['sample_tweets']:
            topic_context += f"\n   Sample takes: {' | '.join(topic['sample_tweets'][:2])}"
    
    prompt = f'''You are a podcast content strategist for Tyler Polumbus — former Denver Broncos offensive lineman (Super Bowl 50 champion), current radio host on Altitude 92.5 (12-3 PM MST), and host of the "Mount Polumbus Speaks" podcast. He played 8 NFL seasons as an undrafted free agent and started over 60 games.

Here are the hottest topics from Denver sports Twitter this week, ranked by total engagement:
{topic_context}

Generate exactly 3 podcast episode ideas based on what's driving the most debate. For each:

1. **EPISODE TITLE** — Catchy, clickable title
2. **THE HOOK** — The central debate or question that will pull listeners in (1-2 sentences)
3. **TYLER'S ANGLE** — What unique perspective can Tyler bring as a former player/insider that fans can't get elsewhere? (2-3 sentences)
4. **SEGMENT BREAKDOWN** — 3 segments for a 30-45 min episode (one line each)
5. **SPICY TAKE** — One bold, quotable opinion Tyler could lead with to drive social media clips

Prioritize topics with high reply counts (that means debate) and topics that appeared across multiple scans (sustained interest, not just a flash).

Return valid JSON array:
[
  {{
    "title": "...",
    "hook": "...",
    "tylers_angle": "...",
    "segments": ["...", "...", "..."],
    "spicy_take": "..."
  }}
]'''
    
    try:
        message = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        response_text = message.content[0].text
        clean_response = response_text.replace('```json', '').replace('```', '').strip()
        return json.loads(clean_response)
    except Exception as e:
        return [{"title": f"ERROR: {str(e)}", "hook": "", "tylers_angle": "", "segments": [], "spicy_take": ""}]

# Button section
col1, col2, col3 = st.columns([3, 3, 1.5])

with col1:
    scan_button = st.button("🔍 Scan for Viral Debates", use_container_width=True, type="primary")

with col2:
    scan_new_button = st.button("🆕 Scan Again (Exclude Previously Shown)", use_container_width=True)

with col3:
    if st.button("🗑️ Clear All", use_container_width=True):
        st.session_state.shown_tweet_ids = set()
        st.session_state.current_broncos_tweets = []
        st.session_state.current_nuggets_tweets = []
        if 'filter_stats' in st.session_state:
            del st.session_state.filter_stats
        st.success("All cleared!")
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
        top_broncos, top_nuggets, filter_stats = get_top_debate_tweets(exclude_ids=exclude_ids)
        
        # Store in session state
        st.session_state.current_broncos_tweets = top_broncos
        st.session_state.current_nuggets_tweets = top_nuggets
        st.session_state.filter_stats = filter_stats  # Store stats for display
        
        # Track newly shown tweets
        for tweet in top_broncos + top_nuggets:
            st.session_state.shown_tweet_ids.add(tweet['id'])
        
        # Save scan to persistent history for weekly rollup
        save_scan_to_history(top_broncos, top_nuggets)
        
        # Calculate trending topics for this scan
        st.session_state.trending_topics = get_trending_topics(top_broncos, top_nuggets)

# Display tweets from session state (so they persist across reruns)
if st.session_state.current_broncos_tweets or st.session_state.current_nuggets_tweets:
    # Display scan results with debug info
    if scan_button or scan_new_button:
        st.success(f"✅ Scan complete! Found {len(top_broncos)} Broncos tweets and {len(top_nuggets)} Nuggets tweets")
        
        # Show filter stats if available
        if 'filter_stats' in st.session_state:
            stats = st.session_state.filter_stats
            with st.expander("📊 Scan Info — Search Breakdown + Filters"):
                st.write(f"**Raw tweets from API:** {stats['total_raw']} (core: {stats.get('total_raw_core', '?')} | fresh: {stats.get('total_raw_fresh', '?')} | insider: {stats.get('total_raw_insider', '?')})")
                st.write(f"**Fresh recency window:** last {stats.get('fresh_window', '?')}")
                if stats.get('subjects_penalized'):
                    st.write(f"**Subjects penalized (overexposed):** {', '.join(stats['subjects_penalized'])}")
                st.write(f"**Filtered out:**")
                st.write(f"- Spam: {stats['filtered_spam']}")
                st.write(f"- Not original: {stats['filtered_not_original']}")
                st.write(f"- Rugby/Brisbane Broncos: {stats['filtered_rugby']}")
                st.write(f"- Duplicates: {stats['filtered_duplicate']}")
                st.write(f"**Kept after filters:** {stats['kept']} ({stats.get('kept_fresh', 0)} fresh tweets)")
                st.write(f"**Final after diversity enforcement:** {len(top_broncos)} Broncos + {len(top_nuggets)} Nuggets")
    
    top_broncos = st.session_state.current_broncos_tweets
    top_nuggets = st.session_state.current_nuggets_tweets
    
    st.success(f"✅ Found {len(top_broncos)} Broncos + {len(top_nuggets)} Nuggets debates with max variety!")
    
    # ========================================
    # 📈 TRENDING TOPICS SECTION
    # ========================================
    if 'trending_topics' in st.session_state and st.session_state.trending_topics:
        trending = st.session_state.trending_topics
        
        with st.expander("📈 TRENDING TOPICS — What's Heating Up Right Now", expanded=True):
            # Show top topics as metric cards
            top_count = min(6, len(trending))
            cols = st.columns(min(3, top_count))
            
            for i in range(top_count):
                topic = trending[i]
                col_idx = i % 3
                with cols[col_idx]:
                    # Color-code by engagement level
                    if i == 0:
                        badge_color = "#f91880"  # Hot pink — #1
                        label = "🔥"
                    elif i <= 2:
                        badge_color = "#ff6b35"  # Orange — top 3
                        label = "⚡"
                    else:
                        badge_color = "#536471"  # Gray — others
                        label = "📊"
                    
                    search_url = get_twitter_search_url(topic["subject"])
                    
                    st.markdown(f'''
                        <a href="{search_url}" target="_blank" style="text-decoration: none;">
                        <div style="background-color: #16181c; border: 1px solid {badge_color}; border-radius: 12px; padding: 14px; margin-bottom: 10px; cursor: pointer; transition: background-color 0.2s;" onmouseover="this.style.backgroundColor='#1c2028'" onmouseout="this.style.backgroundColor='#16181c'">
                            <div style="font-size: 11px; color: {badge_color}; font-weight: bold; margin-bottom: 4px;">{label} #{i+1} TRENDING</div>
                            <div style="font-size: 16px; font-weight: bold; color: #e7e9ea; margin-bottom: 8px;">{topic["subject"]}</div>
                            <div style="display: flex; gap: 12px; font-size: 12px; color: #71767b;">
                                <span>💬 {topic["total_replies"]} replies</span>
                                <span>🔄 {topic["total_retweets"]} RTs</span>
                                <span>❤️ {topic["total_likes"]}</span>
                            </div>
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 6px;">
                                <span style="font-size: 11px; color: #536471;">{topic["tweet_count"]} tweets found</span>
                                <span style="font-size: 11px; color: #1d9bf0;">🔗 Search on 𝕏 →</span>
                            </div>
                        </div>
                        </a>
                    ''', unsafe_allow_html=True)
            
            # Engagement bar chart
            if len(trending) >= 3:
                st.markdown("**Engagement Breakdown:**")
                max_eng = trending[0]["total_engagement"] if trending[0]["total_engagement"] > 0 else 1
                for topic in trending[:8]:
                    bar_pct = int((topic["total_engagement"] / max_eng) * 100)
                    bar_color = "#1d9bf0" if "Broncos" not in topic["subject"] and "Nuggets" not in topic["subject"] else ("#fb4f14" if "Nix" in topic["subject"] or "Payton" in topic["subject"] or "Broncos" in topic["subject"] else "#ffd700")
                    bar_search_url = get_twitter_search_url(topic["subject"])
                    st.markdown(f'''
                        <div style="display: flex; align-items: center; margin-bottom: 4px;">
                            <a href="{bar_search_url}" target="_blank" style="width: 140px; font-size: 12px; color: #1d9bf0; flex-shrink: 0; text-decoration: none;" onmouseover="this.style.textDecoration='underline'" onmouseout="this.style.textDecoration='none'">{topic["subject"]}</a>
                            <div style="flex: 1; background-color: #2f3336; border-radius: 4px; height: 20px; overflow: hidden;">
                                <div style="width: {bar_pct}%; background-color: {bar_color}; height: 100%; border-radius: 4px; display: flex; align-items: center; padding-left: 8px;">
                                    <span style="font-size: 10px; color: white; font-weight: bold;">{topic["total_engagement"]}</span>
                                </div>
                            </div>
                        </div>
                    ''', unsafe_allow_html=True)
                st.markdown("")  # Spacer
            
            # Show Prep Notes button
            st.markdown("")
            if st.button("📋 Generate Show Prep Notes for Today", key="gen_show_prep", use_container_width=True, type="primary"):
                with st.spinner("🎙️ Building your show prep..."):
                    st.session_state.show_prep = generate_show_prep(trending)
            
            # Display show prep if generated
            if 'show_prep' in st.session_state:
                st.markdown("### 🎙️ TODAY'S SHOW PREP")
                st.caption("Read during commercial breaks. Each topic = ~5 min segment.")
                
                for sp_idx, segment in enumerate(st.session_state.show_prep):
                    topic_name = html_lib.escape(str(segment.get('topic', 'Unknown')))
                    open_with = html_lib.escape(str(segment.get('open_with', '')))
                    facts = [html_lib.escape(str(f)) for f in segment.get('key_facts', [])]
                    take = html_lib.escape(str(segment.get('tylers_take', '')))
                    caller_q = html_lib.escape(str(segment.get('caller_question', '')))
                    transition = html_lib.escape(str(segment.get('transition', '')))
                    
                    # Segment colors
                    seg_colors = ["#f91880", "#ff6b35", "#1d9bf0", "#00ba7c"]
                    seg_color = seg_colors[sp_idx % len(seg_colors)]
                    
                    facts_html = "".join(f'<div style="font-size: 13px; color: #c4cad0; margin-left: 8px; line-height: 1.4;">• {fact}</div>' for fact in facts)
                    
                    segment_html = f'''<div style="background-color: #16181c; border-left: 4px solid {seg_color}; border-radius: 8px; padding: 16px; margin: 12px 0;">
<div style="font-size: 11px; color: {seg_color}; font-weight: bold; margin-bottom: 4px;">SEGMENT {sp_idx + 1}</div>
<div style="font-size: 18px; font-weight: bold; color: #e7e9ea; margin-bottom: 10px;">{topic_name}</div>
<div style="margin-bottom: 10px;">
<div style="font-size: 11px; color: #1d9bf0; font-weight: bold;">🎤 OPEN WITH:</div>
<div style="font-size: 14px; color: #e7e9ea; line-height: 1.4;">&ldquo;{open_with}&rdquo;</div>
</div>
<div style="margin-bottom: 10px;">
<div style="font-size: 11px; color: #1d9bf0; font-weight: bold;">📌 KEY FACTS:</div>
{facts_html}
</div>
<div style="margin-bottom: 10px;">
<div style="font-size: 11px; color: #1d9bf0; font-weight: bold;">💪 TYLER'S TAKE:</div>
<div style="font-size: 14px; color: #e7e9ea; font-style: italic; line-height: 1.4;">&ldquo;{take}&rdquo;</div>
</div>
<div style="background-color: #1a2332; border-radius: 8px; padding: 10px; margin-bottom: 8px;">
<div style="font-size: 11px; color: #ff6b35; font-weight: bold;">📞 CALLER QUESTION:</div>
<div style="font-size: 14px; color: #e7e9ea;">&ldquo;{caller_q}&rdquo;</div>
</div>
<div style="font-size: 12px; color: #536471; font-style: italic;">➡️ Transition: {transition}</div>
</div>'''
                    
                    st.markdown(segment_html, unsafe_allow_html=True)
    
    st.markdown("---")
    
    if top_broncos:
        top_3_count = min(3, len(top_broncos))
        if top_3_count > 0:
            st.markdown("### ⭐ TOP 3 BRONCOS PICKS")
            
            # Generate all TOP 3 rewrites concurrently (parallel) - MUCH FASTER!
            top_3_tweets = top_broncos[:top_3_count]
            
            # Check if we need to generate rewrites
            need_generation = any(f"rewrites_b{i}" not in st.session_state for i in range(top_3_count))
            
            if need_generation:
                with st.spinner(f"🚀 Generating rewrites for TOP 3 in parallel..."):
                    def generate_for_index(idx):
                        return idx, generate_rewrites(top_3_tweets[idx]['text'])
                    
                    # Run all 3 API calls at the same time!
                    with ThreadPoolExecutor(max_workers=3) as executor:
                        futures = [executor.submit(generate_for_index, i) for i in range(top_3_count)]
                        for future in futures:
                            idx, rewrites = future.result()
                            st.session_state[f"rewrites_b{idx}"] = rewrites
            
            # Display all TOP 3 with their rewrites
            for i in range(top_3_count):
                tweet = top_3_tweets[i]
                display_tweet_card(tweet, is_top_pick=True, pick_number=i+1)
                
                # Show rewrites (already generated)
                rewrite_key = f"rewrites_b{i}"
                if rewrite_key in st.session_state:
                    rewrites = st.session_state[rewrite_key]
                    st.markdown("**✍️ Your Rewrites (edit before copying):**")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("**📝 Default:**")
                        edited_default = st.text_area(
                            "Default",
                            value=rewrites['Default'],
                            height=100,
                            key=f"edit_default_top{i}",
                            label_visibility="collapsed"
                        )
                        if st.button("📋 Copy Default", key=f"copy_default_top{i}", use_container_width=True):
                            st.code(edited_default, language=None)
                        
                        st.markdown("**🔄 Retweet (Quote Tweet):**")
                        edited_retweet = st.text_area(
                            "Retweet",
                            value=rewrites['Retweet'],
                            height=100,
                            key=f"edit_retweet_top{i}",
                            label_visibility="collapsed"
                        )
                        if st.button("📋 Copy Retweet", key=f"copy_retweet_top{i}", use_container_width=True):
                            st.code(edited_retweet, language=None)
                    
                    with col2:
                        st.markdown("**🔥 Controversial:**")
                        edited_controversial = st.text_area(
                            "Controversial",
                            value=rewrites['Controversial'],
                            height=100,
                            key=f"edit_controversial_top{i}",
                            label_visibility="collapsed"
                        )
                        if st.button("📋 Copy Controversial", key=f"copy_controversial_top{i}", use_container_width=True):
                            st.code(edited_controversial, language=None)
                        
                        st.markdown("**💬 Reply:**")
                        edited_reply = st.text_area(
                            "Reply",
                            value=rewrites['Reply'],
                            height=100,
                            key=f"edit_reply_top{i}",
                            label_visibility="collapsed"
                        )
                        if st.button("📋 Copy Reply", key=f"copy_reply_top{i}", use_container_width=True):
                            st.code(edited_reply, language=None)
                
                # Thread builder button
                thread_key = f"thread_top{i}"
                if thread_key not in st.session_state:
                    if st.button("🧵 Build Thread from This Tweet", key=f"gen_thread_top{i}", use_container_width=True):
                        with st.spinner("🧵 Building your thread..."):
                            st.session_state[thread_key] = generate_thread(tweet['text'])
                            st.rerun()
                
                if thread_key in st.session_state:
                    display_thread(st.session_state[thread_key], f"top{i}")
                
                st.markdown("---")
        
        if len(top_broncos) > 3:
            st.markdown("### 🏈 OTHER BRONCOS TWEETS")
            for idx, tweet in enumerate(top_broncos[3:], start=3):
                display_tweet_card(tweet, is_top_pick=False)
                
                # Button to generate rewrites on demand
                rewrite_key = f"rewrites_b{idx}"
                
                if rewrite_key not in st.session_state:
                    if st.button(f"✨ Generate Rewrites", key=f"gen_b{idx}", use_container_width=True):
                        with st.spinner("Generating rewrites..."):
                            st.session_state[rewrite_key] = generate_rewrites(tweet['text'])
                            st.rerun()
                
                # Show rewrites if generated
                if rewrite_key in st.session_state:
                    rewrites = st.session_state[rewrite_key]
                    st.markdown("**✍️ Your Rewrites (edit before copying):**")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("**📝 Default:**")
                        edited_default = st.text_area(
                            "Default",
                            value=rewrites['Default'],
                            height=100,
                            key=f"edit_default_b{idx}",
                            label_visibility="collapsed"
                        )
                        if st.button("📋 Copy Default", key=f"copy_default_b{idx}", use_container_width=True):
                            st.code(edited_default, language=None)
                        
                        st.markdown("**🔄 Retweet (Quote Tweet):**")
                        edited_retweet = st.text_area(
                            "Retweet",
                            value=rewrites['Retweet'],
                            height=100,
                            key=f"edit_retweet_b{idx}",
                            label_visibility="collapsed"
                        )
                        if st.button("📋 Copy Retweet", key=f"copy_retweet_b{idx}", use_container_width=True):
                            st.code(edited_retweet, language=None)
                    
                    with col2:
                        st.markdown("**🔥 Controversial:**")
                        edited_controversial = st.text_area(
                            "Controversial",
                            value=rewrites['Controversial'],
                            height=100,
                            key=f"edit_controversial_b{idx}",
                            label_visibility="collapsed"
                        )
                        if st.button("📋 Copy Controversial", key=f"copy_controversial_b{idx}", use_container_width=True):
                            st.code(edited_controversial, language=None)
                        
                        st.markdown("**💬 Reply:**")
                        edited_reply = st.text_area(
                            "Reply",
                            value=rewrites['Reply'],
                            height=100,
                            key=f"edit_reply_b{idx}",
                            label_visibility="collapsed"
                        )
                        if st.button("📋 Copy Reply", key=f"copy_reply_b{idx}", use_container_width=True):
                            st.code(edited_reply, language=None)
                
                # Thread builder button
                thread_key = f"thread_b{idx}"
                if thread_key not in st.session_state:
                    if st.button("🧵 Build Thread from This Tweet", key=f"gen_thread_b{idx}", use_container_width=True):
                        with st.spinner("🧵 Building your thread..."):
                            st.session_state[thread_key] = generate_thread(tweet['text'])
                            st.rerun()
                
                if thread_key in st.session_state:
                    display_thread(st.session_state[thread_key], f"b{idx}")
                
                st.markdown("---")
    
    if top_nuggets:
        st.markdown("### 🏀 NUGGETS TWEETS")
        for idx, tweet in enumerate(top_nuggets):
            display_tweet_card(tweet, is_top_pick=False)
            
            # Button to generate rewrites on demand
            rewrite_key = f"rewrites_n{idx}"
            
            if rewrite_key not in st.session_state:
                if st.button(f"✨ Generate Rewrites", key=f"gen_n{idx}", use_container_width=True):
                    with st.spinner("Generating rewrites..."):
                        st.session_state[rewrite_key] = generate_rewrites(tweet['text'])
                        st.rerun()
            
            # Show rewrites if generated
            if rewrite_key in st.session_state:
                rewrites = st.session_state[rewrite_key]
                st.markdown("**✍️ Your Rewrites (edit before copying):**")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("**📝 Default:**")
                    edited_default = st.text_area(
                        "Default",
                        value=rewrites['Default'],
                        height=100,
                        key=f"edit_default_n{idx}",
                        label_visibility="collapsed"
                    )
                    if st.button("📋 Copy Default", key=f"copy_default_n{idx}", use_container_width=True):
                        st.code(edited_default, language=None)
                    
                    st.markdown("**🔄 Retweet (Quote Tweet):**")
                    edited_retweet = st.text_area(
                        "Retweet",
                        value=rewrites['Retweet'],
                        height=100,
                        key=f"edit_retweet_n{idx}",
                        label_visibility="collapsed"
                    )
                    if st.button("📋 Copy Retweet", key=f"copy_retweet_n{idx}", use_container_width=True):
                        st.code(edited_retweet, language=None)
                
                with col2:
                    st.markdown("**🔥 Controversial:**")
                    edited_controversial = st.text_area(
                        "Controversial",
                        value=rewrites['Controversial'],
                        height=100,
                        key=f"edit_controversial_n{idx}",
                        label_visibility="collapsed"
                    )
                    if st.button("📋 Copy Controversial", key=f"copy_controversial_n{idx}", use_container_width=True):
                        st.code(edited_controversial, language=None)
                    
                    st.markdown("**💬 Reply:**")
                    edited_reply = st.text_area(
                        "Reply",
                        value=rewrites['Reply'],
                        height=100,
                        key=f"edit_reply_n{idx}",
                        label_visibility="collapsed"
                    )
                    if st.button("📋 Copy Reply", key=f"copy_reply_n{idx}", use_container_width=True):
                        st.code(edited_reply, language=None)
            
            # Thread builder button
            thread_key = f"thread_n{idx}"
            if thread_key not in st.session_state:
                if st.button("🧵 Build Thread from This Tweet", key=f"gen_thread_n{idx}", use_container_width=True):
                    with st.spinner("🧵 Building your thread..."):
                        st.session_state[thread_key] = generate_thread(tweet['text'])
                        st.rerun()
            
            if thread_key in st.session_state:
                display_thread(st.session_state[thread_key], f"n{idx}")
            
            st.markdown("---")
else:
    # No tweets in session state yet
    if scan_button or scan_new_button:
        st.warning("⚠️ No viral debates found in the last 36 hours. Try again later!")

# ========================================
# 🎙️ WEEKLY ROLLUP — PODCAST IDEAS
# ========================================
st.markdown("---")
st.markdown("## 🎙️ Weekly Rollup — Podcast Ideas")

# Load weekly data
weekly_topics, scan_count = get_weekly_topic_summary()

if scan_count == 0:
    st.info("📭 No scan history yet. Run a few scans over the week and this section will populate with podcast ideas based on the hottest debates.")
else:
    st.caption(f"Based on **{scan_count} scans** over the last 7 days")
    
    # Show weekly topic leaderboard
    if weekly_topics:
        with st.expander("📊 Weekly Topic Leaderboard", expanded=False):
            for i, topic in enumerate(weekly_topics[:12]):
                # Medal for top 3
                if i == 0:
                    medal = "🥇"
                elif i == 1:
                    medal = "🥈"
                elif i == 2:
                    medal = "🥉"
                else:
                    medal = f"#{i+1}"
                
                freq_bar = "🟧" * min(topic["appearances"], 10)
                
                subj_escaped = html_lib.escape(str(topic["subject"]))
                leaderboard_html = f'<div style="background-color: #16181c; border: 1px solid #2f3336; border-radius: 8px; padding: 10px 14px; margin-bottom: 6px; display: flex; justify-content: space-between; align-items: center;"><div><span style="font-size: 14px; margin-right: 8px;">{medal}</span><strong style="color: #e7e9ea; font-size: 14px;">{subj_escaped}</strong><span style="color: #536471; font-size: 11px; margin-left: 10px;">appeared in {topic["appearances"]}/{scan_count} scans</span></div><div style="font-size: 12px; color: #71767b;">💬 {topic["total_replies"]} · 🔄 {topic["total_retweets"]} · ❤️ {topic["total_likes"]} · 📝 {topic["total_tweets"]} tweets</div></div>'
                st.markdown(leaderboard_html, unsafe_allow_html=True)
    
    # Generate podcast ideas button
    st.markdown("")
    
    podcast_col1, podcast_col2 = st.columns([3, 1])
    
    with podcast_col1:
        generate_ideas_btn = st.button(
            "🎙️ Generate 3 Podcast Episode Ideas from This Week's Hottest Debates",
            use_container_width=True,
            type="primary"
        )
    
    with podcast_col2:
        if st.button("🗑️ Clear History", use_container_width=True):
            try:
                SCAN_HISTORY_FILE.unlink(missing_ok=True)
                if 'podcast_ideas' in st.session_state:
                    del st.session_state['podcast_ideas']
                st.success("History cleared!")
                st.rerun()
            except Exception:
                st.error("Failed to clear history")
    
    if generate_ideas_btn:
        if len(weekly_topics) < 2:
            st.warning("Need more scan data to generate good ideas. Run a few more scans!")
        else:
            with st.spinner("🧠 Claude is cooking up podcast ideas from this week's hottest debates..."):
                ideas = generate_podcast_ideas(weekly_topics)
                st.session_state.podcast_ideas = ideas
    
    # Display podcast ideas
    if 'podcast_ideas' in st.session_state:
        ideas = st.session_state.podcast_ideas
        
        st.markdown("### 🎯 Your Podcast Episode Ideas")
        
        for i, idea in enumerate(ideas):
            episode_num = i + 1
            
            # Color by rank
            if episode_num == 1:
                border_color = "#f91880"
                rank_label = "🔥 TOP PICK"
            elif episode_num == 2:
                border_color = "#ff6b35"
                rank_label = "⚡ STRONG"
            else:
                border_color = "#1d9bf0"
                rank_label = "💡 SOLID"
            
            ep_title = html_lib.escape(str(idea.get("title", "Untitled")))
            ep_hook = html_lib.escape(str(idea.get("hook", "")))
            ep_angle = html_lib.escape(str(idea.get("tylers_angle", "")))
            
            idea_html = f'''<div style="background-color: #1a2332; border: 2px solid {border_color}; border-radius: 16px; padding: 20px; margin: 16px 0;">
<div style="font-size: 11px; color: {border_color}; font-weight: bold; margin-bottom: 6px;">{rank_label} — EPISODE IDEA #{episode_num}</div>
<div style="font-size: 20px; font-weight: bold; color: #e7e9ea; margin-bottom: 12px;">🎙️ {ep_title}</div>
<div style="margin-bottom: 12px;">
<div style="font-size: 11px; color: #1d9bf0; font-weight: bold; margin-bottom: 4px;">THE HOOK</div>
<div style="font-size: 14px; color: #e7e9ea; line-height: 1.5;">{ep_hook}</div>
</div>
<div style="margin-bottom: 12px;">
<div style="font-size: 11px; color: #1d9bf0; font-weight: bold; margin-bottom: 4px;">TYLER'S ANGLE</div>
<div style="font-size: 14px; color: #e7e9ea; line-height: 1.5;">{ep_angle}</div>
</div>
</div>'''
            st.markdown(idea_html, unsafe_allow_html=True)
            
            # Segments and spicy take in expandable section
            with st.expander(f"📋 Segments & Spicy Take — Episode #{episode_num}", expanded=False):
                segments = idea.get("segments", [])
                if segments:
                    st.markdown("**Segment Breakdown:**")
                    for j, seg in enumerate(segments, 1):
                        st.markdown(f"**Segment {j}:** {seg}")
                
                spicy = idea.get("spicy_take", "")
                if spicy:
                    spicy_escaped = html_lib.escape(str(spicy))
                    spicy_html = f'''<div style="background-color: #2d1a1a; border-left: 3px solid #f91880; padding: 12px; margin-top: 12px; border-radius: 8px;">
<div style="font-size: 11px; color: #f91880; font-weight: bold; margin-bottom: 4px;">🌶️ SPICY TAKE — Lead with this for clips</div>
<div style="font-size: 15px; color: #e7e9ea; font-style: italic;">&ldquo;{spicy_escaped}&rdquo;</div>
</div>'''
                    st.markdown(spicy_html, unsafe_allow_html=True)
                
                # Copy button for the spicy take
                if spicy:
                    if st.button(f"📋 Copy Spicy Take", key=f"copy_spicy_{i}", use_container_width=True):
                        st.code(spicy, language=None)
            
            st.markdown("")

# ========================================
# 📊 MY TWEET PERFORMANCE
# ========================================
st.markdown("---")
st.markdown("## 📊 My Tweet Performance")
st.caption(f"How your recent tweets are performing — @{TYLER_USERNAME}")

if st.button("📊 Load My Tweet Performance", key="load_performance", use_container_width=True):
    with st.spinner(f"Loading @{TYLER_USERNAME}'s recent tweets..."):
        user_metrics, my_tweets = get_my_tweet_performance()
        if user_metrics and my_tweets:
            st.session_state.my_tweets = my_tweets
            st.session_state.my_user_metrics = user_metrics
        elif user_metrics is None:
            st.error(f"Could not find @{TYLER_USERNAME}. Check the username in config.")
        else:
            st.warning("No recent tweets found.")

if 'my_tweets' in st.session_state and st.session_state.my_tweets:
    my_tweets = st.session_state.my_tweets
    user_metrics = st.session_state.get('my_user_metrics', {})
    
    # Account overview
    if user_metrics:
        acct_cols = st.columns(4)
        acct_cols[0].metric("Followers", f"{user_metrics.get('followers_count', 0):,}")
        acct_cols[1].metric("Following", f"{user_metrics.get('following_count', 0):,}")
        acct_cols[2].metric("Total Tweets", f"{user_metrics.get('tweet_count', 0):,}")
        acct_cols[3].metric("Listed", f"{user_metrics.get('listed_count', 0):,}")
    
    # Performance summary
    avg_engagement = sum(t['total_engagement'] for t in my_tweets) / len(my_tweets) if my_tweets else 0
    best_tweet = my_tweets[0]  # Already sorted by engagement
    worst_tweet = my_tweets[-1]
    
    perf_cols = st.columns(3)
    perf_cols[0].metric("Avg Engagement", f"{avg_engagement:.0f}")
    perf_cols[1].metric("Best Tweet", f"{best_tweet['total_engagement']:,} eng")
    perf_cols[2].metric("Weakest Tweet", f"{worst_tweet['total_engagement']:,} eng")
    
    # Subject analysis
    subject_eng = defaultdict(lambda: {"count": 0, "total_eng": 0})
    for t in my_tweets:
        for s in t['subjects']:
            subject_eng[s]["count"] += 1
            subject_eng[s]["total_eng"] += t['total_engagement']
    
    if subject_eng:
        sorted_subjects = sorted(subject_eng.items(), key=lambda x: x[1]['total_eng'], reverse=True)
        
        with st.expander("📈 What Topics Hit Hardest?", expanded=True):
            for subj, data in sorted_subjects[:6]:
                avg = data['total_eng'] / data['count'] if data['count'] > 0 else 0
                subj_esc = html_lib.escape(str(subj))
                subj_html = f'<div style="display: flex; justify-content: space-between; align-items: center; background-color: #16181c; border-radius: 8px; padding: 10px 14px; margin-bottom: 6px;"><div><strong style="color: #e7e9ea;">{subj_esc}</strong><span style="color: #536471; font-size: 11px; margin-left: 8px;">{data["count"]} tweets</span></div><div style="font-size: 13px;"><span style="color: #1d9bf0; font-weight: bold;">{avg:.0f} avg eng</span><span style="color: #536471; margin-left: 8px;">({data["total_eng"]:,} total)</span></div></div>'
                st.markdown(subj_html, unsafe_allow_html=True)
    
    # Individual tweets ranked
    with st.expander(f"🏆 Your Top {len(my_tweets)} Recent Tweets (Ranked)", expanded=False):
        for rank, t in enumerate(my_tweets, 1):
            # Medal for top 3
            if rank == 1:
                rank_icon = "🥇"
            elif rank == 2:
                rank_icon = "🥈"
            elif rank == 3:
                rank_icon = "🥉"
            else:
                rank_icon = f"#{rank}"
            
            tweet_url = f"https://twitter.com/{TYLER_USERNAME}/status/{t['id']}"
            
            # Engagement color
            if rank <= 3:
                eng_color = "#00ba7c"
            elif rank <= 10:
                eng_color = "#1d9bf0"
            else:
                eng_color = "#f4212e"
            
            created = t.get('created_at', '')
            if created and hasattr(created, 'strftime'):
                time_str = created.strftime('%b %d, %I:%M %p')
            else:
                time_str = str(created)[:16]
            
            tweet_text_esc = html_lib.escape(str(t["text"][:120])) + ("..." if len(t["text"]) > 120 else "")
            ranked_html = f'<div style="background-color: #16181c; border: 1px solid #2f3336; border-radius: 10px; padding: 12px; margin-bottom: 8px;"><div style="display: flex; justify-content: space-between; align-items: flex-start;"><div style="flex: 1;"><span style="font-size: 14px; margin-right: 8px;">{rank_icon}</span><span style="font-size: 13px; color: #e7e9ea;">{tweet_text_esc}</span></div><div style="flex-shrink: 0; margin-left: 12px; text-align: right;"><div style="font-size: 18px; font-weight: bold; color: {eng_color};">{t["total_engagement"]:,}</div><div style="font-size: 10px; color: #536471;">total eng</div></div></div><div style="display: flex; gap: 16px; font-size: 12px; color: #71767b; margin-top: 8px;"><span>💬 {t["replies"]}</span><span>🔄 {t["retweets"]}</span><span>❤️ {t["likes"]}</span><span style="color: #536471;">{time_str}</span><a href="{tweet_url}" target="_blank" style="color: #1d9bf0; text-decoration: none;">View →</a></div></div>'
            st.markdown(ranked_html, unsafe_allow_html=True)

# ========================================
# 🎯 REPLY TARGET FINDER
# ========================================
st.markdown("---")
st.markdown("## 🎯 Reply Target Finder")
st.caption("Big accounts tweeting about Broncos/Nuggets right now — reply for maximum visibility")

reply_cols = st.columns([3, 1])

with reply_cols[0]:
    find_targets_btn = st.button("🎯 Find Reply Targets (25K+ followers)", key="find_reply_targets", use_container_width=True, type="primary")

with reply_cols[1]:
    min_followers_k = st.selectbox("Min followers", [10, 25, 50, 100], index=1, format_func=lambda x: f"{x}K+")

if find_targets_btn:
    with st.spinner("🔍 Scanning for high-follower accounts tweeting about Denver sports..."):
        targets = find_reply_targets(min_followers=min_followers_k * 1000)
        st.session_state.reply_targets = targets

if 'reply_targets' in st.session_state:
    targets = st.session_state.reply_targets
    
    if not targets:
        st.info("No high-follower accounts found tweeting about Broncos/Nuggets in the last 24 hours. Try lowering the follower minimum.")
    else:
        st.success(f"🎯 Found {len(targets)} reply opportunities!")
        
        for t_idx, target in enumerate(targets):
            tweet_url = f"https://twitter.com/{target['author']}/status/{target['id']}"
            reply_url = tweet_url
            
            # Format follower count
            followers = target['followers']
            if followers >= 1_000_000:
                follower_str = f"{followers/1_000_000:.1f}M"
            elif followers >= 1000:
                follower_str = f"{followers/1000:.0f}K"
            else:
                follower_str = str(followers)
            
            # Opportunity level
            if t_idx == 0:
                opp_color = "#f91880"
                opp_label = "🔥 BEST OPPORTUNITY"
            elif t_idx <= 2:
                opp_color = "#ff6b35"
                opp_label = "⚡ HIGH VALUE"
            else:
                opp_color = "#1d9bf0"
                opp_label = "💡 WORTH A REPLY"
            
            verified_badge = " ✅" if target.get('verified') else ""
            
            target_name_esc = html_lib.escape(str(target['author_name']))
            target_text_esc = html_lib.escape(str(target['text'][:200])) + ("..." if len(target['text']) > 200 else "")
            
            target_html = f'<div style="background-color: #16181c; border: 1px solid {opp_color}; border-radius: 12px; padding: 16px; margin-bottom: 10px;"><div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;"><div><span style="font-size: 10px; color: {opp_color}; font-weight: bold;">{opp_label}</span><br><strong style="color: #e7e9ea; font-size: 15px;">{target_name_esc}{verified_badge}</strong><span style="color: #71767b;"> @{target["author"]}</span><span style="background-color: #2f3336; color: #e7e9ea; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: bold; margin-left: 8px;">👥 {follower_str}</span></div></div><div style="font-size: 14px; color: #e7e9ea; line-height: 1.4; margin-bottom: 10px;">{target_text_esc}</div><div style="display: flex; gap: 16px; font-size: 12px; color: #71767b; margin-bottom: 10px;"><span>💬 {target["replies"]}</span><span>🔄 {target["retweets"]}</span><span>❤️ {target["likes"]}</span></div><div style="display: flex; gap: 10px;"><a href="{tweet_url}" target="_blank" style="color: #1d9bf0; text-decoration: none; font-size: 13px;">🔗 View Tweet</a><a href="{reply_url}" target="_blank" style="background-color: #1d9bf0; color: white; padding: 4px 14px; border-radius: 16px; text-decoration: none; font-size: 13px; font-weight: bold;">💬 Reply Now →</a></div></div>'
            st.markdown(target_html, unsafe_allow_html=True)
            
            # Generate a quick reply suggestion
            reply_gen_key = f"reply_suggestion_{t_idx}"
            if reply_gen_key not in st.session_state:
                if st.button(f"✨ Generate Reply Suggestion", key=f"gen_reply_sug_{t_idx}", use_container_width=True):
                    with st.spinner("Crafting your reply..."):
                        reply_prompt = f'''You are Tyler Polumbus — former Broncos OL (Super Bowl 50), radio host on Altitude 92.5. Write a smart, engaging reply to this tweet from @{target['author']} ({follower_str} followers):

"{target['text']}"

Your reply should:
- Be under 280 characters
- Add insider value or a strong opinion
- Be the kind of reply that makes their followers want to follow YOU
- Sound natural, not like a bot

Return just the reply text, nothing else.'''
                        
                        try:
                            reply_msg = client.messages.create(
                                model="claude-sonnet-4-5-20250929",
                                max_tokens=300,
                                messages=[{"role": "user", "content": reply_prompt}]
                            )
                            st.session_state[reply_gen_key] = reply_msg.content[0].text.strip().strip('"')
                            st.rerun()
                        except Exception as e:
                            st.session_state[reply_gen_key] = f"ERROR: {str(e)}"
                            st.rerun()
            
            if reply_gen_key in st.session_state:
                suggestion = st.session_state[reply_gen_key]
                edited_suggestion = st.text_area(
                    "Reply suggestion",
                    value=suggestion,
                    height=70,
                    key=f"edit_reply_sug_{t_idx}",
                    label_visibility="collapsed"
                )
                
                sug_col1, sug_col2 = st.columns(2)
                with sug_col1:
                    if st.button("📋 Copy Reply", key=f"copy_reply_sug_{t_idx}", use_container_width=True):
                        st.code(edited_suggestion, language=None)
                with sug_col2:
                    # Direct reply intent URL with pre-filled text
                    intent_url = f"https://twitter.com/intent/tweet?in_reply_to={target['id']}&text={quote_plus(edited_suggestion)}"
                    st.markdown(f'<a href="{intent_url}" target="_blank" style="display: block; background-color: #1d9bf0; color: white; text-align: center; padding: 8px; border-radius: 20px; text-decoration: none; font-weight: bold;">🚀 Post Reply on 𝕏 →</a>', unsafe_allow_html=True)
            
            st.markdown("")
